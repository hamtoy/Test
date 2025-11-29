"""플러그인 로더

플러그인을 자동으로 발견하고 로드하는 기능을 제공합니다.
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.plugins.base import Plugin

logger = logging.getLogger(__name__)


def load_plugin(file_path: Path) -> list[type["Plugin"]]:
    """단일 플러그인 파일에서 Plugin 클래스들을 로드

    Args:
        file_path: 플러그인 파일 경로

    Returns:
        발견된 Plugin 서브클래스 리스트

    Note:
        모듈 이름으로 file_path.stem을 사용합니다.
        다른 디렉토리에서 같은 이름의 플러그인 파일을 로드할 경우
        이름 충돌이 발생할 수 있습니다.
    """
    from src.plugins.base import Plugin

    # 고유한 모듈 이름 생성 (경로 기반)
    module_name = f"plugin_{file_path.stem}_{hash(str(file_path.absolute())) % 10000}"

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        logger.warning("Failed to load plugin spec: %s", file_path)
        return []

    module = importlib.util.module_from_spec(spec)

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        logger.error("Failed to execute plugin module %s: %s", file_path, e)
        return []

    plugins: list[type[Plugin]] = []
    for item_name in dir(module):
        obj = getattr(module, item_name)
        if isinstance(obj, type) and issubclass(obj, Plugin) and obj is not Plugin:
            plugins.append(obj)

    return plugins


def discover_plugins(plugin_dir: Path | None = None) -> list["Plugin"]:
    """플러그인 자동 발견 및 로드

    지정된 디렉토리에서 모든 플러그인을 찾아 인스턴스화합니다.

    Args:
        plugin_dir: 플러그인 디렉토리 경로 (기본: plugins/)

    Returns:
        로드된 플러그인 인스턴스 리스트
    """
    if plugin_dir is None:
        plugin_dir = Path("plugins")

    if not plugin_dir.exists():
        logger.info("Plugin directory does not exist: %s", plugin_dir)
        return []

    plugins: list[Plugin] = []

    for file_path in plugin_dir.glob("*.py"):
        if file_path.stem.startswith("_"):
            continue

        plugin_classes = load_plugin(file_path)
        for plugin_class in plugin_classes:
            try:
                instance = plugin_class()
                plugins.append(instance)
                logger.info(
                    "Loaded plugin: %s v%s",
                    instance.name,
                    instance.version,
                )
            except Exception as e:
                logger.error(
                    "Failed to instantiate plugin %s: %s",
                    plugin_class.__name__,
                    e,
                )

    return plugins


__all__ = ["discover_plugins", "load_plugin"]
