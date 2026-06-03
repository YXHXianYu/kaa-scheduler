import logging
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from kaa_scheduler.config import build_default_config
from kaa_scheduler.models import UuStatus
from kaa_scheduler.uu import UuController


class UuControllerTests(unittest.TestCase):
    def test_get_status_returns_model(self) -> None:
        config = build_default_config(Path(__file__).resolve().parents[1])
        logger = logging.getLogger("test_uu")
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())

        controller = UuController(config, logger)
        status = controller.get_status()

        self.assertIsInstance(status, UuStatus)

    def test_target_game_page_color_classifier(self) -> None:
        self.assertTrue(
            UuController._looks_like_target_game_page_from_samples(
                [(36, 216, 210), (42, 210, 206)]
            )
        )
        self.assertFalse(
            UuController._looks_like_target_game_page_from_samples(
                [(120, 120, 120), (80, 90, 110)]
            )
        )

    def test_accelerating_state_color_classifiers(self) -> None:
        self.assertTrue(
            UuController._looks_like_stop_button_from_samples(
                [(96, 108, 186), (102, 112, 180)]
            )
        )
        self.assertTrue(
            UuController._looks_like_accelerating_bar_from_samples(
                [(28, 33, 71), (30, 36, 77)]
            )
        )
        self.assertFalse(
            UuController._looks_like_stop_button_from_samples(
                [(36, 216, 210), (42, 210, 206)]
            )
        )

    def test_stop_confirm_dialog_classifier(self) -> None:
        self.assertTrue(
            UuController._looks_like_stop_confirm_button_sample((0, 210, 196))
        )
        self.assertFalse(
            UuController._looks_like_stop_confirm_button_sample((16, 22, 43))
        )


if __name__ == "__main__":
    unittest.main()
