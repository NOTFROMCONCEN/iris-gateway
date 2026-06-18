"""Iris AI Gateway - 人格加载器

负责从 YAML 配置文件加载和管理 AI 人格。
"""

import logging
import os
from typing import Dict, Optional, List

import yaml

from models.schemas import PersonaConfig

logger = logging.getLogger(__name__)


class PersonaLoader:
    """人格加载器"""

    def __init__(self, config_dir: str = "./config/personas"):
        self.config_dir = config_dir
        self._personas: Dict[str, PersonaConfig] = {}
        self._load_all_personas()

    def _load_all_personas(self):
        """加载所有人格配置"""
        if not os.path.exists(self.config_dir):
            logger.warning(f"Persona config directory not found: {self.config_dir}")
            # 使用默认人格
            self._personas["default"] = self._create_default_persona()
            return

        for filename in os.listdir(self.config_dir):
            if filename.endswith(".yaml") or filename.endswith(".yml"):
                filepath = os.path.join(self.config_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                    if data:
                        persona = PersonaConfig(**data)
                        self._personas[persona.id] = persona
                        logger.info(f"Loaded persona: {persona.id} - {persona.name}")
                except Exception as e:
                    logger.error(f"Failed to load persona from {filepath}: {e}")

        # 确保至少有一个默认人格
        if "default" not in self._personas:
            self._personas["default"] = self._create_default_persona()

        logger.info(f"Total personas loaded: {len(self._personas)}")

    def get_persona(self, persona_id: str) -> Optional[PersonaConfig]:
        """获取指定人格配置"""
        return self._personas.get(persona_id)

    def get_default_persona(self) -> PersonaConfig:
        """获取默认人格"""
        return self._personas.get("default", self._create_default_persona())

    def list_personas(self) -> List[Dict[str, str]]:
        """列出所有人格"""
        return [
            {"id": p.id, "name": p.name, "description": p.description}
            for p in self._personas.values()
        ]

    def reload(self):
        """重新加载所有人格"""
        self._personas.clear()
        self._load_all_personas()

    @staticmethod
    def _create_default_persona() -> PersonaConfig:
        """创建默认人格（内联备用）"""
        return PersonaConfig(
            id="default",
            name="Iris",
            description="一个友好、智能的AI助手",
            system_prompt="你是 Iris，一个跨平台统一AI助手。",
            speaking_style="自然、友好、有条理",
        )
