# mypy: allow-untyped-defs
"""Simple cross-platform file locking utility.

Provides a context manager for exclusive file locking to prevent
race conditions when multiple processes write to the same file.
"""

from __future__ import annotations

import contextlib
import os
import time
from pathlib import Path
from typing import IO, Any

# Try to use platform-specific locking
try:
    import msvcrt  # type: ignore  # Windows

    _WINDOWS = True
except ImportError:
    msvcrt = None  # type: ignore
    _WINDOWS = False

try:
    import fcntl  # type: ignore  # Unix/Linux/Mac

    _UNIX = True
except ImportError:
    fcntl = None  # type: ignore
    _UNIX = False


class FileLockError(Exception):
    """Raised when a lock cannot be acquired."""


class FileLock:
    """A simple file-based lock with timeout support.

    Usage:
        with FileLock("/path/to/file"):
            # exclusive access to file
            file.write_text(...)
    """

    def __init__(
        self,
        path: str | Path,
        timeout: float = 10.0,
        poll_interval: float = 0.1,
    ) -> None:
        """Initialize the file lock.

        Args:
            path: Path to the file to lock (creates .lock suffix file)
            timeout: Maximum time to wait for lock acquisition (seconds)
            poll_interval: Time between lock acquisition attempts (seconds)
        """
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self.timeout = timeout
        self.poll_interval = poll_interval
        self._lock_file: IO[str] | None = None

    def _try_create_lock_file(self) -> bool:
        """Try to create and acquire the lock file.

        Returns:
            True if lock was successfully created and acquired.

        Raises:
            FileExistsError: If lock file already exists.
            OSError: If other file operation fails.
        """
        # Open file exclusively - will raise FileExistsError if exists
        self._lock_file = open(  # noqa: SIM115
            self.lock_path, "x", encoding="utf-8"
        )
        # Write PID for debugging
        self._lock_file.write(str(os.getpid()))
        self._lock_file.flush()

        # Apply OS-level lock if available
        if _WINDOWS:
            msvcrt.locking(  # type: ignore
                self._lock_file.fileno(),
                msvcrt.LK_NBLCK,  # type: ignore
                1,
            )
        elif _UNIX:
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)  # type: ignore

        return True

    def _cleanup_failed_lock(self) -> None:
        """Clean up after a failed lock attempt."""
        if self._lock_file:
            self._lock_file.close()
            self._lock_file = None
        with contextlib.suppress(OSError):
            self.lock_path.unlink()

    def _attempt_lock(self) -> tuple[bool, Exception | None]:
        """Attempt to acquire the lock once.

        Returns:
            Tuple of (success, error). If success is True, lock was acquired.
            If success is False and error is None, lock file exists (retry).
            If success is False and error is set, a fatal error occurred.
        """
        try:
            self._try_create_lock_file()
            return (True, None)
        except FileExistsError:
            return (False, None)  # Retry
        except (OSError, IOError) as e:
            self._cleanup_failed_lock()
            return (False, e)

    def acquire(self) -> bool:
        """Acquire the file lock.

        Returns:
            True if lock was acquired successfully.

        Raises:
            FileLockError: If lock cannot be acquired within timeout.
        """
        start_time = time.monotonic()

        while True:
            success, error = self._attempt_lock()

            if success:
                return True

            elapsed = time.monotonic() - start_time
            if elapsed >= self.timeout:
                if error:
                    raise FileLockError(f"Lock acquisition failed: {error}") from error
                raise FileLockError(
                    f"Could not acquire lock on {self.path} "
                    f"within {self.timeout}s timeout"
                )

            time.sleep(self.poll_interval)

    def release(self) -> None:
        """Release the file lock."""
        if self._lock_file:
            try:
                # Release OS-level lock
                if _WINDOWS:
                    with contextlib.suppress(OSError):
                        msvcrt.locking(  # type: ignore
                            self._lock_file.fileno(),
                            msvcrt.LK_UNLCK,  # type: ignore
                            1,
                        )
                elif _UNIX:
                    with contextlib.suppress(OSError):
                        fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)  # type: ignore

                self._lock_file.close()
            finally:
                self._lock_file = None

            # Remove lock file
            with contextlib.suppress(OSError):
                self.lock_path.unlink()

    def __enter__(self) -> "FileLock":
        """Enter context manager."""
        self.acquire()
        return self

    def __exit__(self, _exc_type: Any, _exc_val: Any, _exc_tb: Any) -> None:
        """Exit context manager."""
        self.release()


__all__ = ["FileLock", "FileLockError"]
