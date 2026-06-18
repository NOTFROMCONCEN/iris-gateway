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

## 安装

### 1. 准备环境

- Python 3.11+
- pip
- 可选：Node.js 18+，仅在使用仓库内置 opencode 脚本时需要
- 可选：Docker Desktop / Docker Compose，容器部署时需要

### 2. 获取代码并安装 Python 依赖

```powershell
git clone https://github.com/NOTFROMCONCEN/iris-gateway.git
cd iris-gateway
python -m pip install -r requirements.txt
```

开发或运行测试时安装开发依赖：

```powershell
python -m pip install -r requirements-dev.txt
```

### 3. 配置环境变量

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，至少配置：

```env
IRIS_API_KEYS=iris-key-1
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
```

常用配置说明：

| 配置 | 说明 |
|------|------|
| `IRIS_API_KEYS` | 访问 Iris Gateway 的客户端 API Key，多个值用逗号分隔 |
| `OPENAI_API_KEY` | OpenAI 或 OpenAI 兼容上游 API Key |
| `ANTHROPIC_API_KEY` | Anthropic 或 Anthropic 兼容上游 API Key |
| `MEMORY_BACKEND` | 记忆后端，默认 `sqlite`，也可使用 `ombre` 或 `none` |
| `MODEL_ALIASES` | 客户端模型别名到真实模型名的 JSON 映射 |
| `MODEL_PROVIDERS` | 真实模型名到 `openai` / `anthropic` provider 的 JSON 映射 |

## 启动

### 本地启动

```powershell
python main.py
```

开发模式可使用 uvicorn reload：

```powershell
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Windows 下也可以使用启动脚本：

```powershell
.\scripts\start-gateway.bat
```

启动后检查：

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready
```

### Docker 启动

Docker 配置位于 `deploy/` 目录：

```powershell
docker compose -f deploy/docker-compose.yml up -d
docker compose -f deploy/docker-compose.yml ps
```

停止服务：

```powershell
docker compose -f deploy/docker-compose.yml down
```

Docker Compose 健康检查使用轻量 `/health`，不会因为上游 Provider 短暂不可用而重启容器。需要确认上游就绪状态时访问 `/ready`。

## 使用

### OpenAI 兼容客户端

将客户端的 OpenAI Base URL 指向：

```text
http://localhost:8000/v1
```

API Key 使用 `.env` 中配置的任意一个 `IRIS_API_KEYS`。

最小请求示例：

```powershell
$headers = @{
  Authorization = "Bearer iris-key-1"
  "Content-Type" = "application/json"
}

$body = @{
  model = "kimi-k2"
  messages = @(
    @{ role = "user"; content = "你好，介绍一下 Iris Gateway" }
  )
} | ConvertTo-Json -Depth 10

Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/v1/chat/completions `
  -Headers $headers `
  -Body $body
```

### Anthropic 兼容客户端

将 Anthropic Base URL 指向：

```text
http://localhost:8000
```

API Key 同样使用 `IRIS_API_KEYS`。

Claude Code 可这样连接：

```powershell
$env:ANTHROPIC_BASE_URL = "http://localhost:8000"
$env:ANTHROPIC_API_KEY = "iris-key-1"
claude
```

### opencode

仓库内置了 opencode 配置和启动脚本。首次使用先安装脚本目录下的 npm 依赖：

```powershell
cd scripts
npm install
cd ..
```

启动 opencode：

```powershell
.\scripts\start-opencode.bat
```

配置文件位于 `scripts/opencode.json`，默认连接：

```json
{
  "baseURL": "http://localhost:8000/v1",
  "apiKey": "your-iris-api-key"
}
```

### 健康检查与模型列表

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready
Invoke-RestMethod http://localhost:8000/v1/models -Headers @{ Authorization = "Bearer iris-key-1" }
```

`/health` 只表示进程存活；`/ready` 会检查 Provider 和记忆组件状态。

## 开发与测试

```powershell
python -m pytest -q
python -m ruff check .
```

也可以使用 `scripts/` 下的 npm 包装命令：

```powershell
npm --prefix scripts test
```

测试配置固定只收集 `tests/`，避免外部嵌套仓库或运行时目录影响本项目测试。

## API 端点

| 端点 | 协议 | 说明 |
|------|------|------|
| `POST /v1/chat/completions` | OpenAI | 聊天补全（含流式） |
| `GET /v1/models` | OpenAI | 模型列表 |
| `POST /v1/messages` | Anthropic | Messages API（含流式） |
| `GET /v1/models` | Anthropic | 模型列表 |
| `GET /health` | - | 轻量存活检查，不访问上游 |
| `GET /ready` | - | 就绪检查，包含 Provider 状态 |

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
├── deploy/              # Dockerfile 和 Docker Compose 部署配置
├── scripts/             # 启动脚本、客户端配置、opencode npm 依赖
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
