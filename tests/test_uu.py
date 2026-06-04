import logging
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_stop_target_acceleration_does_not_reopen_target_page(self) -> None:
        config = build_default_config(Path(__file__).resolve().parents[1])
        logger = logging.getLogger("test_uu_stop")
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())

        controller = UuController(config, logger)
        assumed_status = UuStatus(True, True, None, message="status not stable")

        with patch.object(controller, "get_status", return_value=assumed_status), patch.object(
            controller, "attach_window", return_value=UuStatus(True, True, None, message="attached")
        ), patch.object(controller, "_find_attached_window", return_value=object()), patch.object(
            controller, "_build_visual_status", return_value=None
        ), patch.object(controller, "_click_anchor") as click_anchor, patch.object(
            controller, "_has_stop_confirm_dialog", return_value=False
        ), patch.object(controller, "_wait_for_current_page_stop_state", return_value=True
        ), patch.object(controller, "_wait_for_stopped_state", return_value=True), patch.object(
            controller, "_open_target_game_page"
        ) as reopen_target_page:
            result = controller.stop_target_acceleration(dry_run=False)

        reopen_target_page.assert_not_called()
        click_anchor.assert_called()
        self.assertFalse(result.accelerating_target)

    def test_ensure_target_accelerating_stops_other_game_first(self) -> None:
        config = build_default_config(Path(__file__).resolve().parents[1])
        logger = logging.getLogger("test_uu_stop_other_game")
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())

        controller = UuController(config, logger)
        initial_status = UuStatus(True, True, False, message="not accelerating target")
        target_status = UuStatus(True, True, True, message="target accelerating", active_game_name=config.target_game_name)

        with patch.object(controller, "get_status", side_effect=[initial_status, target_status]), patch.object(
            controller, "attach_window", return_value=UuStatus(True, True, None, message="attached")
        ), patch.object(controller, "_find_attached_window", return_value=object()), patch.object(
            controller, "_is_current_page_accelerating_any_game", return_value=True
        ), patch.object(controller, "_stop_current_page_acceleration") as stop_current_page, patch.object(
            controller, "_open_target_game_page"
        ) as open_target_game_page, patch.object(controller, "_wait_for_target_game_page", return_value=True), patch.object(
            controller, "_build_visual_status", return_value=UuStatus(True, True, False, message="target page opened")
        ), patch.object(controller, "_click_anchor") as click_anchor, patch.object(
            controller, "_wait_for_accelerating_state", return_value=True
        ):
            result = controller.ensure_target_accelerating(dry_run=False)

        stop_current_page.assert_called_once()
        open_target_game_page.assert_called_once()
        click_anchor.assert_called_once()
        self.assertTrue(result.accelerating_target)


if __name__ == "__main__":
    unittest.main()
