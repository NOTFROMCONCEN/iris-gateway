# Iris AI Gateway

个人统一 AI 网关 —— 在不同 AI 客户端（opencode、Claude Code、Cline、Continue 等）之间，通过网关统一调用 AI，实现**跨端统一记忆、统一人格、统一 MCP/SKILL**。

## 设计目标

**单用户多终端**：这是为"我"个人设计的 AI 中间层。无论使用哪个客户端、哪个协议，都共享同一套记忆、人格和工具能力。

```
opencode (OpenAI协议)  ──┐
Claude Code (Anthropic) ──┤
Cline (OpenAI协议)      ──┼──→ Iris Gateway ──→ 上游 AI (Kimi/OpenAI/Anthropic)
Continue (OpenAI协议)    ──┤      ↑
自定义客户端 (任一协议)  ──┘      │
                          统一记忆 + 人格 + MCP + SKILL
```

## 核心特性

- **双向协议兼容**：对外同时暴露 OpenAI (`/v1/chat/completions`) 和 Anthropic (`/v1/messages`) API 端点，任何兼容客户端可直接接入
- **跨端统一记忆**：无论从哪个客户端发起对话，共享同一份记忆（短期 + 长期摘要），实现"在 Claude Code 聊过的内容，opencode 里也记得"
- **统一人格系统**：YAML 配置人格，所有客户端共享同一 AI 性格和行为风格
- **上游伪装**：模拟 Claude Code 等工具的请求特征，绕过调用源限制
- **感知分析**：基于规则引擎的情绪、意图、关键词分析
- **流式响应**：完整支持 SSE 流式代理 OpenAI 和 Anthropic 的 streaming

## 当前实现状态

| 能力 | 状态 | 说明 |
|------|------|------|
| 双向协议兼容 | ✅ 已完成 | OpenAI + Anthropic 端点，含流式 |
| 跨端统一记忆 | ✅ 已完成 | SQLite / Ombre-Brain 后端，短期窗口 + 长期摘要 |
| 统一人格 | ✅ 已完成 | YAML 配置 → System Prompt 注入 |
| 上游伪装 | ✅ 已完成 | Claude Code / OpenAI 伪装，Headers 可配置 |
| 感知分析 | ✅ 已完成 | 规则引擎：情绪/意图/关键词/紧急度 |
| Provider 调度 | ✅ 已完成 | 重试 + 连接池 + 模型别名映射 |
| MCP 工具代理 | 🔲 规划中 | 将 MCP 工具统一暴露给所有客户端 |
| SKILL 系统 | 🔲 规划中 | 可复用的技能定义和执行框架 |
| 跨协议多模态 | 🔲 规划中 | OpenAI ↔ Anthropic 图片/文件块互转 |

## 快速开始

### 1. 安装依赖

```bash
cd iris-gateway
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入你的上游 API Key
```

### 3. 启动服务

```bash
python main.py
# 或
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 开发与测试

```bash
pip install -r requirements-dev.txt
python -m pytest -q
# 或
npm test
```

测试配置固定只收集 `tests/`，避免外部嵌套仓库或运行时目录影响本项目测试。

### 5. 使用客户端连接

#### opencode 配置 (OpenAI 协议)

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "iris": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Iris Gateway",
      "options": {
        "baseURL": "http://localhost:8000/v1",
        "apiKey": "your-iris-api-key"
      },
      "models": {
        "kimi-for-coding": { "name": "Kimi for Coding" },
        "kimi-k2": { "name": "Kimi K2" }
      }
    }
  }
}
```

#### Claude Code 配置 (Anthropic 协议)

```bash
export ANTHROPIC_BASE_URL=http://localhost:8000
export ANTHROPIC_API_KEY=your-iris-api-key
claude
```

## API 端点

| 端点 | 协议 | 说明 |
|------|------|------|
| `POST /v1/chat/completions` | OpenAI | 聊天补全（含流式） |
| `GET /v1/models` | OpenAI | 模型列表 |
| `POST /v1/messages` | Anthropic | Messages API（含流式） |
| `GET /v1/models` | Anthropic | 模型列表 |
| `GET /health` | - | 健康检查 |

## 人格配置

在 `config/personas/` 目录下创建 YAML 文件：

```yaml
id: "coder"
name: "CodeMaster"
description: "专业的编程助手"
system_prompt: "你是 CodeMaster，专注于代码和架构..."
personality_traits:
  friendliness: 0.7
  creativity: 0.8
  verbosity: 0.3  # 简洁
speaking_style: "技术、精准、高效"
response_guidelines:
  - "提供可运行的代码示例"
  - "解释设计决策"
```

## Docker 部署

```bash
docker-compose up -d
docker compose ps
```

Docker Compose 健康检查使用 Python 标准库访问 `/health`，不依赖镜像内额外安装 `curl`。部署前请在 `.env` 中配置上游 API Key 和 `IRIS_API_KEYS`，避免网关在公网环境下无认证暴露。

## 外部依赖

`external/ombre-brain/` 是本地外部仓库目录，已被 `.gitignore` 排除，不会随 Iris Gateway 提交。需要 Ombre-Brain 后端时，请单独 clone 或复制该仓库到此路径，并自行记录使用的版本。

## 项目结构

```
iris-gateway/
├── main.py              # FastAPI 入口
├── bootstrap.py         # 应用启动引导（组件初始化）
├── middleware.py         # API Key 认证中间件
├── disguise.py           # 上游伪装层
├── config/              # 配置管理 + 人格文件
├── models/              # 数据模型 (OpenAI + Anthropic + 内部 + 异常)
├── api/                 # API 兼容路由
├── core/                # 核心处理 (协议转换、人格注入、感知分析)
│   ├── persona/         # 人格加载器 + 注入器
│   └── perception/      # 感知分析器
├── memory/              # 记忆管理
│   └── backends/        # 存储后端 (SQLite, Ombre-Brain)
├── providers/           # 上游 Provider (OpenAI, Anthropic, 调度器)
├── utils/               # 日志等工具
├── scripts/             # 启动脚本、客户端配置
└── tests/               # 测试 (api/ core/ memory/ providers/ config/)
```

## 架构

```
下游客户端 (opencode / Claude Code / Cline / ...)
    ↓ OpenAI 或 Anthropic 协议
API 兼容层 (认证 + 路由)
    ↓ 协议转换
核心处理器
    ↓ 人格注入 ← 记忆检索 ← 感知分析
Provider 调度器
    ↓ 伪装层
上游 AI API (Kimi / OpenAI / Anthropic)
```

## 许可

MIT License
