"""Unified tool, SKILL, and memory API routes."""

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.skills.registry import SkillRegistry
from core.tools.registry import ToolRegistry

router = APIRouter()


class ToolCallBody(BaseModel):
    """Tool call body."""

    arguments: Dict[str, Any] = Field(default_factory=dict)


class SkillRunBody(BaseModel):
    """Skill run body."""

    inputs: Dict[str, Any] = Field(default_factory=dict)


@router.get("/v1/tools")
async def list_tools(req: Request, format: str = "native"):
    """List unified tools for native, OpenAI, or Anthropic clients."""
    registry: ToolRegistry = req.app.state.tool_registry
    if format not in {"native", "openai", "anthropic"}:
        raise HTTPException(status_code=400, detail="format must be native, openai, or anthropic")
    return JSONResponse(content=registry.list_tools_for_format(format))


@router.post("/v1/tools/{tool_name}/call")
async def call_tool(tool_name: str, body: ToolCallBody, req: Request):
    """Call a unified tool."""
    registry: ToolRegistry = req.app.state.tool_registry
    try:
        result = await registry.call(tool_name, body.arguments)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return JSONResponse(content={"tool": tool_name, "result": result})


@router.get("/v1/skills")
async def list_skills(req: Request):
    """List loaded SKILL definitions."""
    registry: SkillRegistry = req.app.state.skill_registry
    return JSONResponse(content={
        "skills": [skill.model_dump() for skill in registry.list_skills()],
    })


@router.post("/v1/skills/{skill_id}/run")
async def run_skill(skill_id: str, body: SkillRunBody, req: Request):
    """Run a loaded SKILL by id."""
    registry: SkillRegistry = req.app.state.skill_registry
    try:
        result = registry.run(skill_id, body.inputs)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return JSONResponse(content=result)


@router.get("/v1/memory/sessions/{session_id}")
async def inspect_memory_session(
    session_id: str,
    req: Request,
    persona_id: str = "default",
    limit: int = 20,
):
    """Inspect a shared memory session for cross-client recovery."""
    memory_manager = req.app.state.memory_manager
    if not memory_manager:
        return JSONResponse(content={
            "session_id": session_id,
            "persona_id": persona_id,
            "messages": [],
            "summaries": [],
            "disabled": True,
        })

    messages, summaries = await memory_manager.inspect_session(
        session_id=session_id,
        persona_id=persona_id,
        limit=limit,
    )
    return JSONResponse(content={
        "session_id": session_id,
        "persona_id": persona_id,
        "messages": [entry.model_dump(mode="json") for entry in messages],
        "summaries": [summary.model_dump(mode="json") for summary in summaries],
    })
