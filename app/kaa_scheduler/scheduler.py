"""Main scheduler entry points for the project."""

import time
from dataclasses import asdict, is_dataclass
from logging import Logger
from typing import Any, Callable, List, Optional, Tuple

from kaa_scheduler.config import AppConfig
from kaa_scheduler.models import RunOptions, RunResult, StepResult
from kaa_scheduler.kaa import KaaController
from kaa_scheduler.uu import UuController
from kaa_scheduler.infra.single_instance import SingleInstanceLock


STEP_HELP = {
    "uu.ensure_started": "Ensure that the UU process exists.",
    "uu.attach_window": "Attach and foreground the UU main window.",
    "uu.get_status": "Read the current UU status without clicking.",
    "uu.ensure_target_accelerating": "Open the target game page and ensure acceleration is active.",
    "uu.stop_target_acceleration": "Stop target-game acceleration in UU.",
    "kaa.launch": "Launch kaa.exe.",
    "kaa.wait_until_finish": "Wait for kaa.exe to exit.",
}


class Scheduler:
    """Coordinate the high-level flow between UU and kaa."""

    def __init__(self, config: AppConfig, logger: Logger) -> None:
        self.config = config
        self.logger = logger
        self.uu = UuController(config, logger)
        self.kaa = KaaController(config, logger)

    def run(self, options: RunOptions) -> RunResult:
        """Dispatch one CLI command into the matching scheduler flow."""

        if options.command == "run":
            return self.run_full_flow(options)
        if options.command == "step":
            return self.run_single_step(options)
        if options.command == "probe-uu":
            return self.run_uu_probe(options)
        if options.command == "probe-kaa":
            return self.run_kaa_probe(options)
        return RunResult(
            command=options.command,
            success=False,
            exit_code=2,
            message="Unknown command: " + options.command,
        )

    def run_full_flow(self, options: RunOptions) -> RunResult:
        """Run the main daily flow skeleton."""

        start_time = time.perf_counter()
        steps: List[StepResult] = []
        try:
            with SingleInstanceLock(self.config.lock_file):
                self._run_step(steps, "uu.ensure_started", lambda: self.uu.ensure_started(options.dry_run))
                self._run_step(
                    steps,
                    "uu.attach_window",
                    lambda: self.uu.attach_window(require_window=not options.dry_run),
                )
                self._run_step(
                    steps,
                    "uu.ensure_target_accelerating",
                    lambda: self.uu.ensure_target_accelerating(options.dry_run),
                )
                self._run_step(steps, "kaa.launch", lambda: self.kaa.launch(options.dry_run))
                self._run_step(
                    steps,
                    "kaa.wait_until_finish",
                    lambda: self.kaa.wait_until_finish(options.timeout_seconds, options.dry_run),
                )
                self._run_step(
                    steps,
                    "uu.stop_target_acceleration",
                    lambda: self.uu.stop_target_acceleration(options.dry_run),
                )
        except NotImplementedError as exc:
            return self._build_result(options, steps, False, 2, str(exc), start_time)
        except Exception as exc:
            return self._build_result(options, steps, False, 1, str(exc), start_time)

        return self._build_result(options, steps, True, 0, "Run completed.", start_time)

    def run_uu_probe(self, options: RunOptions) -> RunResult:
        """Run the UU probe path."""

        start_time = time.perf_counter()
        steps: List[StepResult] = []
        try:
            self._run_step(steps, "uu.ensure_started", lambda: self.uu.ensure_started(options.dry_run))
            self._run_step(
                steps,
                "uu.attach_window",
                lambda: self.uu.attach_window(require_window=not options.dry_run),
            )
            self._run_step(steps, "uu.get_status", self.uu.get_status)
        except Exception as exc:
            return self._build_result(options, steps, False, 1, str(exc), start_time)

        return self._build_result(options, steps, True, 0, "UU probe completed.", start_time)

    def run_kaa_probe(self, options: RunOptions) -> RunResult:
        """Run the kaa probe path."""

        start_time = time.perf_counter()
        steps: List[StepResult] = []
        try:
            self._run_step(steps, "kaa.launch", lambda: self.kaa.launch(options.dry_run))
            self._run_step(
                steps,
                "kaa.wait_until_finish",
                lambda: self.kaa.wait_until_finish(options.timeout_seconds, options.dry_run),
            )
        except Exception as exc:
            return self._build_result(options, steps, False, 1, str(exc), start_time)

        return self._build_result(options, steps, True, 0, "kaa probe completed.", start_time)

    def run_single_step(self, options: RunOptions) -> RunResult:
        """Run exactly one named step from the scheduler flow."""

        start_time = time.perf_counter()
        steps: List[StepResult] = []

        if not options.step_name:
            return self._build_result(options, steps, False, 2, "Missing step name.", start_time)

        action = self._build_step_action(options, options.step_name)
        if action is None:
            available = ", ".join(sorted(STEP_HELP))
            return self._build_result(
                options,
                steps,
                False,
                2,
                "Unknown step: " + options.step_name + ". Available steps: " + available,
                start_time,
            )

        try:
            with SingleInstanceLock(self.config.lock_file):
                self._run_step(steps, options.step_name, action)
        except NotImplementedError as exc:
            return self._build_result(options, steps, False, 2, str(exc), start_time)
        except Exception as exc:
            return self._build_result(options, steps, False, 1, str(exc), start_time)

        return self._build_result(options, steps, True, 0, "Step completed.", start_time)

    def _build_step_action(self, options: RunOptions, step_name: str) -> Optional[Callable[[], Any]]:
        """Return the callable for one step name, if supported."""

        action_map: dict[str, Callable[[], Any]] = {
            "uu.ensure_started": lambda: self.uu.ensure_started(options.dry_run),
            "uu.attach_window": lambda: self.uu.attach_window(require_window=not options.dry_run),
            "uu.get_status": self.uu.get_status,
            "uu.ensure_target_accelerating": lambda: self.uu.ensure_target_accelerating(options.dry_run),
            "uu.stop_target_acceleration": lambda: self.uu.stop_target_acceleration(options.dry_run),
            "kaa.launch": lambda: self.kaa.launch(options.dry_run),
            "kaa.wait_until_finish": lambda: self.kaa.wait_until_finish(options.timeout_seconds, options.dry_run),
        }
        return action_map.get(step_name)

    def _run_step(self, steps: List[StepResult], name: str, action: Callable[[], Any]) -> Any:
        """Run one step, log it, and append a structured result."""

        self.logger.info("Starting step: %s", name)
        started = time.perf_counter()
        try:
            value = action()
        except Exception as exc:
            duration = time.perf_counter() - started
            steps.append(StepResult(name=name, success=False, message=str(exc), duration_seconds=duration))
            self.logger.exception("Step failed: %s", name)
            raise

        duration = time.perf_counter() - started
        message, metadata = self._describe_step_value(value)
        steps.append(
            StepResult(
                name=name,
                success=True,
                message=message,
                duration_seconds=duration,
                metadata=metadata,
            )
        )
        self.logger.info("Completed step: %s | %s", name, message)
        return value

    def _build_result(
        self,
        options: RunOptions,
        steps: List[StepResult],
        success: bool,
        exit_code: int,
        message: str,
        started_at: float,
    ) -> RunResult:
        """Build the final command result."""

        return RunResult(
            command=options.command,
            success=success,
            exit_code=exit_code,
            message=message,
            steps=steps,
            duration_seconds=time.perf_counter() - started_at,
        )

    def _describe_step_value(self, value: Any) -> Tuple[str, dict]:
        """Extract a readable message and metadata for one step result."""

        if is_dataclass(value):
            metadata = asdict(value)
            message = metadata.get("message") or value.__class__.__name__
            return str(message), metadata
        return str(value), {}
