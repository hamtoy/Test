"""Cache management module.

Provides local context cache handling with optional TTL and backward compatible
APIs used by older code paths.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from src.config import AppConfig
from src.config.constants import CacheConfig
from src.core.type_aliases import CachedContentProtocol, CachingModuleProtocol


class CacheManager:
    """Cache manager handling local cache files.

    The primary API uses an :class:`AppConfig` instance for configuration.
    Compatibility wrappers are provided for legacy signatures.
    """

    def __init__(self, config: AppConfig, *, min_tokens: int | None = None) -> None:
        """Initialize the cache manager.

        Args:
            config: Application configuration instance.
            min_tokens: Minimum token count for caching eligibility.
        """
        self.config = config
        self.logger = logging.getLogger("GeminiWorkflow")
        self.cache_hits = 0
        self.cache_misses = 0
        self.min_tokens = (
            min_tokens
            if min_tokens is not None
            else getattr(config, "cache_min_tokens", CacheConfig.MIN_TOKENS_FOR_CACHING)
        )

    # ---------------------------------------------------------------------
    # Caching decision logic
    # ---------------------------------------------------------------------
    def should_cache(self, prompt_tokens: int) -> bool:
        """캐싱 활성화 여부 결정.

        Args:
            prompt_tokens: 프롬프트의 토큰 수

        Returns:
            True: 캐싱 사용 (2048+ 토큰)
            False: 일반 API 사용 (2048 미만)
        """
        if prompt_tokens < self.min_tokens:
            self.logger.debug(
                "캐싱 건너뜀: %d 토큰 (최소 %d 필요, Gemini API 제약)",
                prompt_tokens,
                self.min_tokens,
            )
            return False

        savings_estimate = self._estimate_savings(prompt_tokens)
        self.logger.debug(
            "캐싱 활성화: %d 토큰 (예상 절감: ~%d%%)",
            prompt_tokens,
            savings_estimate,
        )
        return True

    def _estimate_savings(self, tokens: int) -> int:
        """대략적인 비용 절감률 추정."""
        if tokens < 5000:
            return 50
        if tokens < 20000:
            return 70
        return 85

    # ---------------------------------------------------------------------
    # Compatibility layer for older code that used ``track_cache_usage``
    # ---------------------------------------------------------------------
    def track_cache_usage(self, cached: bool) -> None:
        """Increment hit/miss counters.

        Args:
            cached: ``True`` if a cache hit occurred, ``False`` otherwise.
        """
        if cached:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

    # ---------------------------------------------------------------------
    # New API – explicit TTL handling
    # ---------------------------------------------------------------------
    def _local_cache_manifest_path(self) -> Path:
        """Return the path to the local cache manifest JSON file.

        The path is resolved relative to ``config.base_dir`` if ``local_cache_dir``
        is not absolute.
        """
        base = Path(self.config.local_cache_dir)
        if not base.is_absolute():
            base = self.config.base_dir / base
        return base / "context_cache.json"

    def cleanup_expired_cache(self, ttl_minutes: int) -> None:
        """Remove expired entries from the cache manifest.

        Args:
            ttl_minutes: Time‑to‑live in minutes for cache entries.
        """
        manifest_path = self._local_cache_manifest_path()
        if not manifest_path.exists():
            return
        try:
            with open(manifest_path, encoding="utf-8") as f:
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
        self,
        fingerprint: str,
        ttl_minutes: int,
        caching_module: CachingModuleProtocol,
    ) -> CachedContentProtocol | None:
        """Load a cached entry if it exists and is not expired.

        Args:
            fingerprint: The fingerprint of the content.
            ttl_minutes: TTL for the entry.
            caching_module: The ``google.generativeai.caching`` module.

        Returns:
            The cached content if found, None otherwise.
        """
        manifest_path = self._local_cache_manifest_path()
        if not manifest_path.exists():
            return None
        self.cleanup_expired_cache(ttl_minutes)
        try:
            with open(manifest_path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            self.logger.debug("Local cache load skipped: %s", e)
            return None
        entry = data.get(fingerprint)
        if not entry:
            return None
        cache_name = entry.get("name")
        if cache_name:
            return caching_module.CachedContent.get(name=cache_name)
        return None

    def store_local_cache(
        self,
        fingerprint: str,
        cache_name: str,
        ttl_minutes: int,
    ) -> None:
        """Persist a cache entry to the manifest.

        Args:
            fingerprint: The fingerprint of the content.
            cache_name: Name used by the caching module.
            ttl_minutes: TTL for the entry.
        """
        manifest_path = self._local_cache_manifest_path()
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {}
        if manifest_path.exists():
            try:
                with open(manifest_path, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                data = {}
        data[fingerprint] = {
            "name": cache_name,
            "created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "ttl_minutes": ttl_minutes,
        }
        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            self.logger.debug("Local cache manifest write skipped: %s", e)

    # ---------------------------------------------------------------------
    # Backward‑compatible wrappers (old method names)
    # ---------------------------------------------------------------------
    def cleanup_expired(self, ttl_minutes: int | None = None) -> None:
        """Legacy wrapper that forwards to :meth:`cleanup_expired_cache`."""
        self.cleanup_expired_cache(ttl_minutes or self.config.cache_ttl_minutes)

    def load_cached(
        self,
        fingerprint: str,
        caching_module: CachingModuleProtocol,
    ) -> CachedContentProtocol | None:
        """Legacy wrapper for loading cache without explicit TTL.

        Args:
            fingerprint: The fingerprint of the content.
            caching_module: The caching module to use.

        Returns:
            The cached content if found, None otherwise.
        """
        return self.load_local_cache(
            fingerprint,
            self.config.cache_ttl_minutes,
            caching_module,
        )

    def store_cache(self, fingerprint: str, cache_name: str, ttl_minutes: int) -> None:
        """Legacy wrapper for storing cache."""
        self.store_local_cache(fingerprint, cache_name, ttl_minutes)

    @staticmethod
    def compute_fingerprint(content: str) -> str:
        """Compute SHA‑256 fingerprint of *content*."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
