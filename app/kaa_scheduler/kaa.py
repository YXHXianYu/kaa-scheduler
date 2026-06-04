"""kaa process control helpers."""

import subprocess
import time
from logging import Logger
from typing import Optional

from kaa_scheduler.config import AppConfig
from kaa_scheduler.models import KaaStatus
from kaa_scheduler.infra.process import is_process_running, launch_process, list_process_details, wait_for_process_exit


WORKER_COMMAND_FRAGMENT = "-m kaa.main.cli"


class KaaController:
    """Encapsulate kaa process launch and wait logic."""

    def __init__(self, config: AppConfig, logger: Logger) -> None:
        self.config = config
        self.logger = logger
        self._process: Optional[subprocess.Popen] = None
        self._worker_pid: Optional[int] = None

    def _find_worker_process(self) -> Optional[dict]:
        """Return the real kaa worker process identified by its Python command line."""

        working_dir = str(self.config.kaa_working_dir).lower()
        for process in list_process_details():
            command_line = process.get("command_line", "")
            executable_path = process.get("executable_path", "")
            if process.get("image_name", "").lower() != "python.exe":
                continue
            if WORKER_COMMAND_FRAGMENT not in command_line:
                continue
            normalized_command = command_line.lower()
            normalized_path = executable_path.lower()
            if working_dir not in normalized_command and working_dir not in normalized_path:
                continue
            return process
        return None

    def _wait_for_worker_start(self, timeout_seconds: int = 15, poll_interval: float = 0.5) -> dict:
        """Wait until the real kaa worker process appears."""

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            worker = self._find_worker_process()
            if worker is not None:
                return worker
            time.sleep(poll_interval)
        raise RuntimeError("kaa launcher exited before the real worker process could be identified.")

    def _wait_for_worker_exit(self, pid: int, timeout_seconds: int, poll_interval: float = 0.5) -> int:
        """Wait until the identified kaa worker process exits."""

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            worker = self._find_worker_process()
            if worker is None or int(worker.get("pid") or 0) != pid:
                return 0
            time.sleep(poll_interval)
        raise TimeoutError("kaa worker process did not exit before the timeout.")

    def launch(self, dry_run: bool = False) -> KaaStatus:
        """Launch kaa from its fixed working directory."""

        if dry_run:
            message = "dry-run: skipped launching kaa"
            self.logger.info(message)
            return KaaStatus(process_running=False, pid=None, exit_code=0, message=message)

        if not self.config.kaa_exe_path.exists():
            raise FileNotFoundError("kaa executable was not found: " + str(self.config.kaa_exe_path))

        if not self.config.kaa_working_dir.exists():
            raise FileNotFoundError("kaa working directory was not found: " + str(self.config.kaa_working_dir))

        self._process = launch_process([str(self.config.kaa_exe_path)], cwd=self.config.kaa_working_dir)
        worker = self._wait_for_worker_start()
        self._worker_pid = int(worker["pid"])
        self.logger.info("kaa launched: launcher_pid=%s worker_pid=%s", self._process.pid, self._worker_pid)
        return KaaStatus(process_running=True, pid=self._worker_pid, message="kaa worker process identified")

    def wait_until_finish(self, timeout_seconds: int, dry_run: bool = False) -> KaaStatus:
        """Wait for the launched kaa process to exit."""

        if dry_run:
            message = "dry-run: skipped waiting for kaa"
            self.logger.info(message)
            return KaaStatus(process_running=False, pid=None, exit_code=0, message=message)

        if self._process is None:
            raise RuntimeError("kaa has not been launched in the current process.")

        launcher_exit_code = wait_for_process_exit(self._process, timeout_seconds)
        if self._worker_pid is None:
            raise RuntimeError("kaa worker process has not been identified in the current process.")

        exit_code = self._wait_for_worker_exit(self._worker_pid, timeout_seconds)
        self.logger.info(
            "kaa exited: launcher_pid=%s launcher_exit_code=%s worker_pid=%s worker_exit_code=%s",
            self._process.pid,
            launcher_exit_code,
            self._worker_pid,
            exit_code,
        )
        return KaaStatus(
            process_running=False,
            pid=self._worker_pid,
            exit_code=exit_code,
            message="kaa worker process exited",
        )

    def is_running(self) -> bool:
        """Return whether kaa currently appears to be running."""

        return is_process_running(self.config.kaa_process_name)
