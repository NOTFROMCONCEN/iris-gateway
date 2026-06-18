"""Iris AI Gateway - 人格注入器

在请求链路中将人格配置注入为 System Prompt。
"""

import logging
from typing import List, Dict

from models.schemas import Message, MessageRole, PersonaConfig

logger = logging.getLogger(__name__)


class PersonaInjector:
    """人格注入器"""

    def inject(self, messages: List[Message], persona: PersonaConfig) -> List[Message]:
        """
        将人格配置注入消息列表中。

        策略：
        1. 在消息列表开头插入人格的 system_prompt
        2. 动态渲染 personality_traits 为 traits 描述
        3. 应用 speaking_style
        4. 插入 response_guidelines
        """
        # 构建人格增强的 system prompt
        system_prompt = self._build_system_prompt(persona)

        # 检查是否已有 system 消息
        has_system = any(m.role == MessageRole.SYSTEM for m in messages)

        new_messages = list(messages)

        if has_system:
            # 如果有 system 消息，在第一条 system 消息后追加人格配置
            for i, msg in enumerate(new_messages):
                if msg.role == MessageRole.SYSTEM:
                    new_messages[i] = Message(
                        role=MessageRole.SYSTEM,
                        content=system_prompt + "\n\n" + msg.content,
                        metadata=msg.metadata,
                    )
                    break
        else:
            # 在消息列表开头插入人格 system prompt
            new_messages.insert(0, Message(
                role=MessageRole.SYSTEM,
                content=system_prompt,
            ))

        logger.debug(f"Injected persona [{persona.name}] into messages")
        return new_messages

    def _build_system_prompt(self, persona: PersonaConfig) -> str:
        """根据人格配置构建 system prompt"""
        parts = []

        # 核心身份描述
        if persona.system_prompt:
            parts.append(persona.system_prompt.strip())

        # 性格特征渲染
        if persona.personality_traits:
            traits_lines = []
            for trait, value in persona.personality_traits.items():
                level = self._trait_level(value)
                traits_lines.append(f"- {trait}: {level} (得分 {value:.1f}/1.0)")
            if traits_lines:
                parts.append("\n你的性格特征：")
                parts.extend(traits_lines)

        # 说话风格
        if persona.speaking_style:
            parts.append(f"\n你的说话风格：{persona.speaking_style}")

        # 响应准则
        if persona.response_guidelines:
            parts.append("\n你的响应准则：")
            for guideline in persona.response_guidelines:
                parts.append(f"- {guideline}")

        # 知识领域
        if persona.knowledge_domains:
            domains = ", ".join(persona.knowledge_domains)
            parts.append(f"\n你擅长的领域：{domains}")

        # 禁止话题
        if persona.forbidden_topics:
            topics = ", ".join(persona.forbidden_topics)
            parts.append(f"\n你应避免的话题：{topics}")

        return "\n".join(parts)

    @staticmethod
    def _trait_level(value: float) -> str:
        """将特征值映射为描述词"""
        if value >= 0.9:
            return "极强"
        elif value >= 0.7:
            return "较强"
        elif value >= 0.5:
            return "中等"
        elif value >= 0.3:
            return "较弱"
        else:
            return "极弱"
