const state = {
  config: null,
  adminSettings: null,
  apiKey: window.localStorage.getItem("iris_admin_api_key") || "",
};

const $ = (id) => document.getElementById(id);

function setText(id, value) {
  const node = $(id);
  if (node) {
    node.textContent = value;
  }
}

function statusClass(value) {
  if (value === true || value === "ok") return "ok";
  if (value === "degraded") return "warn";
  return "bad";
}

function setStatus(id, value) {
  const node = $(id);
  node.textContent = String(value);
  node.className = statusClass(value);
}

function authHeaders() {
  const headers = {"Content-Type": "application/json"};
  if (state.apiKey) {
    headers.Authorization = `Bearer ${state.apiKey}`;
  }
  return headers;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch (error) {
      data = {raw: text};
    }
  }
  if (!response.ok) {
    const message = data?.detail || data?.error?.message || response.statusText;
    throw new Error(`${response.status} ${message}`);
  }
  return data;
}

function renderRoutes(config) {
  const routeList = $("routeList");
  const aliases = config.models.aliases || {};
  const providers = config.models.providers || {};
  const entries = Object.entries(providers);

  if (!entries.length) {
    routeList.innerHTML = '<div class="empty">暂无模型路由配置。</div>';
    return;
  }

  routeList.innerHTML = entries.map(([model, provider]) => {
    const aliasNames = Object.entries(aliases)
      .filter(([, target]) => target === model)
      .map(([alias]) => alias)
      .join(", ");
    const aliasText = aliasNames ? `别名: ${aliasNames}` : "无别名";
    return `
      <div class="route-item">
        <div>
          <strong>${model}</strong>
          <small>${aliasText}</small>
        </div>
        <span class="pill">${provider}</span>
      </div>
    `;
  }).join("");
}

function renderConfig(config) {
  state.config = config;
  setText("authStatus", config.auth_required ? "启用" : "未启用");
  setText("memoryBackend", config.memory.backend);
  setText(
    "memoryMeta",
    `窗口 ${config.memory.max_short_term} / 摘要阈值 ${config.memory.summary_threshold}`,
  );
  setText("openaiConfigured", config.providers.openai_configured ? "已配置" : "未配置");
  setText("anthropicConfigured", config.providers.anthropic_configured ? "已配置" : "未配置");
  setText("modelDiscovery", config.providers.model_discovery ? "启用" : "关闭");
  setText("environment", config.environment);
  setText("corsOrigins", config.cors_origins.join(", ") || "未配置");
  setText("defaultModel", config.models.default);
  setText("toolCount", String(config.p6.tools));
  setText("skillCount", String(config.p6.skills));
  setText("mcpToolCount", String(config.p6.mcp_tools));
  setText("memoryView", config.p6.memory_view ? "启用" : "关闭");
  $("modelInput").value = config.models.default || $("modelInput").value;
  hydrateCompatDefaults(config);
  renderRoutes(config);
}

function gatewayBaseUrl() {
  return window.location.origin;
}

function hydrateCompatDefaults(config) {
  const baseInput = $("compatBaseUrl");
  if (!baseInput.value) {
    baseInput.value = gatewayBaseUrl();
  }
  if (!$("compatApiKey").value && state.apiKey) {
    $("compatApiKey").value = state.apiKey;
  }
  const openAIModel = Object.entries(config.models.providers || {})
    .find(([, provider]) => provider === "openai")?.[0];
  if (openAIModel) {
    $("compatOpenAIModel").value = openAIModel;
  }

  const anthropicModel = Object.entries(config.models.providers || {})
    .find(([, provider]) => provider === "anthropic")?.[0];
  if (anthropicModel) {
    $("compatAnthropicModel").value = anthropicModel;
  }
  renderCompatConfig();
}

function configInputs() {
  const baseUrl = $("compatBaseUrl").value.trim().replace(/\/+$/, "") || gatewayBaseUrl();
  const apiKey = $("compatApiKey").value.trim() || "iris-key-1";
  return {
    type: $("compatClient").value,
    baseUrl,
    openaiBaseUrl: `${baseUrl}/v1`,
    apiKey,
    openaiModel: $("compatOpenAIModel").value.trim() || "kimi-k2",
    anthropicModel: $("compatAnthropicModel").value.trim() || "kimi-for-coding",
    sessionId: $("compatSessionId").value.trim() || "iris-shared",
    personaId: $("compatPersonaId").value.trim() || "default",
  };
}

