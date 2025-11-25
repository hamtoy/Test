from __future__ import annotations

import atexit
from contextlib import suppress
from typing import Callable, Optional

from neo4j import GraphDatabase, Driver


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

    def session(self, *args, **kwargs):
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

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __getattr__(self, name: str):
        if self._driver is None:
            raise AttributeError(name)
        return getattr(self._driver, name)

    def __del__(self):
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
