"""kaa process control helpers."""

import subprocess
from logging import Logger
from typing import Optional

from kaa_scheduler.config import AppConfig
from kaa_scheduler.models import KaaStatus
from kaa_scheduler.infra.process import is_process_running, launch_process, wait_for_process_exit


class KaaController:
    """Encapsulate kaa process launch and wait logic."""

    def __init__(self, config: AppConfig, logger: Logger) -> None:
        self.config = config
        self.logger = logger
        self._process: Optional[subprocess.Popen] = None

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
        self.logger.info("kaa launched: pid=%s", self._process.pid)
        return KaaStatus(process_running=True, pid=self._process.pid, message="kaa launch command issued")

    def wait_until_finish(self, timeout_seconds: int, dry_run: bool = False) -> KaaStatus:
        """Wait for the launched kaa process to exit."""

        if dry_run:
            message = "dry-run: skipped waiting for kaa"
            self.logger.info(message)
            return KaaStatus(process_running=False, pid=None, exit_code=0, message=message)

        if self._process is None:
            raise RuntimeError("kaa has not been launched in the current process.")

        exit_code = wait_for_process_exit(self._process, timeout_seconds)
        self.logger.info("kaa exited: pid=%s exit_code=%s", self._process.pid, exit_code)
        return KaaStatus(
            process_running=False,
            pid=self._process.pid,
            exit_code=exit_code,
            message="kaa process exited",
        )

    def is_running(self) -> bool:
        """Return whether kaa currently appears to be running."""

        return is_process_running(self.config.kaa_process_name)
