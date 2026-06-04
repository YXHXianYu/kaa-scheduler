import logging
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from kaa_scheduler.config import build_default_config
from kaa_scheduler.models import RunOptions
from kaa_scheduler.scheduler import Scheduler


class SchedulerDryRunTests(unittest.TestCase):
    def test_run_dry_run_succeeds(self) -> None:
        config = build_default_config(Path(__file__).resolve().parents[1])
        config.ensure_runtime_dirs()
        logger = logging.getLogger("test_scheduler")
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())

        scheduler = Scheduler(config, logger)
        options = RunOptions(command="run", timeout_seconds=5, log_level="CRITICAL", dry_run=True)
        result = scheduler.run(options)

        self.assertTrue(result.success)
        self.assertEqual(result.exit_code, 0)
        self.assertGreaterEqual(len(result.steps), 5)

    def test_single_step_dry_run_succeeds(self) -> None:
        config = build_default_config(Path(__file__).resolve().parents[1])
        config.ensure_runtime_dirs()
        logger = logging.getLogger("test_scheduler_step")
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())

        scheduler = Scheduler(config, logger)
        options = RunOptions(
            command="step",
            step_name="kaa.launch",
            timeout_seconds=5,
            log_level="CRITICAL",
            dry_run=True,
        )

        result = scheduler.run(options)

        self.assertTrue(result.success)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(len(result.steps), 1)
        self.assertEqual(result.steps[0].name, "kaa.launch")

    def test_unknown_step_returns_error(self) -> None:
        config = build_default_config(Path(__file__).resolve().parents[1])
        config.ensure_runtime_dirs()
        logger = logging.getLogger("test_scheduler_unknown_step")
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())

        scheduler = Scheduler(config, logger)
        options = RunOptions(
            command="step",
            step_name="uu.not_real",
            timeout_seconds=5,
            log_level="CRITICAL",
            dry_run=True,
        )

        result = scheduler.run(options)

        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, 2)
        self.assertIn("Unknown step", result.message)


if __name__ == "__main__":
    unittest.main()
