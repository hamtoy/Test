"""Context Cache 관리 모듈."""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    import google.generativeai.caching as caching


class CacheManager:
    """로컬 및 원격 Context Cache 관리."""

    def __init__(self, cache_dir: Path, ttl_minutes: int = 60):
        self.cache_dir = cache_dir
        self.ttl_minutes = ttl_minutes
        self._manifest_path = self._resolve_manifest_path(cache_dir)
        self.logger = logging.getLogger(__name__)
        self.cache_hits = 0
        self.cache_misses = 0

    def _resolve_manifest_path(self, cache_dir: Path) -> Path:
        # Assuming cache_dir is already absolute or relative to CWD correctly handled by caller
        # But original code handled base_dir relative logic.
        # Here we assume cache_dir passed is the final resolved path.
        return cache_dir / "context_cache.json"

    def get_fingerprint(self, content: str) -> str:
        """컨텐츠 해시 기반 fingerprint 생성."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def track_usage(self, hit: bool) -> None:
        if hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

    def _cleanup_expired(self) -> None:
        """Remove expired cache entries from the local manifest (best-effort)."""
        if not self._manifest_path.exists():
            return
        try:
            with open(self._manifest_path, "r", encoding="utf-8") as f:
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

            ttl = int(entry.get("ttl_minutes", self.ttl_minutes) or self.ttl_minutes)
            if now - created <= datetime.timedelta(minutes=ttl):
                updated[fingerprint] = entry

        if len(updated) == len(data):
            return

        try:
            self._manifest_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._manifest_path, "w", encoding="utf-8") as f:
                json.dump(updated, f, ensure_ascii=False, indent=2)
        except OSError as e:
            self.logger.debug("Cache cleanup skipped (write error): %s", e)

    def cleanup_expired(self, ttl_minutes: Optional[int] = None) -> None:
        """Public method to clean up expired cache entries."""
        # ttl_minutes parameter is kept for backward compatibility
        # but the internal _cleanup_expired uses self.ttl_minutes
        self._cleanup_expired()

    def load_cached(
        self, fingerprint: str, caching_module: Any
    ) -> Optional["caching.CachedContent"]:
        """로컬 캐시에서 유효한 캐시 로드."""
        if not self._manifest_path.exists():
            return None

        self._cleanup_expired()

        try:
            with open(self._manifest_path, "r", encoding="utf-8") as f:
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

            ttl = int(entry.get("ttl_minutes", self.ttl_minutes) or self.ttl_minutes)
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

    def store_cache(self, fingerprint: str, cache_name: str, ttl_minutes: int) -> None:
        """캐시 정보를 로컬 매니페스트에 저장."""
        self._manifest_path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if self._manifest_path.exists():
            try:
                with open(self._manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                data = {}

        data[fingerprint] = {
            "name": cache_name,
            "created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "ttl_minutes": ttl_minutes,
        }

        try:
            with open(self._manifest_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            self.logger.debug("Local cache manifest write skipped: %s", e)
