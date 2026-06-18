"""Iris AI Gateway - 核心模块

提供向后兼容的导入路径。
"""

# 向后兼容：允许 from core.persona_loader import PersonaLoader 等旧路径
from core.persona.loader import PersonaLoader
from core.persona.injector import PersonaInjector
from core.perception.analyzer import PerceptionAnalyzer

__all__ = ["PersonaLoader", "PersonaInjector", "PerceptionAnalyzer"]
