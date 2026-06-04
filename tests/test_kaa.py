import logging
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from kaa_scheduler.config import build_default_config
from kaa_scheduler.kaa import KaaController, START_IMMEDIATELY_ARGUMENT


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

    def test_find_worker_process_by_command_line(self) -> None:
        config = build_default_config(Path(__file__).resolve().parents[1])
        logger = logging.getLogger("test_kaa_worker")
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())

        controller = KaaController(config, logger)
        fake_processes = [
            {
                "pid": "100",
                "parent_pid": "1",
                "image_name": "python.exe",
                "executable_path": r"D:\Programs\kaa-bootstrap-0.5.1\WPy64-310111\python-3.10.11.amd64\python.exe",
                "command_line": r'"D:\Programs\kaa-bootstrap-0.5.1\WPy64-310111\python-3.10.11.amd64\python.exe" -m kaa.main.cli',
            },
            {
                "pid": "101",
                "parent_pid": "1",
                "image_name": "python.exe",
                "executable_path": r"C:\Python39\python.exe",
                "command_line": r'"C:\Python39\python.exe" script.py',
            },
        ]

        with patch("kaa_scheduler.kaa.list_process_details", return_value=fake_processes):
            worker = controller._find_worker_process()

        self.assertIsNotNone(worker)
        self.assertEqual(worker["pid"], "100")

    def test_launch_passes_start_immediately_argument(self) -> None:
        config = build_default_config(Path(__file__).resolve().parents[1])
        logger = logging.getLogger("test_kaa_launch_args")
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())

        controller = KaaController(config, logger)
        fake_process = MagicMock(pid=123)

        with patch("pathlib.Path.exists", return_value=True), \
             patch("kaa_scheduler.kaa.launch_process", return_value=fake_process) as launch_process_mock, \
             patch.object(controller, "_wait_for_worker_start", return_value={"pid": "456"}):
            status = controller.launch(dry_run=False)

        launch_process_mock.assert_called_once_with(
            [str(config.kaa_exe_path), START_IMMEDIATELY_ARGUMENT],
            cwd=config.kaa_working_dir,
        )
        self.assertEqual(status.pid, 456)
        self.assertTrue(status.process_running)


if __name__ == "__main__":
    unittest.main()
