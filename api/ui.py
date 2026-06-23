"""Iris AI Gateway - Web UI routes."""

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from config.settings import settings

router = APIRouter()
WEB_DIR = Path(__file__).resolve().parent.parent / "web" / "admin"
PROJECT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_DIR / ".env"

SENSITIVE_KEYS = {
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "IRIS_API_KEYS",
    "OMBRE_MCP_TOKEN",
    "OMBRE_DEHYDRATION_API_KEY",
}
JSON_KEYS = {"MODEL_ALIASES", "MODEL_PROVIDERS", "AVAILABLE_MODELS", "MCP_TOOLS"}
ADMIN_CONFIG_KEYS = [
    "IRIS_HOST",
    "IRIS_PORT",
    "IRIS_DEBUG",
    "IRIS_LOG_LEVEL",
    "IRIS_ENVIRONMENT",
    "CORS_ORIGINS",
    "IRIS_API_KEYS",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_ORGANIZATION",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_HEADER",
    "UPSTREAM_TIMEOUT",
    "UPSTREAM_MAX_RETRIES",
    "MEMORY_BACKEND",
    "MEMORY_DB_PATH",
    "MEMORY_MAX_SHORT_TERM",
    "MEMORY_SUMMARY_THRESHOLD",
    "PERSONA_CONFIG_DIR",
    "SKILLS_CONFIG_DIR",
    "MODEL_ALIASES",
    "MODEL_PROVIDERS",
    "AVAILABLE_MODELS",
    "MCP_TOOLS",
]


class AdminSettingsUpdate(BaseModel):
    """Admin settings write request."""

    values: Dict[str, str] = Field(default_factory=dict)


def _env_path(req: Request) -> Path:
    """Allow tests to override the config file path."""
    return Path(getattr(req.app.state, "admin_env_path", ENV_PATH))


def _parse_env_file(path: Path) -> Dict[str, str]:
    """Parse a simple dotenv file without expanding variables."""
    values: Dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _format_env_value(value: str) -> str:
    """Format one dotenv value."""
    if "\n" in value:
        value = value.replace("\n", "\\n")
    if value == "" or any(ch.isspace() for ch in value):
        return json.dumps(value, ensure_ascii=False)
    return value


def _write_env_values(path: Path, updates: Dict[str, str]) -> None:
    """Update or append selected keys while preserving unrelated lines."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    seen = set()
    output = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            output.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in updates:
            output.append(f"{key}={_format_env_value(updates[key])}")
            seen.add(key)
        else:
            output.append(line)

    missing = [key for key in ADMIN_CONFIG_KEYS if key in updates and key not in seen]
    if missing and output and output[-1].strip():
        output.append("")
    for key in missing:
        output.append(f"{key}={_format_env_value(updates[key])}")

    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def _validate_admin_updates(values: Dict[str, str]) -> Dict[str, str]:
    """Validate admin config updates and drop empty sensitive fields."""
    allowed = set(ADMIN_CONFIG_KEYS)
    updates: Dict[str, str] = {}
    for key, value in values.items():
        if key not in allowed:
            raise HTTPException(status_code=400, detail=f"Unsupported config key: {key}")
        if key in SENSITIVE_KEYS and value == "":
            continue
        if key in JSON_KEYS and value.strip():
            try:
                json.loads(value)
            except json.JSONDecodeError as exc:
                raise HTTPException(status_code=400, detail=f"{key} is not valid JSON") from exc
        updates[key] = value
    return updates


def _admin_settings_payload(path: Path) -> Dict[str, Any]:
    """Build a safe settings payload for the admin UI."""
    values = _parse_env_file(path)
    payload_values = {}
    for key in ADMIN_CONFIG_KEYS:
        value = values.get(key, "")
        payload_values[key] = {
            "value": "" if key in SENSITIVE_KEYS else value,
            "configured": bool(value),
            "sensitive": key in SENSITIVE_KEYS,
        }
    return {
        "env_path": str(path),
        "exists": path.exists(),
        "restart_required": True,
        "values": payload_values,
        "json_keys": sorted(JSON_KEYS),
    }


@router.get("/admin", include_in_schema=False)
async def admin_index():
    """Serve the Web UI shell."""
    return FileResponse(WEB_DIR / "index.html")


@router.get("/admin/{asset_name}", include_in_schema=False)
async def admin_asset(asset_name: str):
    """Serve simple static assets for the Web UI."""
    allowed_assets = {
        "styles.css": "text/css",
        "app.js": "application/javascript",
    }
    if asset_name not in allowed_assets:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return FileResponse(WEB_DIR / asset_name, media_type=allowed_assets[asset_name])


@router.get("/admin/api/config", include_in_schema=False)
async def admin_config(req: Request):
    """Return sanitized runtime configuration for the Web UI."""
    skill_registry = getattr(req.app.state, "skill_registry", None)
    tool_registry = getattr(req.app.state, "tool_registry", None)
    skills = skill_registry.list_skills() if skill_registry else []
    tools = tool_registry.list_tools() if tool_registry else []
    return JSONResponse(content={
        "version": "0.1.0",
        "environment": settings.iris_environment,
        "auth_required": bool(settings.api_key_list),
        "cors_origins": settings.cors_origin_list,
        "memory": {
            "backend": settings.memory_backend,
            "max_short_term": settings.memory_max_short_term,
            "summary_threshold": settings.memory_summary_threshold,
        },
        "providers": {
            "openai_configured": bool(settings.openai_api_key),
            "anthropic_configured": bool(settings.anthropic_api_key),
            "model_discovery": settings.provider_model_discovery,
        },
        "models": {
            "available": getattr(req.app.state, "available_models", settings.available_models),
            "aliases": settings.model_aliases,
            "providers": settings.model_providers,
            "default": settings.default_model,
        },
        "p6": {
            "skills": len(skills),
            "tools": len(tools),
            "mcp_tools": len(settings.mcp_tools),
            "session_recovery": True,
            "memory_view": bool(getattr(req.app.state, "memory_manager", None)),
        },
        "endpoints": {
            "health": "/health",
            "ready": "/ready",
            "models": "/v1/models",
            "chat": "/v1/chat/completions",
            "tools": "/v1/tools",
            "skills": "/v1/skills",
            "memory_session": "/v1/memory/sessions/{session_id}",
        },
    })


@router.get("/admin/api/settings", include_in_schema=False)
async def admin_settings(req: Request):
    """Return editable admin settings without exposing secret values."""
    return JSONResponse(content=_admin_settings_payload(_env_path(req)))


@router.post("/admin/api/settings", include_in_schema=False)
async def update_admin_settings(body: AdminSettingsUpdate, req: Request):
    """Persist selected settings to .env. Restart is required to apply them."""
    path = _env_path(req)
    updates = _validate_admin_updates(body.values)
    if not updates:
        return JSONResponse(content={
            "updated": [],
            "restart_required": False,
            "settings": _admin_settings_payload(path),
        })

    _write_env_values(path, updates)
    return JSONResponse(content={
        "updated": sorted(updates.keys()),
        "restart_required": True,
        "settings": _admin_settings_payload(path),
    })
