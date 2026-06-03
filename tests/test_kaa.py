import logging
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from kaa_scheduler.config import build_default_config
from kaa_scheduler.kaa import KaaController


class KaaControllerTests(unittest.TestCase):
    def test_dry_run_launch_and_wait(self) -> None:
        config = build_default_config(Path(__file__).resolve().parents[1])
        logger = logging.getLogger("test_kaa")
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())

        controller = KaaController(config, logger)
        launch_status = controller.launch(dry_run=True)
        wait_status = controller.wait_until_finish(timeout_seconds=5, dry_run=True)

        self.assertEqual(launch_status.exit_code, 0)
        self.assertEqual(wait_status.exit_code, 0)


if __name__ == "__main__":
    unittest.main()
