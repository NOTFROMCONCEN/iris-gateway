# Iris AI Gateway

统一 AI 网关，兼容 OpenAI 和 Anthropic API 协议，支持人格系统、记忆系统、感知能力，以及上游伪装功能。

## 核心特性

- **双向协议兼容**：对外同时暴露 OpenAI (`/v1/chat/completions`) 和 Anthropic (`/v1/messages`) API 端点
- **上游伪装**：模拟 Claude Code 等工具的请求特征，绕过调用源限制
- **统一人格系统**：YAML 配置人格，跨端一致的 AI 性格和行为风格
- **记忆系统**：SQLite 存储，短期记忆窗口 + 长期记忆摘要
- **感知分析**：基于规则引擎的情绪、意图、关键词分析
- **流式响应**：完整支持 SSE 流式代理 OpenAI 和 Anthropic 的 streaming
- **多用户隔离**：API Key 认证 + 会话隔离

## 快速开始

### 1. 安装依赖

```bash
cd iris-gateway
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入你的 API Key
```

### 3. 启动服务

```bash
python main.py
# 或
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 使用客户端连接

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
        "gpt-4o": { "name": "GPT-4o" },
        "claude-sonnet-4-20250514": { "name": "Claude Sonnet 4" }
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
```

## 项目结构

```
iris-gateway/
├── main.py              # FastAPI 入口
├── config/              # 配置管理 + 人格文件
├── models/              # 数据模型 (OpenAI + Anthropic + 内部)
├── api/                 # API 兼容路由
├── core/                # 协议转换器、人格注入、感知分析、核心处理器
├── memory/              # 记忆存储 (SQLite)
├── providers/           # 上游 Provider 抽象
├── disguise/            # 伪装层
├── middleware/          # 认证中间件
└── tests/               # 测试
```

## 架构

```
下游客户端 → API兼容层 → 协议转换 → 核心处理器
                                              ↓
人格注入 ← 记忆检索 ← 感知分析 ← 请求处理
                                              ↓
Provider调度 → 伪装层 → 上游API (OpenAI/Anthropic)
```

## 许可

MIT License
