"""환경 변수 검증 시스템

애플리케이션 시작 시 필수 환경 변수의 형식과 값을 검증합니다.
"""

from __future__ import annotations

import os
import re
from pathlib import Path


class ValidationError(Exception):
    """환경 변수 검증 실패 예외"""



class EnvValidator:
    """환경 변수 검증기"""

    @staticmethod
    def validate_gemini_api_key(key: str) -> None:
        """Gemini API 키 형식 검증

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
        """포트 번호 검증

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
        """URL 형식 검증

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
        """로그 레벨 검증

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
        """양의 정수 검증

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

    def validate_all(self) -> list[tuple[str, str]]:
        """모든 환경 변수 검증

        Returns:
            검증 실패한 (환경변수명, 에러메시지) 튜플 리스트

        """
        errors: list[tuple[str, str]] = []

        # GEMINI_API_KEY 검증 (필수)
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            try:
                self.validate_gemini_api_key(api_key)
            except ValidationError as e:
                errors.append(("GEMINI_API_KEY", str(e)))
        else:
            errors.append(("GEMINI_API_KEY", "Environment variable is required"))

        # NEO4J_URI 검증 (선택)
        neo4j_uri = os.getenv("NEO4J_URI")
        if neo4j_uri:
            try:
                self.validate_url(neo4j_uri)
            except ValidationError as e:
                errors.append(("NEO4J_URI", str(e)))

        # REDIS_URL 검증 (선택)
        redis_url = os.getenv("REDIS_URL")
        if redis_url and not (
            redis_url.startswith("redis://") or redis_url.startswith("rediss://")
        ):
            errors.append(("REDIS_URL", "Must start with 'redis://' or 'rediss://'"))

        # LOG_LEVEL 검증 (선택)
        log_level = os.getenv("LOG_LEVEL")
        if log_level:
            try:
                self.validate_log_level(log_level)
            except ValidationError as e:
                errors.append(("LOG_LEVEL", str(e)))

        # GEMINI_MAX_OUTPUT_TOKENS 검증 (선택)
        max_tokens = os.getenv("GEMINI_MAX_OUTPUT_TOKENS")
        if max_tokens:
            try:
                self.validate_positive_int(max_tokens, "GEMINI_MAX_OUTPUT_TOKENS")
            except ValidationError as e:
                errors.append(("GEMINI_MAX_OUTPUT_TOKENS", str(e)))

        # GEMINI_TIMEOUT 검증 (선택)
        timeout = os.getenv("GEMINI_TIMEOUT")
        if timeout:
            try:
                self.validate_positive_int(timeout, "GEMINI_TIMEOUT")
            except ValidationError as e:
                errors.append(("GEMINI_TIMEOUT", str(e)))

        # GEMINI_MAX_CONCURRENCY 검증 (선택)
        concurrency = os.getenv("GEMINI_MAX_CONCURRENCY")
        if concurrency:
            try:
                self.validate_positive_int(concurrency, "GEMINI_MAX_CONCURRENCY")
            except ValidationError as e:
                errors.append(("GEMINI_MAX_CONCURRENCY", str(e)))

        return errors


def validate_env_file_permissions() -> list[str]:
    """.env 파일 권한이 안전한지 확인

    권장: 600 (소유자만 읽기/쓰기)
    Note: Windows에서는 이 검사를 건너뜁니다.

    Returns:
        경고 메시지 리스트

    """
    import sys

    warnings: list[str] = []
    env_path = Path(".env")

    # Skip permission check on Windows
    if sys.platform == "win32":
        return warnings

    if env_path.exists():
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
    """환경 변수 검증 및 결과 출력

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
