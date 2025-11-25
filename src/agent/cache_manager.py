"""캐시 관리 모듈.

Gemini Context Cache 관리 및 로컬 디스크 캐시 기능 제공.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    import google.generativeai.caching as caching

    from src.config import AppConfig


class CacheManager:
    """캐시 관리 클래스.

    Gemini Context Cache 생성/조회 및 로컬 디스크 캐시 관리를 담당합니다.
    """

    def __init__(self, config: "AppConfig") -> None:
        """CacheManager 초기화.

        Args:
            config: 애플리케이션 설정
        """
        self.config = config
        self.logger = logging.getLogger("GeminiWorkflow")
        self.cache_hits = 0
        self.cache_misses = 0

    def track_cache_usage(self, cached: bool) -> None:
        """캐시 적중/미스 추적.

        Args:
            cached: True면 캐시 히트, False면 캐시 미스
        """
        if cached:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

    def _local_cache_manifest_path(self) -> Path:
        """로컬 캐시 매니페스트 파일 경로."""
        base = Path(self.config.local_cache_dir)
        if not base.is_absolute():
            base = self.config.base_dir / base
        return base / "context_cache.json"

    def cleanup_expired_cache(self, ttl_minutes: int) -> None:
        """만료된 캐시 엔트리 정리.

        Args:
            ttl_minutes: TTL (분 단위)
        """
        manifest_path = self._local_cache_manifest_path()
        if not manifest_path.exists():
            return
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            self.logger.debug("Cache cleanup skipped (read error): %s", e)
            return

        now = datetime.datetime.now(datetime.timezone.utc)
        updated: dict[str, dict[str, Any]] = {}

        for fingerprint, entry in data.items():
            created_raw = entry.get("created")
            created = (
                datetime.datetime.fromisoformat(created_raw) if created_raw else None
            )
            if created is None:
                continue
            if created.tzinfo is None:
                created = created.replace(tzinfo=datetime.timezone.utc)
            ttl = int(entry.get("ttl_minutes", ttl_minutes) or ttl_minutes)
            if now - created <= datetime.timedelta(minutes=ttl):
                updated[fingerprint] = entry

        if len(updated) == len(data):
            return

        try:
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(updated, f, ensure_ascii=False, indent=2)
        except OSError as e:
            self.logger.debug("Cache cleanup skipped (write error): %s", e)

    def load_local_cache(
        self, fingerprint: str, ttl_minutes: int, caching_module: Any
    ) -> Optional["caching.CachedContent"]:
        """로컬 캐시에서 캐시 로드.

        Args:
            fingerprint: 캐시 핑거프린트
            ttl_minutes: TTL (분 단위)
            caching_module: google.generativeai.caching 모듈

        Returns:
            캐시된 콘텐츠 (없거나 만료 시 None)
        """
        manifest_path = self._local_cache_manifest_path()
        if not manifest_path.exists():
            return None
        self.cleanup_expired_cache(ttl_minutes)
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            entry = data.get(fingerprint)
            if not entry:
                return None
            created_raw = entry.get("created")
            created = (
                datetime.datetime.fromisoformat(created_raw) if created_raw else None
            )
            if created is None:
                return None
            ttl_raw = entry.get("ttl_minutes", ttl_minutes)
            ttl = int(ttl_raw) if ttl_raw is not None else ttl_minutes
            now = datetime.datetime.now(datetime.timezone.utc)
            if created.tzinfo is None:
                created = created.replace(tzinfo=datetime.timezone.utc)
            if now - created > datetime.timedelta(minutes=ttl):
                return None
            cache_name = entry.get("name")
            if cache_name:
                return caching_module.CachedContent.get(name=cache_name)
        except (OSError, json.JSONDecodeError, KeyError, ValueError) as e:
            self.logger.debug("Local cache load skipped: %s", e)
        return None

    def store_local_cache(
        self, fingerprint: str, cache_name: str, ttl_minutes: int
    ) -> None:
        """로컬 캐시에 저장.

        Args:
            fingerprint: 캐시 핑거프린트
            cache_name: 캐시 이름
            ttl_minutes: TTL (분 단위)
        """
        manifest_path = self._local_cache_manifest_path()
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {}
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                data = {}
        data[fingerprint] = {
            "name": cache_name,
            "created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "ttl_minutes": ttl_minutes,
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def compute_fingerprint(content: str) -> str:
        """콘텐츠의 SHA256 핑거프린트 계산.

        Args:
            content: 핑거프린트를 계산할 콘텐츠

        Returns:
            SHA256 해시 문자열
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
