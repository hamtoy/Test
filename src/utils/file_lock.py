# mypy: allow-untyped-defs
"""Simple cross-platform file locking utility.

Provides a context manager for exclusive file locking to prevent
race conditions when multiple processes write to the same file.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

# Try to use platform-specific locking
try:
    import msvcrt  # Windows

    _WINDOWS = True
except ImportError:
    _WINDOWS = False

try:
    import fcntl  # Unix/Linux/Mac

    _UNIX = True
except ImportError:
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
        self._lock_file: Any = None

    def acquire(self) -> bool:
        """Acquire the file lock.

        Returns:
            True if lock was acquired successfully.

        Raises:
            FileLockError: If lock cannot be acquired within timeout.
        """
        start_time = time.monotonic()

        while True:
            try:
                # Try to create lock file exclusively
                self._lock_file = open(self.lock_path, "x", encoding="utf-8")
                # Write PID for debugging
                self._lock_file.write(str(os.getpid()))
                self._lock_file.flush()

                # Apply OS-level lock if available
                if _WINDOWS:
                    msvcrt.locking(
                        self._lock_file.fileno(),
                        msvcrt.LK_NBLCK,
                        1,
                    )
                elif _UNIX:
                    fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

                return True

            except FileExistsError:
                # Lock file exists, check timeout
                elapsed = time.monotonic() - start_time
                if elapsed >= self.timeout:
                    raise FileLockError(
                        f"Could not acquire lock on {self.path} "
                        f"within {self.timeout}s timeout"
                    )
                time.sleep(self.poll_interval)

            except (OSError, IOError) as e:
                # Clean up partial lock file
                if self._lock_file:
                    self._lock_file.close()
                    self._lock_file = None
                if self.lock_path.exists():
                    try:
                        self.lock_path.unlink()
                    except OSError:
                        pass

                elapsed = time.monotonic() - start_time
                if elapsed >= self.timeout:
                    raise FileLockError(f"Lock acquisition failed: {e}")
                time.sleep(self.poll_interval)

    def release(self) -> None:
        """Release the file lock."""
        if self._lock_file:
            try:
                # Release OS-level lock
                if _WINDOWS:
                    try:
                        msvcrt.locking(
                            self._lock_file.fileno(),
                            msvcrt.LK_UNLCK,
                            1,
                        )
                    except OSError:
                        pass
                elif _UNIX:
                    try:
                        fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass

                self._lock_file.close()
            finally:
                self._lock_file = None

            # Remove lock file
            try:
                self.lock_path.unlink()
            except OSError:
                pass

    def __enter__(self) -> "FileLock":
        """Enter context manager."""
        self.acquire()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager."""
        self.release()


__all__ = ["FileLock", "FileLockError"]
