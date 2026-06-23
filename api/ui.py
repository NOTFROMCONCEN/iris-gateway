"""Iris AI Gateway - Web UI routes."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse

from config.settings import settings

router = APIRouter()
WEB_DIR = Path(__file__).resolve().parent.parent / "web" / "admin"


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
