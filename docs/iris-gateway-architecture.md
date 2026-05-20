# Iris AI Gateway - 系统架构设计

## 1. 需求确认

### 核心目标
1. **下游兼容**：对外暴露 OpenAI (`/v1/chat/completions`) 和 Anthropic (`/v1/messages`) 兼容 API，让 opencode、Claude Code、Cline、Continue 等工具直接连入
2. **上游伪装**：模拟 Claude Code 等工具的请求特征调用 Anthropic/OpenAI API，绕过调用源限制
3. **统一增强**：在请求链路中注入统一人格、记忆上下文、感知分析，实现跨端一致体验
4. **多人共享**：多用户会话隔离，跨地域/时间的人格和记忆统一

### 伪装策略（上游 → Anthropic/OpenAI）
| 特征 | Claude Code 典型值 | Iris 伪装实现 |
|------|-------------------|--------------|
| User-Agent | `ClaudeCode/0.2.x` | 可配置伪装 |
| X-Stainless-Arch | `x64` 等 | 可配置伪装 |
| X-Stainless-Lang | `python` 等 | 可配置伪装 |
| X-Stainless-OS | `Mac OS` 等 | 可配置伪装 |
| X-Stainless-Runtime | `CPython` 等 | 可配置伪装 |
| X-Stainless-Runtime-Version | `3.11.x` 等 | 可配置伪装 |
| anthropic-version | `2023-06-01` | 按上游要求配置 |

**注意**：Anthropic 可能通过请求签名、TLS fingerprint、API Key 来源、甚至行为模式检测第三方客户端。伪装层应设计为可插拔，可灵活调整。

---

## 2. 系统架构

```mermaid
graph TB
    subgraph Clients [下游客户端]
        OC[opencode-ai<br>OpenAI协议]
        CC[Claude Code<br>Anthropic协议]
        CL[Cline/Continue<br>OpenAI协议]
        CU[其他自定义客户端]
    end

    subgraph Iris [Iris Gateway 核心]
        direction TB

        subgraph API_Layer [API 兼容层]
            OEP[OpenAI 端点<br>/v1/chat/completions<br>/v1/models]
            AEP[Anthropic 端点<br>/v1/messages<br>/v1/models]
            MK[/认证中间件<br>API Key 验证 + 用户识别]
        end

        subgraph Core_Layer [核心处理层]
            PT[协议转换器<br>外部格式 ↔ 内部格式]
            PI[人格注入器<br>System Prompt 注入 + 特征渲染]
            MS[记忆管理器<br>短期记忆 + 长期记忆 + 摘要]
            PS[感知分析器<br>情绪 + 意图 + 关键词 + 紧急度]
            SM[会话管理器<br>多用户隔离 + 跨端恢复]
        end

        subgraph Upstream_Layer [上游代理层]
            UD[Provider 调度器<br>路由 + 负载均衡 + 重试]
            CL_D[Claude 伪装器<br>Headers + User-Agent + 指纹]
            OAI_D[OpenAI 伪装器<br>Headers + 代理配置]
        end
    end

    subgraph Upstream [上游 API]
        ANTH[Anthropic API<br>Messages API]
        OAI[OpenAI API<br>Chat Completions API]
    end

    OC -->|OpenAI格式| OEP
    CC -->|Anthropic格式| AEP
    CL -->|OpenAI格式| OEP
    CU -->|任一格式| OEP
    CU -->|任一格式| AEP

    OEP --> MK
    AEP --> MK
    MK --> PT
    PT --> PI
    PI --> MS
    MS --> PS
    PS --> UD
    UD -->|Claude 伪装| CL_D
    UD -->|OpenAI 伪装| OAI_D
    CL_D --> ANTH
    OAI_D --> OAI
```

---

## 3. 目录结构

```
iris-gateway/
├── main.py                          # FastAPI 入口
├── config/
│   ├── __init__.py
│   ├── settings.py                  # Pydantic Settings 配置
│   └── personas/                    # 人格配置文件目录
│       └── default.yaml
├── models/
│   ├── __init__.py
│   ├── schemas.py                   # 统一数据模型（已有）
│   ├── openai_schemas.py            # OpenAI API 格式模型
│   └── anthropic_schemas.py         # Anthropic API 格式模型
├── api/
│   ├── __init__.py
│   ├── openai.py                    # OpenAI 兼容路由
│   ├── anthropic.py                 # Anthropic 兼容路由
│   └── health.py                    # 健康检查路由
├── core/
│   ├── __init__.py
│   ├── protocol_converter.py        # 协议转换器
│   ├── persona_injector.py          # 人格注入器
│   ├── session_manager.py           # 会话管理器
│   └── perception_analyzer.py       # 感知分析器
├── memory/
│   ├── __init__.py
│   ├── base.py                      # 记忆存储抽象接口
│   ├── sqlite_backend.py            # SQLite 存储实现
│   ├── redis_backend.py             # Redis 存储实现
│   └── manager.py                   # 记忆管理器（窗口+检索+摘要）
├── providers/
│   ├── __init__.py
│   ├── base.py                      # Provider 抽象接口
│   ├── anthropic_provider.py        # Anthropic 上游 Provider
│   ├── openai_provider.py           # OpenAI 上游 Provider
│   └── dispatcher.py                # Provider 调度器
├── disguise/
│   ├── __init__.py
│   ├── claude_disguise.py           # Claude Code 伪装
│   ├── openai_disguise.py           # OpenAI 伪装
│   └── config.py                    # 伪装配置
├── middleware/
│   ├── __init__.py
│   └── auth.py                      # API Key 认证中间件
├── utils/
│   ├── __init__.py
│   ├── stream_handler.py            # SSE 流式处理工具
│   └── logging.py                   # 日志配置
├── data/                            # 数据目录
│   └── memory/
├── tests/                           # 测试目录
│   ├── __init__.py
│   ├── test_api.py
│   ├── test_converter.py
│   └── test_memory.py
├── requirements.txt
├── .env.example
├── Dockerfile
└── docker-compose.yml
```

