"""Unified tool registry for Iris Gateway."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

import httpx

from core.skills.registry import SkillRegistry
from memory.manager import MemoryManager


class ToolRegistry:
    """Expose memory, SKILL, and configured MCP tools through one surface."""

    def __init__(
        self,
        skill_registry: SkillRegistry,
        memory_manager: Optional[MemoryManager] = None,
        mcp_tools: Optional[Dict[str, Dict[str, Any]]] = None,
        timeout: float = 30.0,
    ):
        self.skill_registry = skill_registry
        self.memory_manager = memory_manager
        self.mcp_tools = mcp_tools or {}
        self.timeout = timeout

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return native Iris tool definitions."""
        tools = [
            {
                "name": "iris.memory.recall",
                "description": "Recall messages and summaries from a shared Iris session.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "persona_id": {"type": "string", "default": "default"},
                        "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
                    },
                    "required": ["session_id"],
                },
                "source": "memory",
            },
            *self.skill_registry.tool_definitions(),
        ]

        for name, cfg in sorted(self.mcp_tools.items()):
            tools.append({
                "name": name,
                "description": cfg.get("description", "Configured MCP tool"),
                "input_schema": cfg.get("input_schema", {"type": "object"}),
                "source": "mcp",
                "remote_name": cfg.get("remote_name", name),
            })
        return tools

    def list_tools_for_format(self, target_format: str) -> Dict[str, Any]:
        """Render tool definitions for native, OpenAI, or Anthropic clients."""
        tools = self.list_tools()
        if target_format == "openai":
            return {
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": tool["name"],
                            "description": tool.get("description", ""),
                            "parameters": tool.get("input_schema", {"type": "object"}),
                        },
                    }
                    for tool in tools
                ]
            }
        if target_format == "anthropic":
            return {
                "tools": [
                    {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "input_schema": tool.get("input_schema", {"type": "object"}),
                    }
                    for tool in tools
                ]
            }
        return {"tools": tools}

    async def call(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a registered tool."""
        if name == "iris.memory.recall":
            return await self._call_memory_recall(arguments)

        if name.startswith("skill."):
            return self.skill_registry.run(name.removeprefix("skill."), arguments)

        if name in self.mcp_tools:
            return await self._call_mcp_tool(name, arguments)

        raise KeyError(f"Unknown tool: {name}")

    async def _call_memory_recall(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not self.memory_manager:
            return {
                "session_id": arguments.get("session_id", ""),
                "persona_id": arguments.get("persona_id", "default"),
                "messages": [],
                "summaries": [],
                "disabled": True,
            }

        session_id = str(arguments["session_id"])
        persona_id = str(arguments.get("persona_id") or "default")
        limit = int(arguments.get("limit") or 20)
        messages, summaries = await self.memory_manager.inspect_session(
            session_id=session_id,
            persona_id=persona_id,
            limit=limit,
        )
        return {
            "session_id": session_id,
            "persona_id": persona_id,
            "messages": [entry.model_dump(mode="json") for entry in messages],
            "summaries": [summary.model_dump(mode="json") for summary in summaries],
        }

    async def _call_mcp_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        cfg = self.mcp_tools[name]
        url = cfg.get("url")
        if not url:
            raise ValueError(f"MCP tool {name} has no url configured")

        payload = {
            "jsonrpc": "2.0",
            "id": f"iris-{uuid.uuid4().hex[:12]}",
            "method": "tools/call",
            "params": {
                "name": cfg.get("remote_name", name),
                "arguments": arguments,
            },
        }
        headers = cfg.get("headers") or {}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        if data.get("error"):
            raise ValueError(data["error"].get("message", "MCP tool call failed"))
        return {
            "tool": name,
            "source": "mcp",
            "result": data.get("result"),
        }

