"""Feature Flag 시스템 - Safe feature rollout and A/B testing."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class FeatureFlags:
    """Feature Flag 관리.

    Manage feature flags for safe feature rollout and A/B testing.
    """

    def __init__(self, config_file: Path | None = None) -> None:
        """Initialize feature flags.

        Args:
            config_file: Path to the feature flags JSON config file
        """
        self.config_file = config_file or Path("config/feature_flags.json")
        self.flags = self._load_flags()

    def _load_flags(self) -> dict[str, Any]:
        """설정 파일 로드.

        Load flags from the configuration file.

        Returns:
            Dictionary of flag configurations
        """
        if not self.config_file.exists():
            return {}

        try:
            content = self.config_file.read_text(encoding="utf-8")
            return dict(json.loads(content))
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to load feature flags: {e}")
            return {}

    def save_flags(self) -> bool:
        """Save flags to the configuration file.

        Returns:
            True if save was successful, False otherwise
        """
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            self.config_file.write_text(
                json.dumps(self.flags, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save feature flags: {e}")
            return False

    def is_enabled(
        self,
        flag_name: str,
        user_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """Feature 활성화 여부 확인.

        Check if a feature flag is enabled for the given user and context.

        Args:
            flag_name: Name of the feature flag
            user_id: Optional user identifier for rollout targeting
            context: Optional context dictionary for rule evaluation

        Returns:
            True if the feature is enabled, False otherwise
        """
        flag = self.flags.get(flag_name)
        if not flag:
            return False  # 정의되지 않은 플래그는 비활성화

        # 1. 전역 스위치
        if not flag.get("enabled", False):
            return False

        # 2. 환경 제한
        allowed_envs = flag.get(
            "environments", ["development", "staging", "production"]
        )
        current_env = os.getenv("ENVIRONMENT", "development")
        if current_env not in allowed_envs:
            return False

        # 3. 화이트리스트 (특정 사용자만) - whitelist가 비어있으면 무시
        whitelist = flag.get("whitelist", [])
        if whitelist:
            # whitelist에 있으면 rollout 체크 스킵, 없으면 False
            return user_id in whitelist

        # 4. 롤아웃 비율 (0-100)
        rollout_percent = flag.get("rollout_percent", 100)
        if rollout_percent < 100:
            if not user_id:
                return False  # user_id 없으면 랜덤 선택 불가

            # 일관된 해시 기반 선택
            user_hash = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
            bucket = user_hash % 100
            if bucket >= rollout_percent:
                return False

        # 5. 컨텍스트 규칙
        rules = flag.get("rules", [])
        if rules and context:
            return self._check_rules(rules, context)

        return True

    def _check_rules(
        self, rules: list[dict[str, Any]], context: dict[str, Any]
    ) -> bool:
        """컨텍스트 기반 규칙 확인.

        Check if the context matches all rules.

        Args:
            rules: List of rule dictionaries
            context: Context dictionary to evaluate against

        Returns:
            True if all rules match, False otherwise
        """
        for rule in rules:
            field = rule.get("field", "")
            operator = rule.get("operator", "")
            value = rule.get("value")

            ctx_value = context.get(field)

            if operator == "equals":
                if ctx_value != value:
                    return False
            elif operator == "not_equals":
                if ctx_value == value:
                    return False
            elif operator == "greater_than":
                if ctx_value is None or ctx_value <= value:
                    return False
            elif operator == "less_than":
                if ctx_value is None or ctx_value >= value:
                    return False
            elif operator == "contains":
                if ctx_value is None:
                    return False
                # Check if value is in the string representation of ctx_value
                if isinstance(value, str) and value not in str(ctx_value):
                    return False
            elif operator == "in":
                if ctx_value is None:
                    return False
                if isinstance(value, (list, tuple, str)) and ctx_value not in value:
                    return False

        return True

    def get_variant(self, flag_name: str, user_id: str) -> str:
        """A/B 테스트용 변형 반환.

        Get the variant for A/B testing based on user_id.

        Args:
            flag_name: Name of the feature flag
            user_id: User identifier for consistent variant assignment

        Returns:
            Variant name (defaults to "control" if not found)
        """
        flag = self.flags.get(flag_name, {})
        variants = flag.get("variants", ["control"])

        if len(variants) <= 1:
            return variants[0] if variants else "control"

        # 일관된 해시 기반 변형 선택
        user_hash = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
        variant_index = user_hash % len(variants)

        return str(variants[variant_index])

    def enable_flag(self, flag_name: str) -> bool:
        """Enable a feature flag.

        Args:
            flag_name: Name of the flag to enable

        Returns:
            True if successful, False if flag not found
        """
        if flag_name not in self.flags:
            return False

        self.flags[flag_name]["enabled"] = True
        return self.save_flags()

    def disable_flag(self, flag_name: str) -> bool:
        """Disable a feature flag.

        Args:
            flag_name: Name of the flag to disable

        Returns:
            True if successful, False if flag not found
        """
        if flag_name not in self.flags:
            return False

        self.flags[flag_name]["enabled"] = False
        return self.save_flags()

    def set_rollout_percent(self, flag_name: str, percent: int) -> bool:
        """Set rollout percentage for a flag.

        Args:
            flag_name: Name of the flag
            percent: Rollout percentage (0-100)

        Returns:
            True if successful, False otherwise
        """
        if flag_name not in self.flags:
            return False

        if not 0 <= percent <= 100:
            return False

        self.flags[flag_name]["rollout_percent"] = percent
        return self.save_flags()

    def list_flags(self) -> list[dict[str, Any]]:
        """List all feature flags with their status.

        Returns:
            List of flag info dictionaries
        """
        result = []
        for name, config in self.flags.items():
            result.append(
                {
                    "name": name,
                    "enabled": config.get("enabled", False),
                    "description": config.get("description", ""),
                    "rollout_percent": config.get("rollout_percent", 100),
                    "environments": config.get("environments", []),
                }
            )
        return result