---

## 4. 模块详细设计

### 4.1 API 兼容层 (`api/`)

#### OpenAI 端点
- `POST /v1/chat/completions` - 聊天补全（支持 streaming）
- `GET /v1/models` - 模型列表
- `POST /v1/completions` - 兼容旧版（可选）

#### Anthropic 端点
- `POST /v1/messages` - Messages API（支持 streaming）
- `GET /v1/models` - 模型列表

**处理流程**：
1. 接收客户端请求（OpenAI 或 Anthropic 格式）
2. 通过 `api/` 路由解析为各自 schema
3. 验证 API Key（提取用户身份）
4. 转换为内部 `ChatRequest` 格式
5. 进入核心处理层
6. 核心层返回 `ChatResponse`
7. 转换回客户端请求的格式（OpenAI 或 Anthropic）
8. 返回响应（支持 SSE streaming）

### 4.2 协议转换器 (`core/protocol_converter.py`)

```python
class ProtocolConverter:
    @staticmethod
    def openai_to_internal(req: OpenAIChatRequest) -> ChatRequest:
        """OpenAI 格式 → 内部统一格式"""
    
    @staticmethod
    def anthropic_to_internal(req: AnthropicMessageRequest) -> ChatRequest:
        """Anthropic 格式 → 内部统一格式"""
    
    @staticmethod
    def internal_to_openai(resp: ChatResponse, stream: bool = False) -> dict:
        """内部格式 → OpenAI 响应格式"""
    
    @staticmethod
    def internal_to_anthropic(resp: ChatResponse, stream: bool = False) -> dict:
        """内部格式 → Anthropic 响应格式"""
```

**关键转换**：
- OpenAI 的 `system` role ↔ Anthropic 的 `system` 参数
- OpenAI 的 `messages` 列表 ↔ Anthropic 的 `messages` 列表
- OpenAI 的 `model` 字段 ↔ Anthropic 的 `model` 字段（映射表）
- OpenAI 的 SSE `data: {...}` ↔ Anthropic 的 SSE `event: content_block_delta`

### 4.3 人格注入器 (`core/persona_injector.py`)

```python
class PersonaInjector:
    def inject(self, messages: List[Message], persona: PersonaConfig) -> List[Message]:
        """
        1. 将人格的 system_prompt 注入为第一条 system 消息
        2. 动态渲染 personality_traits 为 traits 描述
        3. 应用 speaking_style 到 system prompt
        4. 插入 response_guidelines
        """
```

### 4.4 记忆管理器 (`memory/`)

```python
class MemoryManager:
    def get_context(self, session_id: str, persona_id: str, 
                    current_messages: List[Message]) -> List[Message]:
        """
        1. 获取短期记忆窗口（最近 N 条消息）
        2. 检索长期相关记忆（基于 embedding 相似度）
        3. 获取记忆摘要（如果消息数超过阈值）
        4. 组装为增强的 messages 列表
        """
    
    def store(self, session_id: str, entry: MemoryEntry):
        """存储新记忆"""
    
    def summarize(self, session_id: str):
        """触发记忆摘要生成"""
```

### 4.5 感知分析器 (`core/perception_analyzer.py`)

```python
class PerceptionAnalyzer:
    async def analyze(self, messages: List[Message]) -> PerceptionResult:
        """
        可选：使用轻量级模型或规则引擎分析用户消息
        - 情绪识别
        - 意图分类
        - 关键词提取
        - 紧急度评估
        """
```

### 4.6 Provider 调度器 (`providers/`)

```python
class ProviderDispatcher:
    async def dispatch(self, request: ChatRequest, 
                       disguise_config: DisguiseConfig) -> ChatResponse:
        """
        1. 根据 request.provider 选择目标 Provider
        2. 应用伪装配置（Headers、User-Agent 等）
        3. 发送请求到上游 API
        4. 返回上游响应
        """

class AnthropicProvider(BaseProvider):
    async def chat(self, request: ChatRequest, 
                   disguise: ClaudeDisguise) -> AsyncIterator[StreamChunk]:
        """伪装为 Claude Code 调用 Anthropic API"""

class OpenAIProvider(BaseProvider):
    async def chat(self, request: ChatRequest,
                   disguise: OpenAIDisguise) -> AsyncIterator[StreamChunk]:
        """调用 OpenAI API"""
```

