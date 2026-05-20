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

- [ ] Preserve OpenAI parameters such as `logit_bias` and `max_completion_tokens`.
- [ ] Support OpenAI tool call round trips more completely.
- [ ] Support Anthropic `tool_use` and `tool_result` blocks more completely.
- [ ] Make multimodal handling explicit: preserve supported blocks or return clear errors.
- [ ] Add conversion tests for tool and multimodal paths.

## P3 - Configuration And Deployment

- [ ] Move hard-coded model list into configuration.
- [ ] Add client model alias mapping to upstream model ids.
- [ ] Add configurable CORS origins.
- [ ] Warn strongly or fail closed when production runs without `IRIS_API_KEYS`.
- [ ] Run the Docker image as a non-root user.

## P4 - Engineering Quality

- [ ] Add linting, for example `ruff`.
- [ ] Add a CI workflow.
- [ ] Add a mock provider test path that avoids real upstream APIs.
- [ ] Document how `external/ombre-brain` should be cloned or pinned.
- [ ] Reconcile README claims with the currently implemented backend support.
