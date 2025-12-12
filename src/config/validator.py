"""환경 변수 검증 시스템.

애플리케이션 시작 시 필수 환경 변수의 형식과 값을 검증합니다.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from pathlib import Path


class ValidationError(Exception):
    """환경 변수 검증 실패 예외."""


class EnvValidator:
    """환경 변수 검증기."""

    @staticmethod
    def validate_gemini_api_key(key: str) -> None:
        """Gemini API 키 형식 검증.

        Args:
            key: Gemini API 키

        Raises:
            ValidationError: 키 형식이 올바르지 않은 경우

        """
        if not key.startswith("AIza"):
            raise ValidationError("GEMINI_API_KEY must start with 'AIza'")
        if len(key) != 39:
            raise ValidationError(
                f"GEMINI_API_KEY must be 39 characters, got {len(key)}",
            )

    @staticmethod
    def validate_port(port: str) -> None:
        """포트 번호 검증.

        Args:
            port: 포트 번호 문자열

        Raises:
            ValidationError: 포트 번호가 유효하지 않은 경우

        """
        try:
            p = int(port)
            if not (1024 <= p <= 65535):
                raise ValidationError(f"Port {port} must be between 1024-65535")
        except ValueError:
            raise ValidationError(f"Port {port} must be an integer")

    @staticmethod
    def validate_url(url: str) -> None:
        """URL 형식 검증.

        Args:
            url: URL 문자열

        Raises:
            ValidationError: URL 형식이 올바르지 않은 경우

        """
        pattern = re.compile(
            r"^(https?|bolt)://"  # http, https, bolt
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
            r"localhost|"
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
            r"(?::\d+)?"
            r"(?:/?|[/?]\S+)?$",
            re.IGNORECASE,
        )
        if not pattern.match(url):
            raise ValidationError(f"Invalid URL format: {url}")

    @staticmethod
    def validate_log_level(level: str) -> None:
        """로그 레벨 검증.

        Args:
            level: 로그 레벨 문자열

        Raises:
            ValidationError: 로그 레벨이 유효하지 않은 경우

        """
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if level.upper() not in valid_levels:
            raise ValidationError(
                f"Invalid log level: {level}. Use one of: {valid_levels}",
            )

    @staticmethod
    def validate_positive_int(value: str, name: str) -> None:
        """양의 정수 검증.

        Args:
            value: 검증할 값
            name: 환경 변수 이름 (에러 메시지용)

        Raises:
            ValidationError: 값이 양의 정수가 아닌 경우

        """
        try:
            v = int(value)
            if v <= 0:
                raise ValidationError(f"{name} must be a positive integer, got {v}")
        except ValueError:
            raise ValidationError(f"{name} must be an integer, got {value}")

    def _validate_required_env(
        self,
        key: str,
        validator: Callable[[str], None],
        errors: list[tuple[str, str]],
    ) -> None:
        value = os.getenv(key)
        if not value:
            errors.append((key, "Environment variable is required"))
            return
        self._validate_value(key, value, validator, errors)

    def _validate_optional_env(
        self,
        key: str,
        validator: Callable[[str], None],
        errors: list[tuple[str, str]],
    ) -> None:
        value = os.getenv(key)
        if value:
            self._validate_value(key, value, validator, errors)

    def _validate_optional_positive_int(
        self,
        key: str,
        errors: list[tuple[str, str]],
    ) -> None:
        value = os.getenv(key)
        if not value:
            return
        try:
            self.validate_positive_int(value, key)
        except ValidationError as exc:
            errors.append((key, str(exc)))

    def _validate_redis_url(self, errors: list[tuple[str, str]]) -> None:
        redis_url = os.getenv("REDIS_URL")
        if redis_url and not (
            redis_url.startswith("redis://") or redis_url.startswith("rediss://")
        ):
            errors.append(("REDIS_URL", "Must start with 'redis://' or 'rediss://'"))

    def _validate_value(
        self,
        key: str,
        value: str,
        validator: Callable[[str], None],
        errors: list[tuple[str, str]],
    ) -> None:
        try:
            validator(value)
        except ValidationError as exc:
            errors.append((key, str(exc)))

    def validate_all(self) -> list[tuple[str, str]]:
        """모든 환경 변수 검증.

        Returns:
            검증 실패한 (환경변수명, 에러메시지) 튜플 리스트

        """
        errors: list[tuple[str, str]] = []

        self._validate_required_env(
            "GEMINI_API_KEY",
            self.validate_gemini_api_key,
            errors,
        )
        self._validate_optional_env("NEO4J_URI", self.validate_url, errors)
        self._validate_redis_url(errors)
        self._validate_optional_env("LOG_LEVEL", self.validate_log_level, errors)

        for key in (
            "GEMINI_MAX_OUTPUT_TOKENS",
            "GEMINI_TIMEOUT",
            "GEMINI_MAX_CONCURRENCY",
        ):
            self._validate_optional_positive_int(key, errors)

        return errors


def validate_env_file_permissions() -> list[str]:
    """.env 파일 권한이 안전한지 확인.

    권장: 600 (소유자만 읽기/쓰기)
    Note: Windows에서는 이 검사를 건너뜁니다.

    Returns:
        경고 메시지 리스트

    """
    import sys

    warnings: list[str] = []
    env_path = Path(".env")

    # Permission check only on Unix-like systems
    if sys.platform != "win32" and env_path.exists():
        try:
            st = env_path.stat()
            # Check if group or others have any permissions (Unix only)
            if st.st_mode & 0o077:
                mode_str = oct(st.st_mode)[-3:]
                warnings.append(
                    f".env 파일 권한이 안전하지 않습니다: {mode_str}\n"
                    f"  💡 권장: chmod 600 .env",
                )
        except (OSError, AttributeError):
            # On some platforms or file systems, skip permission check
            pass

    return warnings


def validate_environment(strict: bool = False) -> bool:
    """환경 변수 검증 및 결과 출력.

    Args:
        strict: True인 경우 검증 실패 시 SystemExit 발생

    Returns:
        검증 성공 시 True, 실패 시 False

    Raises:
        SystemExit: strict=True이고 검증 실패 시

    """
    validator = EnvValidator()
    errors = validator.validate_all()

    # Check file permissions (warnings only)
    permission_warnings = validate_env_file_permissions()
    for warning in permission_warnings:
        print(f"⚠️  {warning}")

    if errors:
        print("❌ Environment validation failed:")
        for key, error in errors:
            print(f"  - {key}: {error}")

        if strict:
            raise SystemExit(1)
        return False

    print("✅ All environment variables validated")
    return True


__all__ = [
    "EnvValidator",
    "ValidationError",
    "validate_env_file_permissions",
    "validate_environment",
]