function renderCompatConfig() {
  const cfg = configInputs();
  const templates = {
    opencode: {
      $schema: "https://opencode.ai/config.json",
      provider: {
        "iris-gateway": {
          npm: "@ai-sdk/openai-compatible",
          name: "Iris Gateway",
          options: {
            baseURL: cfg.openaiBaseUrl,
            apiKey: cfg.apiKey,
          },
          models: {
            [cfg.openaiModel]: {name: cfg.openaiModel},
            [cfg.anthropicModel]: {name: cfg.anthropicModel},
          },
        },
      },
    },
    cline: {
      "cline.apiProvider": "openai-compatible",
      "cline.openAiCompatibleBaseUrl": cfg.openaiBaseUrl,
      "cline.openAiCompatibleApiKey": cfg.apiKey,
      "cline.openAiCompatibleModelId": cfg.openaiModel,
    },
    continue: {
      models: [
        {
          title: "Iris Gateway",
          provider: "openai",
          model: cfg.openaiModel,
          apiBase: cfg.openaiBaseUrl,
          apiKey: cfg.apiKey,
        },
      ],
    },
    request: {
      model: cfg.openaiModel,
      session_id: cfg.sessionId,
      persona_id: cfg.personaId,
      messages: [
        {
          role: "user",
          content: "继续这个跨端会话。",
        },
      ],
    },
  };

  if (cfg.type === "claude") {
    $("compatOutput").textContent = [
      `$env:ANTHROPIC_BASE_URL = "${cfg.baseUrl}"`,
      `$env:ANTHROPIC_API_KEY = "${cfg.apiKey}"`,
      "claude",
    ].join("\n");
    return;
  }

  if (cfg.type === "env") {
    $("compatOutput").textContent = [
      `IRIS_API_KEYS=${cfg.apiKey}`,
      `OPENAI_BASE_URL=${cfg.openaiBaseUrl}`,
      `ANTHROPIC_BASE_URL=${cfg.baseUrl}`,
      `MODEL_ALIASES={"coding":"${cfg.anthropicModel}","chat":"${cfg.openaiModel}"}`,
      `MODEL_PROVIDERS={"${cfg.openaiModel}":"openai","${cfg.anthropicModel}":"anthropic"}`,
    ].join("\n");
    return;
  }

  $("compatOutput").textContent = JSON.stringify(templates[cfg.type], null, 2);
}

function renderModels(data) {
  const models = data?.data || [];
  const modelList = $("modelList");
  if (!models.length) {
    modelList.innerHTML = '<div class="empty">没有返回模型。</div>';
    return;
  }

  modelList.innerHTML = models.map((model) => `
    <div class="model-item">
      <div>
        <strong>${model.id}</strong>
        <small>${model.owned_by || model.display_name || "unknown"}</small>
      </div>
      <button type="button" data-model="${model.id}">选用</button>
    </div>
  `).join("");

  modelList.querySelectorAll("button[data-model]").forEach((button) => {
    button.addEventListener("click", () => {
      $("modelInput").value = button.dataset.model;
    });
  });
}

function renderTools(data) {
  const tools = data?.tools || [];
  const toolList = $("toolList");
  if (!tools.length) {
    toolList.innerHTML = '<div class="empty">没有返回工具。</div>';
    return;
  }

  toolList.innerHTML = tools.map((tool) => `
    <div class="model-item">
      <div>
        <strong>${tool.name}</strong>
        <small>${tool.description || "无描述"}</small>
      </div>
      <span class="pill">${tool.source || "tool"}</span>
    </div>
  `).join("");
}

function formatJsonField(value) {
  if (!value) return "";
  try {
    return JSON.stringify(JSON.parse(value), null, 2);
  } catch (error) {
    return value;
  }
}

function configFields() {
  return Array.from(document.querySelectorAll("[data-config-key]"));
}

function renderAdminSettings(data) {
  state.adminSettings = data;
  configFields().forEach((field) => {
    const key = field.dataset.configKey;
    const item = data.values?.[key];
    if (!item) return;

    field.classList.remove("invalid-input");
    if (item.sensitive) {
      field.value = "";
      field.placeholder = item.configured ? "已配置，留空保持不变" : "未配置";
      return;
    }

    field.value = field.dataset.json !== undefined
      ? formatJsonField(item.value)
      : item.value;
  });
  setText(
    "settingsStatus",
    `${data.exists ? ".env 已加载" : ".env 不存在，保存时创建"}；保存后需要重启服务生效`,
  );
}

function validateJsonFields() {
  let valid = true;
  configFields().forEach((field) => {
    field.classList.remove("invalid-input");
    if (field.dataset.json === undefined || !field.value.trim()) return;
    try {
      JSON.parse(field.value);
    } catch (error) {
      field.classList.add("invalid-input");
      valid = false;
    }
  });
  return valid;
}

async function loadAdminSettings() {
  saveKey();
  if (!state.apiKey) {
    setText("settingsStatus", "请先在请求测试区域填写并保存 API Key。");
    return;
  }
  setText("settingsStatus", "正在读取配置...");
  try {
    const data = await fetchJson("/admin/api/settings", {headers: authHeaders()});
    renderAdminSettings(data);
  } catch (error) {
    setText("settingsStatus", `读取失败：${error.message}`);
  }
}

