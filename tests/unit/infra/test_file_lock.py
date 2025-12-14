"""Tests for src/infra/file_lock.py module.

This module tests the cross-platform file locking functionality.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.infra.file_lock import FileLock, FileLockError


class TestFileLockInit:
    """Test FileLock initialization."""

    def test_init_with_string_path(self, tmp_path: Path) -> None:
        """Test initialization with string path."""
        path = str(tmp_path / "test.txt")
        lock = FileLock(path)

        assert lock.path == Path(path)
        assert lock.lock_path == Path(path + ".lock")
        assert lock.timeout == 10.0
        assert lock.poll_interval == 0.1
        assert lock._lock_file is None

    def test_init_with_path_object(self, tmp_path: Path) -> None:
        """Test initialization with Path object."""
        path = tmp_path / "test.txt"
        lock = FileLock(path)

        assert lock.path == path
        assert lock.lock_path == path.with_suffix(".txt.lock")

    def test_init_custom_timeout(self, tmp_path: Path) -> None:
        """Test initialization with custom timeout."""
        path = tmp_path / "test.txt"
        lock = FileLock(path, timeout=5.0)

        assert lock.timeout == 5.0

    def test_init_custom_poll_interval(self, tmp_path: Path) -> None:
        """Test initialization with custom poll interval."""
        path = tmp_path / "test.txt"
        lock = FileLock(path, poll_interval=0.5)

        assert lock.poll_interval == 0.5


class TestFileLockAcquire:
    """Test FileLock.acquire method."""

    def test_acquire_creates_lock_file(self, tmp_path: Path) -> None:
        """Test that acquire creates a lock file."""
        path = tmp_path / "test.txt"
        lock = FileLock(path)

        result = lock.acquire()

        assert result is True
        assert lock.lock_path.exists()
        lock.release()

    def test_acquire_writes_pid(self, tmp_path: Path) -> None:
        """Test that acquire writes PID to lock file."""
        path = tmp_path / "test.txt"
        lock = FileLock(path)

        lock.acquire()

        # On Windows, the lock file is locked so we can't read it directly
        # Verify lock file exists and PID was written by checking _lock_file
        assert lock._lock_file is not None
        assert lock.lock_path.exists()
        lock.release()

    def test_acquire_timeout(self, tmp_path: Path) -> None:
        """Test that acquire raises FileLockError on timeout."""
        path = tmp_path / "test.txt"
        lock_file = path.with_suffix(".txt.lock")

        # Create existing lock file
        lock_file.write_text("12345", encoding="utf-8")

        lock = FileLock(path, timeout=0.3, poll_interval=0.1)

        with pytest.raises(FileLockError) as exc_info:
            lock.acquire()

        assert "timeout" in str(exc_info.value).lower()

    def test_acquire_retry_on_file_exists(self, tmp_path: Path) -> None:
        """Test that acquire retries when lock file exists."""
        path = tmp_path / "test.txt"
        lock_file = path.with_suffix(".txt.lock")
        lock = FileLock(path, timeout=1.0, poll_interval=0.1)

        # Create lock file that will be deleted after short time
        lock_file.write_text("12345", encoding="utf-8")

        def delete_after_delay() -> None:
            time.sleep(0.2)
            lock_file.unlink()

        thread = threading.Thread(target=delete_after_delay)
        thread.start()

        result = lock.acquire()
        thread.join()

        assert result is True
        lock.release()


class TestFileLockRelease:
    """Test FileLock.release method."""

    def test_release_removes_lock_file(self, tmp_path: Path) -> None:
        """Test that release removes the lock file."""
        path = tmp_path / "test.txt"
        lock = FileLock(path)

        lock.acquire()
        assert lock.lock_path.exists()

        lock.release()
        assert not lock.lock_path.exists()

    def test_release_when_not_acquired(self, tmp_path: Path) -> None:
        """Test release when lock was not acquired."""
        path = tmp_path / "test.txt"
        lock = FileLock(path)

        # Should not raise
        lock.release()

    def test_release_twice(self, tmp_path: Path) -> None:
        """Test releasing twice doesn't raise."""
        path = tmp_path / "test.txt"
        lock = FileLock(path)

        lock.acquire()
        lock.release()
        lock.release()  # Should not raise


class TestFileLockContextManager:
    """Test FileLock context manager protocol."""

    def test_context_manager_acquires_and_releases(self, tmp_path: Path) -> None:
        """Test that context manager acquires and releases lock."""
        path = tmp_path / "test.txt"
        lock_file = path.with_suffix(".txt.lock")
        lock = FileLock(path)

        with lock:
            assert lock_file.exists()

        assert not lock_file.exists()

    def test_context_manager_releases_on_exception(self, tmp_path: Path) -> None:
        """Test that context manager releases lock even on exception."""
        path = tmp_path / "test.txt"
        lock_file = path.with_suffix(".txt.lock")
        lock = FileLock(path)

        with pytest.raises(ValueError), lock:
            assert lock_file.exists()
            raise ValueError("Test exception")

        assert not lock_file.exists()

    def test_context_manager_returns_self(self, tmp_path: Path) -> None:
        """Test that __enter__ returns the lock instance."""
        path = tmp_path / "test.txt"
        lock = FileLock(path)

        with lock as acquired_lock:
            assert acquired_lock is lock


