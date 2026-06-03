"""Single-instance file lock used by the scheduler."""

import msvcrt
import os
from pathlib import Path
from typing import Optional, TextIO


class SingleInstanceLock:
    """A tiny Windows-only file lock to prevent duplicate runs."""

    def __init__(self, lock_path: Path) -> None:
        self.lock_path = Path(lock_path)
        self._handle: Optional[TextIO] = None

    def acquire(self) -> None:
        """Acquire the lock or raise if another process already holds it."""

        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.lock_path, "a+", encoding="utf-8")
        handle.seek(0)
        handle.write(" ")
        handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            handle.close()
            raise RuntimeError("Another kaa_scheduler instance is already running.") from exc

        handle.seek(0)
        handle.write(str(os.getpid()).ljust(32))
        handle.truncate()
        handle.flush()
        self._handle = handle

    def release(self) -> None:
        """Release the lock if it is currently held."""

        if self._handle is None:
            return
        self._handle.seek(0)
        msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
        self._handle.close()
        self._handle = None

    def __enter__(self) -> "SingleInstanceLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        self.release()
