# Iris Gateway TODO

## P0 - Stability

- [x] Initialize a git repository and establish a baseline commit.
- [x] Tag the baseline as `baseline-before-optimizations`.
- [x] Make `python -m pytest -q` collect only project tests reliably.
- [x] Fix Docker healthcheck so it does not depend on missing `curl`.
- [x] Add `.dockerignore` to keep secrets, caches, data, and external repos out of images.
- [x] Add `.gitattributes` to reduce CRLF/LF churn on Windows.
- [x] Document development test commands and Docker startup notes in `README.md`.

## P1 - Core Behavior

- [x] Inject short-term memory into request context instead of only fetching it.
- [x] Add memory-context tests for short-term memory, summaries, and no-memory cases.
- [x] Fix OpenAI streaming chunks so `finish_reason` stays on the choice, not inside `delta`.
- [x] Improve Anthropic stream finish events and output token accounting.
- [x] Preserve upstream status codes and error type where practical.

## P2 - Protocol Compatibility

- [x] Preserve OpenAI parameters such as `logit_bias` and `max_completion_tokens`.
- [x] Support OpenAI tool call round trips more completely.
- [x] Support Anthropic `tool_use` and `tool_result` blocks more completely.
- [x] Make multimodal handling explicit: preserve supported blocks or return clear errors.
- [x] Add conversion tests for tool and multimodal paths.

## P3 - Configuration And Deployment

- [x] Move hard-coded model list into configuration.
- [x] Add client model alias mapping to upstream model ids.
- [x] Add configurable CORS origins.
- [x] Warn strongly or fail closed when production runs without `IRIS_API_KEYS`.
- [x] Run the Docker image as a non-root user.

## P4 - Engineering Quality

- [x] Add linting, for example `ruff`.
- [x] Add a CI workflow.
- [x] Add a mock provider test path that avoids real upstream APIs.
- [x] Document how `external/ombre-brain` should be cloned or pinned.
- [x] Reconcile README claims with the currently implemented backend support.

## P5 - Directory Structure Optimization

- [x] P0: Extract `main.py` initialization logic into `bootstrap.py`.
- [x] P1: Split `core/` into sub-packages (`persona/`, `perception/`).
- [x] P1: Move memory backends to `memory/backends/` sub-directory.
- [x] P2: Relocate `utils/exceptions.py` → `models/exceptions.py`.
- [x] P2: Relocate `utils/upstream_errors.py` → `providers/upstream_errors.py`.
- [x] P2: Merge `disguise/` package into single `disguise.py` file.
- [x] P2: Merge `middleware/` package into single `middleware.py` file.
- [x] P2: Restructure `tests/` into sub-directories (`api/`, `core/`, `memory/`, `providers/`, `config/`).
- [x] P3: Clean up root directory (move `opencode.json` to `scripts/`).
- [x] Update all import references across the project.
- [x] All 33 tests pass after refactoring.

## P6 - 单用户多终端增强

> 设计目标：单用户在不同 AI 客户端之间统一调用 AI，达成跨端统一记忆、MCP、SKILL。

- [x] **MCP 工具代理**：将 MCP (Model Context Protocol) 工具统一注册到网关，无论客户端使用 OpenAI 还是 Anthropic 协议，都能调用同一套工具。
- [x] **SKILL 系统**：可复用的技能定义和执行框架，跨客户端共享技能配置和执行结果。
- [x] **跨协议多模态转换**：OpenAI `image_url` ↔ Anthropic `image` block 互转，确保图片/文件在所有客户端都能正确传递。
- [x] **跨端会话恢复**：通过固定 session_id 或客户端标识，在不同客户端之间恢复同一会话上下文。
- [x] **统一记忆视图**：所有客户端共享同一记忆空间，在 Claude Code 中聊过的内容 opencode 也能回忆。