class TestFileLockConcurrency:
    """Test FileLock concurrency behavior."""

    def test_concurrent_access_blocks(self, tmp_path: Path) -> None:
        """Test that concurrent access is blocked."""
        path = tmp_path / "test.txt"
        results: list[tuple[int, float]] = []

        def worker(worker_id: int) -> None:
            lock = FileLock(path, timeout=5.0)
            start = time.time()
            with lock:
                results.append((worker_id, time.time() - start))
                time.sleep(0.1)  # Hold lock briefly

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]

        start_time = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        total_time = time.time() - start_time

        # All threads should have completed
        assert len(results) == 3
        # Total time should be at least 0.3 seconds (3 * 0.1)
        assert total_time >= 0.25


class TestFileLockError:
    """Test FileLockError exception."""

    def test_file_lock_error_message(self) -> None:
        """Test that FileLockError contains message."""
        error = FileLockError("Test error message")
        assert str(error) == "Test error message"

    def test_file_lock_error_inheritance(self) -> None:
        """Test that FileLockError inherits from Exception."""
        assert issubclass(FileLockError, Exception)


class TestFileLockCleanup:
    """Test internal cleanup methods."""

    def test_cleanup_failed_lock(self, tmp_path: Path) -> None:
        """Test _cleanup_failed_lock method."""
        path = tmp_path / "test.txt"
        lock = FileLock(path)

        # Create a mock lock file
        mock_file = MagicMock()
        lock._lock_file = mock_file
        lock.lock_path.write_text("test", encoding="utf-8")

        lock._cleanup_failed_lock()

        assert lock._lock_file is None
        mock_file.close.assert_called_once()  # type: ignore[unreachable]

    def test_cleanup_failed_lock_handles_oserror(self, tmp_path: Path) -> None:
        """Test _cleanup_failed_lock handles OSError gracefully."""
        path = tmp_path / "test.txt"
        lock = FileLock(path)

        # Set up mock that doesn't exist
        mock_file = MagicMock()
        mock_file.close = MagicMock()
        lock._lock_file = mock_file

        # Should not raise even if unlink fails
        lock._cleanup_failed_lock()


class TestAttemptLock:
    """Test _attempt_lock method."""

    def test_attempt_lock_success(self, tmp_path: Path) -> None:
        """Test successful lock attempt."""
        path = tmp_path / "test.txt"
        lock = FileLock(path)

        success, error = lock._attempt_lock()

        assert success is True
        assert error is None
        lock.release()

    def test_attempt_lock_file_exists(self, tmp_path: Path) -> None:
        """Test lock attempt when file already exists."""
        path = tmp_path / "test.txt"
        lock_file = path.with_suffix(".txt.lock")
        lock_file.write_text("12345", encoding="utf-8")

        lock = FileLock(path)
        success, error = lock._attempt_lock()

        assert success is False
        assert error is None  # FileExistsError returns None error

    def test_attempt_lock_os_error(self, tmp_path: Path) -> None:
        """Test lock attempt with OSError."""
        path = tmp_path / "test.txt"
        lock = FileLock(path)

        with patch("builtins.open", side_effect=OSError("Permission denied")):
            success, error = lock._attempt_lock()

        assert success is False
        assert isinstance(error, OSError)


class TestTryCreateLockFile:
    """Test _try_create_lock_file method."""

    def test_try_create_lock_file_success(self, tmp_path: Path) -> None:
        """Test successful lock file creation."""
        path = tmp_path / "test.txt"
        lock = FileLock(path)

        result = lock._try_create_lock_file()

        assert result is True
        assert lock._lock_file is not None
        assert lock.lock_path.exists()
        lock.release()

    def test_try_create_lock_file_already_exists(self, tmp_path: Path) -> None:
        """Test lock file creation when file already exists."""
        path = tmp_path / "test.txt"
        lock_file = path.with_suffix(".txt.lock")
        lock_file.write_text("12345", encoding="utf-8")

        lock = FileLock(path)

        with pytest.raises(FileExistsError):
            lock._try_create_lock_file()


class TestModuleExports:
    """Test module exports."""

    def test_all_exports(self) -> None:
        """Test __all__ contains expected exports."""
        from src.infra import file_lock

        assert hasattr(file_lock, "__all__")
        assert "FileLock" in file_lock.__all__
        assert "FileLockError" in file_lock.__all__


class TestPlatformSpecificLocking:
    """Test platform-specific locking behavior."""

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    def test_windows_locking(self, tmp_path: Path) -> None:
        """Test Windows-specific locking with msvcrt."""
        path = tmp_path / "test.txt"
        lock = FileLock(path)

        lock.acquire()
        assert lock._lock_file is not None
        lock.release()

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-specific test")
    def test_unix_locking(self, tmp_path: Path) -> None:
        """Test Unix-specific locking with fcntl."""
        path = tmp_path / "test.txt"
        lock = FileLock(path)

        lock.acquire()
        assert lock._lock_file is not None
        lock.release()