function collectAdminSettings() {
  const values = {};
  configFields().forEach((field) => {
    const key = field.dataset.configKey;
    const item = state.adminSettings?.values?.[key];
    const value = field.value.trim();
    if (item?.sensitive && value === "") {
      return;
    }
    values[key] = value;
  });
  return values;
}

async function saveAdminSettings() {
  saveKey();
  if (!state.apiKey) {
    setText("settingsStatus", "请先在请求测试区域填写并保存 API Key。");
    return;
  }
  if (!validateJsonFields()) {
    setText("settingsStatus", "JSON 配置格式有误，请修正高亮字段。");
    return;
  }

  setText("settingsStatus", "正在保存配置...");
  try {
    const data = await fetchJson("/admin/api/settings", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({values: collectAdminSettings()}),
    });
    renderAdminSettings(data.settings);
    setText(
      "settingsStatus",
      data.restart_required
        ? `已保存 ${data.updated.length} 项；重启服务后生效`
        : "没有需要保存的配置",
    );
  } catch (error) {
    setText("settingsStatus", `保存失败：${error.message}`);
  }
}

async function refreshOverview() {
  const [health, ready, config] = await Promise.all([
    fetchJson("/health"),
    fetchJson("/ready"),
    fetchJson("/admin/api/config"),
  ]);

  setStatus("healthStatus", health.status);
  setText("healthMeta", `${Math.round(health.uptime)}s uptime`);
  setStatus("readyStatus", ready.status);
  const providerText = Object.entries(ready.providers || {})
    .map(([name, value]) => `${name}:${value ? "ok" : "fail"}`)
    .join(" / ");
  setText("readyMeta", providerText || "未配置 Provider");
  renderConfig(config);
  setText("lastUpdated", new Date().toLocaleString());
}

async function loadModels() {
  const modelList = $("modelList");
  if (!state.apiKey) {
    modelList.innerHTML = '<div class="empty">请先填写并保存 API Key。</div>';
    return;
  }
  modelList.innerHTML = '<div class="empty">正在读取模型...</div>';
  try {
    const data = await fetchJson("/v1/models", {headers: authHeaders()});
    renderModels(data);
  } catch (error) {
    modelList.innerHTML = `<div class="empty">读取失败：${error.message}</div>`;
  }
}

async function loadTools() {
  const toolList = $("toolList");
  if (!state.apiKey) {
    toolList.innerHTML = '<div class="empty">请先填写并保存 API Key。</div>';
    return;
  }
  toolList.innerHTML = '<div class="empty">正在读取工具...</div>';
  try {
    const data = await fetchJson("/v1/tools", {headers: authHeaders()});
    renderTools(data);
  } catch (error) {
    toolList.innerHTML = `<div class="empty">读取失败：${error.message}</div>`;
  }
}

async function sendTest() {
  const box = $("responseBox");
  const body = {
    model: $("modelInput").value.trim(),
    messages: [
      {
        role: "user",
        content: $("messageInput").value.trim(),
      },
    ],
  };

  if (!body.model || !body.messages[0].content) {
    box.textContent = "请填写模型和消息。";
    return;
  }

  box.textContent = "请求中...";
  try {
    const data = await fetchJson("/v1/chat/completions", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(body),
    });
    box.textContent = JSON.stringify(data, null, 2);
  } catch (error) {
    box.textContent = `请求失败：${error.message}`;
  }
}

function saveKey() {
  state.apiKey = $("apiKeyInput").value.trim();
  if (state.apiKey) {
    window.localStorage.setItem("iris_admin_api_key", state.apiKey);
  } else {
    window.localStorage.removeItem("iris_admin_api_key");
  }
}

function useSavedKeyForCompat() {
  $("compatApiKey").value = state.apiKey || $("apiKeyInput").value.trim();
  renderCompatConfig();
}

function bindEvents() {
  $("apiKeyInput").value = state.apiKey;
  $("refreshButton").addEventListener("click", () => refreshOverview().catch(console.error));
  $("loadModelsButton").addEventListener("click", loadModels);
  $("loadToolsButton").addEventListener("click", loadTools);
  $("loadSettingsButton").addEventListener("click", loadAdminSettings);
  $("saveSettingsButton").addEventListener("click", saveAdminSettings);
  $("saveKeyButton").addEventListener("click", saveKey);
  $("useSavedKeyButton").addEventListener("click", useSavedKeyForCompat);
  $("generateConfigButton").addEventListener("click", renderCompatConfig);
  $("compatClient").addEventListener("change", renderCompatConfig);
  $("sendButton").addEventListener("click", async () => {
    saveKey();
    await sendTest();
  });
}

bindEvents();
refreshOverview().catch((error) => {
  setText("lastUpdated", `刷新失败：${error.message}`);
});
