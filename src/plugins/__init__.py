"""플러그인 시스템 패키지

동적 플러그인 로딩 및 확장 기능을 제공합니다.
"""

from src.plugins.base import Plugin
from src.plugins.loader import discover_plugins, load_plugin

__all__ = [
    "Plugin",
    "discover_plugins",
    "load_plugin",
]
