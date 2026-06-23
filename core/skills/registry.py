"""Lightweight SKILL registry.

Skills are YAML definitions that expose reusable prompt workflows as gateway
tools. This keeps the first implementation deterministic and testable while
leaving room for richer executors later.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml
from pydantic import BaseModel, Field


class SkillDefinition(BaseModel):
    """A reusable skill loaded from YAML."""

    id: str
    name: str
    description: str = ""
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    prompt_template: str

    @property
    def tool_name(self) -> str:
        return f"skill.{self.id}"


class SkillRegistry:
    """Loads and executes local SKILL definitions."""

    def __init__(self, config_dir: str):
        self.config_dir = Path(config_dir)
        self._skills: Dict[str, SkillDefinition] = {}
        self.reload()

    def reload(self) -> None:
        """Reload skill YAML files from disk."""
        self._skills = {}
        if not self.config_dir.exists():
            return

        for path in sorted(self.config_dir.glob("*.yaml")):
            with path.open("r", encoding="utf-8") as fh:
                raw = yaml.safe_load(fh) or {}
            skill = SkillDefinition(**raw)
            self._skills[skill.id] = skill

    def list_skills(self) -> List[SkillDefinition]:
        """Return all loaded skills."""
        return list(self._skills.values())

    def get(self, skill_id: str) -> SkillDefinition | None:
        """Return a skill by id."""
        return self._skills.get(skill_id)

    def tool_definitions(self) -> List[Dict[str, Any]]:
        """Expose each skill as a callable tool."""
        return [
            {
                "name": skill.tool_name,
                "description": skill.description or skill.name,
                "input_schema": skill.input_schema,
                "source": "skill",
                "skill_id": skill.id,
            }
            for skill in self.list_skills()
        ]

    def run(self, skill_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Render a skill prompt with supplied inputs."""
        skill = self.get(skill_id)
        if not skill:
            raise KeyError(f"Unknown skill: {skill_id}")

        rendered = skill.prompt_template
        for key, value in inputs.items():
            rendered = rendered.replace("{{" + key + "}}", str(value))

        return {
            "skill_id": skill.id,
            "name": skill.name,
            "rendered_prompt": rendered,
            "inputs": inputs,
        }