### 4.7 伪装层 (`disguise/`)

```python
@dataclass
class DisguiseConfig:
    user_agent: str
    headers: Dict[str, str]
    client_name: str  # "claude-code", "opencode", "custom"

class ClaudeDisguise:
    """Claude Code 伪装
    
    模拟 Claude Code 的请求特征：
    - User-Agent: "ClaudeCode/0.2.32 (darwin; arm64)"
    - X-Stainless-Arch: "arm64"
    - X-Stainless-Lang: "python"
    - X-Stainless-OS: "Mac OS"
    - X-Stainless-Runtime: "CPython"
    - X-Stainless-Runtime-Version: "3.11.7"
    - X-Stainless-Package-Version: "0.46.0"
    - anthropic-version: "2023-06-01"
    - anthropic-beta: "prompt-caching-2024-07-31,computer-use-2024-10-22"
    """
    
    def apply(self, headers: Dict[str, str]) -> Dict[str, str]:
        """应用伪装 headers 到请求"""
```

---

## 5. 配置扩展

### 新增配置项（settings.py）

```python
# === 伪装配置 ===
claude_disguise_enabled: bool = False
claude_disguise_user_agent: str = "ClaudeCode/0.2.32 (darwin; arm64)"
claude_disguise_headers: Dict[str, str] = Field(default_factory=dict)

# === 人格配置 ===
persona_config_dir: str = "./config/personas"

# === 上游 Provider 配置 ===
upstream_timeout: int = 120
upstream_max_retries: int = 3
upstream_retry_delay: float = 1.0

# === 模型映射 ===
# 允许客户端使用通用 model 名称，网关映射到上游实际 model
model_mapping: Dict[str, str] = Field(default_factory=lambda: {
    "gpt-4o": "gpt-4o",
    "claude-sonnet-4": "claude-sonnet-4-20250514",
})
```

### 人格 YAML 配置示例

```yaml
# config/personas/default.yaml
id: "default"
name: "Iris"
description: "一个友好、智能的AI助手"
system_prompt: |
  你是 Iris，一个跨平台统一AI助手。你拥有持久记忆和统一人格。
  无论用户通过什么客户端与你交互，你都会保持一致的风格和记忆。
personality_traits:
  friendliness: 0.8
  formality: 0.5
  creativity: 0.7
  empathy: 0.8
  humor: 0.6
  verbosity: 0.5
speaking_style: "自然、友好、有条理"
knowledge_domains: []
forbidden_topics: []
default_emotion: "neutral"
response_guidelines:
  - "保持回答简洁但有信息量"
  - "在不确定时诚实承认"
  - "优先使用用户偏好的语言"
```

---

## 6. 流式响应设计

### OpenAI SSE 格式
```
data: {"id":"...","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant","content":"Hello"}}]}

data: {"id":"...","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":" world"}}]}

data: {"id":"...","object":"chat.completion.chunk","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

### Anthropic SSE 格式
```
event: message_start
data: {"type":"message_start","message":{"id":"...","type":"message","role":"assistant","model":"claude-sonnet-4-20250514","content":[],"stop_reason":null,"usage":{"input_tokens":10,"output_tokens":1}}}

event: content_block_start
data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}

...

event: message_stop
data: {"type":"message_stop"}
```

### Iris 流式处理
1. 接收下游 streaming 请求
2. 向上游发起 streaming 请求
3. 将上游 SSE chunks 转换为内部 `StreamChunk`
4. 根据下游请求格式（OpenAI/Anthropic）转换回对应 SSE 格式
5. 通过 FastAPI `StreamingResponse` 返回

---

## 7. 关键实现要点

### 7.1 多用户隔离
- API Key → User ID 映射
- Session ID = hash(user_id + client_id + 可选自定义标识)
- 每个用户的记忆完全隔离

### 7.2 跨端会话恢复
- 用户可通过在请求中指定 `session_id` 恢复会话
- 网关自动将同一用户的不同 session 关联到同一记忆空间
- 支持基于用户 ID 的跨会话记忆检索

### 7.3 模型映射
- 客户端可以请求通用模型名（如 `"gpt-4o"`）
- 网关根据目标 Provider 映射到实际模型名
- 支持通过配置自定义映射

### 7.4 错误处理
- 上游错误透明转发（转换格式）
- 网关内部错误统一包装为对应协议的 ErrorResponse
- 重试机制（指数退避）

---

## 8. 实现阶段

| 阶段 | 内容 | 优先级 |
|------|------|--------|
| Phase 1 | 项目骨架 + API 兼容端点 + 协议转换 + 流式响应 | P0 |
| Phase 2 | 上游伪装层 + Provider 抽象 + 调度策略 | P0 |
| Phase 3 | 人格系统 + 记忆系统 + 感知系统 | P1 |
| Phase 4 | 多用户会话 + 认证 + 配置扩展 | P1 |
| Phase 5 | 测试 + 文档 + Docker 部署 | P2 |
