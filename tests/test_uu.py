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

    def test_stop_confirm_dialog_text_matcher(self) -> None:
        config = build_default_config(Path(__file__).resolve().parents[1])
        logger = logging.getLogger("test_uu_stop_confirm_text")
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())

        controller = UuController(config, logger)

        self.assertTrue(controller._has_stop_confirm_dialog_text("其他游戏正在加速，是否继续加速该游戏?"))
        self.assertFalse(controller._has_stop_confirm_dialog_text("确定"))

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

        with patch.object(
            controller, "_read_current_page_game_title", return_value="彩虹六号：围攻"
        ), patch.object(controller, "_is_current_page_accelerating_any_game", return_value=True):
            self.assertIsNone(controller._build_visual_status(object()))

        with patch.object(
            controller, "_read_current_page_game_title", return_value="学园偶像大师"
        ), patch.object(controller, "_is_current_page_accelerating_any_game", return_value=True):
            status = controller._build_visual_status(object())

        self.assertIsNotNone(status)
        assert status is not None
        self.assertTrue(status.accelerating_target)

    def test_build_visual_status_uses_negation_for_not_accelerating(self) -> None:
        config = build_default_config(Path(__file__).resolve().parents[1])
        logger = logging.getLogger("test_uu_visual_status_negation")
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())

        controller = UuController(config, logger)

        with patch.object(controller, "_read_current_page_game_title", return_value="学园偶像大师"), patch.object(
            controller, "_is_current_page_accelerating_any_game", return_value=False
        ):
            status = controller._build_visual_status(object())

        self.assertIsNotNone(status)
        assert status is not None
        self.assertFalse(status.accelerating_target)


if __name__ == "__main__":
    unittest.main()
