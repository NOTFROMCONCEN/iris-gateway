const state = {
  config: null,
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
  $("modelInput").value = config.models.default || $("modelInput").value;
  renderRoutes(config);
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
  modelList.innerHTML = '<div class="empty">正在读取模型...</div>';
  try {
    const data = await fetchJson("/v1/models", {headers: authHeaders()});
    renderModels(data);
  } catch (error) {
    modelList.innerHTML = `<div class="empty">读取失败：${error.message}</div>`;
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

function bindEvents() {
  $("apiKeyInput").value = state.apiKey;
  $("refreshButton").addEventListener("click", () => refreshOverview().catch(console.error));
  $("loadModelsButton").addEventListener("click", loadModels);
  $("saveKeyButton").addEventListener("click", saveKey);
  $("sendButton").addEventListener("click", async () => {
    saveKey();
    await sendTest();
  });
}

bindEvents();
refreshOverview().catch((error) => {
  setText("lastUpdated", `刷新失败：${error.message}`);
});
