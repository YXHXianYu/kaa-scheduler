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

    def test_target_game_title_text_matcher(self) -> None:
        config = build_default_config(Path(__file__).resolve().parents[1])
        logger = logging.getLogger("test_uu_title_match")
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())

        controller = UuController(config, logger)

        self.assertTrue(controller._is_target_game_title_text("学园偶像大师"))
        self.assertTrue(controller._is_target_game_title_text(" 学园 偶像大师 "))
        self.assertFalse(controller._is_target_game_title_text("边狱公司"))

    def test_stop_button_text_matcher(self) -> None:
        config = build_default_config(Path(__file__).resolve().parents[1])
        logger = logging.getLogger("test_uu_stop_button_text")
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())

        controller = UuController(config, logger)

        self.assertTrue(controller._has_stop_button_text("停止加速"))
        self.assertTrue(controller._has_stop_button_text(" 停止 加速 "))
        self.assertFalse(controller._has_stop_button_text("启动游戏"))

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
        ), patch.object(controller, "_is_current_page_target_game", return_value=False
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

    def test_ensure_target_accelerating_does_not_stop_when_ocr_matches_target(self) -> None:
        config = build_default_config(Path(__file__).resolve().parents[1])
        logger = logging.getLogger("test_uu_keep_target")
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())

        controller = UuController(config, logger)
        initial_status = UuStatus(True, True, False, message="not accelerating target")
        target_status = UuStatus(True, True, True, message="target accelerating", active_game_name=config.target_game_name)

        with patch.object(controller, "get_status", side_effect=[initial_status, target_status]), patch.object(
            controller, "attach_window", return_value=UuStatus(True, True, None, message="attached")
        ), patch.object(controller, "_find_attached_window", return_value=object()), patch.object(
            controller, "_is_current_page_accelerating_any_game", return_value=True
        ), patch.object(controller, "_is_current_page_target_game", return_value=True), patch.object(
            controller, "_stop_current_page_acceleration"
        ) as stop_current_page, patch.object(controller, "_open_target_game_page") as open_target_game_page, patch.object(
            controller, "_wait_for_target_game_page", return_value=True
        ), patch.object(controller, "_build_visual_status", return_value=UuStatus(True, True, False, message="target page opened")), patch.object(
            controller, "_click_anchor"
        ) as click_anchor, patch.object(controller, "_wait_for_accelerating_state", return_value=True):
            result = controller.ensure_target_accelerating(dry_run=False)

        stop_current_page.assert_not_called()
        open_target_game_page.assert_called_once()
        click_anchor.assert_called_once()
        self.assertTrue(result.accelerating_target)

    def test_current_page_target_game_uses_ocr_only(self) -> None:
        config = build_default_config(Path(__file__).resolve().parents[1])
        logger = logging.getLogger("test_uu_target_confirmation")
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())

        controller = UuController(config, logger)

        with patch.object(controller, "_read_current_page_game_title", return_value="学园偶像大师"):
            self.assertTrue(controller._is_current_page_target_game(object()))

        with patch.object(controller, "_read_current_page_game_title", return_value="彩虹六号：围攻"):
            self.assertFalse(controller._is_current_page_target_game(object()))

    def test_build_visual_status_requires_target_title_ocr(self) -> None:
        config = build_default_config(Path(__file__).resolve().parents[1])
        logger = logging.getLogger("test_uu_visual_status_ocr")
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())

        controller = UuController(config, logger)

        with patch("kaa_scheduler.uu.capture_window_image", return_value=object()), patch.object(
            controller, "_read_current_page_game_title", return_value="彩虹六号：围攻"
        ), patch.object(controller, "_image_sample_rgb", side_effect=[(96, 108, 186), (96, 108, 186), (28, 33, 71), (28, 33, 71)]):
            self.assertIsNone(controller._build_visual_status(object()))

        with patch("kaa_scheduler.uu.capture_window_image", return_value=object()), patch.object(
            controller, "_read_current_page_game_title", return_value="学园偶像大师"
        ), patch.object(controller, "_image_sample_rgb", side_effect=[(96, 108, 186), (96, 108, 186), (28, 33, 71), (28, 33, 71)]):
            status = controller._build_visual_status(object())

        self.assertIsNotNone(status)
        assert status is not None
        self.assertTrue(status.accelerating_target)


if __name__ == "__main__":
    unittest.main()
