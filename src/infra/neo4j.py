"""Neo4j 연결 유틸리티 모듈."""

from __future__ import annotations

import atexit
import os
from contextlib import suppress
from typing import Any, Callable, Optional

from neo4j import GraphDatabase, Driver

__all__ = ["SafeDriver", "create_sync_driver", "get_neo4j_driver_from_env"]


class SafeDriver:
    """
    Thin wrapper around Neo4j sync Driver that guarantees close is called.
    Supports context manager semantics to encourage explicit lifecycle control.
    """

    def __init__(self, driver: Driver, *, register_atexit: bool = False):
        self._driver: Optional[Driver] = driver
        self._register_atexit = register_atexit
        if register_atexit:
            atexit.register(self.close)

    @property
    def driver(self) -> Driver:
        """내부 Neo4j Driver 인스턴스에 대한 접근자."""
        if self._driver is None:
            raise RuntimeError("Driver already closed")
        return self._driver

    def session(self, *args: Any, **kwargs: Any) -> Any:
        if self._driver is None:
            raise RuntimeError("Driver already closed")
        return self._driver.session(*args, **kwargs)

    def close(self) -> None:
        if self._driver is None:
            return
        with suppress(Exception):
            self._driver.close()
        self._driver = None

    def __enter__(self) -> "SafeDriver":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def __getattr__(self, name: str) -> Any:
        if self._driver is None:
            raise AttributeError(name)
        return getattr(self._driver, name)

    def __del__(self) -> None:
        self.close()


def create_sync_driver(
    uri: str,
    user: str,
    password: str,
    *,
    register_atexit: bool = False,
    graph_db_factory: Optional[Callable[..., Driver]] = None,
) -> SafeDriver:
    """
    Create a Neo4j sync driver wrapped with SafeDriver to enforce close().
    """
    factory = graph_db_factory or GraphDatabase.driver
    driver = factory(uri, auth=(user, password))
    return SafeDriver(driver, register_atexit=register_atexit)


def get_neo4j_driver_from_env(*, register_atexit: bool = False) -> SafeDriver:
    """
    환경 변수에서 Neo4j 연결 정보를 읽어 SafeDriver 생성.

    환경 변수:
        NEO4J_URI: Neo4j 서버 URI
        NEO4J_USER: 사용자 이름
        NEO4J_PASSWORD: 비밀번호

    Raises:
        EnvironmentError: 필수 환경 변수 누락 시

    Returns:
        SafeDriver 인스턴스
    """
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    if uri is None or user is None or password is None:
        raise EnvironmentError(
            "Missing required Neo4j environment variables: "
            "NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD"
        )

    return create_sync_driver(uri, user, password, register_atexit=register_atexit)
