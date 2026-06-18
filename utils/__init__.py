"""Iris AI Gateway - 工具模块

提供向后兼容的导入路径。
"""

# 向后兼容：允许 from utils.exceptions import ... 和 from utils.upstream_errors import ...
from models.exceptions import *
from providers.upstream_errors import build_upstream_http_exception
