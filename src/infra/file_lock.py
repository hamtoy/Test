"""Simple cross-platform file locking utility.

Provides a context manager for exclusive file locking to prevent
race conditions when multiple processes write to the same file.
"""

from __future__ import annotations

import contextlib
import errno
import os
import sys
import time
from pathlib import Path
from typing import IO, Any

# Platform detection
_WINDOWS = sys.platform == "win32"
_UNIX = sys.platform != "win32"

# Platform-specific module references (set at runtime)
_msvcrt: Any = None
_fcntl: Any = None

if _WINDOWS:
    import msvcrt as _msvcrt  # Windows-only
elif _UNIX:
    import fcntl as _fcntl  # Unix/Linux/Mac


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
        if _WINDOWS and _msvcrt is not None:
            _msvcrt.locking(
                self._lock_file.fileno(),
                _msvcrt.LK_NBLCK,
                1,
            )
        elif _UNIX and _fcntl is not None:
            _fcntl.flock(self._lock_file.fileno(), _fcntl.LOCK_EX | _fcntl.LOCK_NB)

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
            # If OS-level locking failed due to contention, don't delete the lock file.
            # This can happen on some filesystems where exclusive file creation is not
            # strictly atomic under concurrency; deleting here would break mutual exclusion.
            if getattr(e, "errno", None) in {
                errno.EACCES,
                errno.EAGAIN,
                errno.EWOULDBLOCK,
            }:
                if self._lock_file:
                    self._lock_file.close()
                    self._lock_file = None
                return (False, None)

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
                if _WINDOWS and _msvcrt is not None:
                    with contextlib.suppress(OSError):
                        _msvcrt.locking(
                            self._lock_file.fileno(),
                            _msvcrt.LK_UNLCK,
                            1,
                        )
                elif _UNIX and _fcntl is not None:
                    with contextlib.suppress(OSError):
                        _fcntl.flock(self._lock_file.fileno(), _fcntl.LOCK_UN)

                self._lock_file.close()
            finally:
                self._lock_file = None

            # Remove lock file
            with contextlib.suppress(OSError):
                self.lock_path.unlink()

    def __enter__(self) -> FileLock:
        """Enter context manager."""
        self.acquire()
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: Any,
    ) -> None:
        """Exit context manager."""
        self.release()


__all__ = ["FileLock", "FileLockError"]
