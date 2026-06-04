"""UU process and window probe helpers."""

import re
import time
from dataclasses import dataclass
from logging import Logger
from typing import Optional, Tuple

from kaa_scheduler.config import AppConfig
from kaa_scheduler.models import UuStatus
from kaa_scheduler.infra.process import is_process_running, launch_process, wait_for_process_start
from kaa_scheduler.infra.window import (
    bring_window_to_front,
    capture_window_image,
    click_window_reference_point,
    click_uia_control,
    find_first_window_by_title_contains,
    has_uia_control,
    is_uia_available,
    list_uia_control_names,
    send_foreground_keys,
    send_foreground_text,
    wait_for_window,
)
from PIL import Image, ImageOps  # pyright: ignore[reportMissingImports]

REFERENCE_WIDTH = 1000
REFERENCE_HEIGHT = 688
TITLE_TEXT_REGION = (38, 220, 276, 320)
STOP_BUTTON_TEXT_REGION = (122, 326, 278, 368)
STOP_CONFIRM_DIALOG_TEXT_REGION = (354, 258, 640, 312)


@dataclass(frozen=True)
class UuAnchor:
    """One anchor point measured against the fixed UU window screenshot."""

    x: int
    y: int


SEARCH_BOX_ANCHOR = UuAnchor(826, 49)
SEARCH_FIRST_RESULT_ANCHOR = UuAnchor(809, 104)
ACTION_BUTTON_CLICK_ANCHOR = UuAnchor(221, 347)
STOP_CONFIRM_BUTTON_ANCHOR = UuAnchor(431, 455)
LANCZOS_RESAMPLE = getattr(Image, "Resampling", Image).LANCZOS


class UuController:
    """Encapsulate UU launch, attach and basic status probing."""

    _ocr_engine = None

    def __init__(self, config: AppConfig, logger: Logger) -> None:
        self.config = config
        self.logger = logger

    @classmethod
    def _get_ocr_engine(cls):
        if cls._ocr_engine is not None:
            return cls._ocr_engine
        try:
            from rapidocr_onnxruntime import RapidOCR  # pyright: ignore[reportMissingImports]
        except ImportError:  # pragma: no cover - depends on local environment
            return None
        cls._ocr_engine = RapidOCR()
        return cls._ocr_engine

    @staticmethod
    def _normalize_ocr_text(text: str) -> str:
        return re.sub(r"\s+", "", text).lower()

    def _is_target_game_title_text(self, text: Optional[str]) -> bool:
        if not text:
            return False
        normalized_text = self._normalize_ocr_text(text)
        normalized_target = self._normalize_ocr_text(self.config.target_game_name)
        return normalized_target in normalized_text

    def _has_stop_button_text(self, text: Optional[str]) -> bool:
        if not text:
            return False
        return "停止加速" in self._normalize_ocr_text(text)

    def _has_stop_confirm_dialog_text(self, text: Optional[str]) -> bool:
        if not text:
            return False
        normalized_text = self._normalize_ocr_text(text)
        return "其他游戏正在加速" in normalized_text

    def _find_attached_window(self):
        window = find_first_window_by_title_contains(self.config.uu_window_title)
        if window is None:
            raise RuntimeError("UU window is not attached.")
        return window

    def _crop_reference_region(self, image, region: Tuple[int, int, int, int]):
        left, top, right, bottom = region
        crop_left = min(max(round((left / REFERENCE_WIDTH) * image.width), 0), image.width)
        crop_top = min(max(round((top / REFERENCE_HEIGHT) * image.height), 0), image.height)
        crop_right = min(max(round((right / REFERENCE_WIDTH) * image.width), crop_left + 1), image.width)
        crop_bottom = min(max(round((bottom / REFERENCE_HEIGHT) * image.height), crop_top + 1), image.height)
        return image.crop((crop_left, crop_top, crop_right, crop_bottom))

    def _read_text_in_region(self, window, region: Tuple[int, int, int, int]) -> Optional[str]:
        ocr_engine = self._get_ocr_engine()
        if ocr_engine is None:
            return None

        try:
            import numpy  # pyright: ignore[reportMissingImports]
        except ImportError:  # pragma: no cover - depends on local environment
            return None

        image = capture_window_image(window)
        crop = self._crop_reference_region(image, region)
        grayscale_crop = crop.convert("L")
        prepared_crop = ImageOps.autocontrast(grayscale_crop).resize(
            (grayscale_crop.width * 2, grayscale_crop.height * 2),
            resample=LANCZOS_RESAMPLE,
        )

        ocr_result, _ = ocr_engine(numpy.array(prepared_crop))
        if not ocr_result:
            return None

        text_parts = []
        for item in ocr_result:
            if len(item) < 2:
                continue
            text = str(item[1]).strip()
            if text:
                text_parts.append(text)
        if not text_parts:
            return None
        return " ".join(text_parts)

    def _read_current_page_game_title(self, window) -> Optional[str]:
        title_text = self._read_text_in_region(window, TITLE_TEXT_REGION)
        self.logger.info("OCR current UU page title region: %s", title_text or "<none>")
        return title_text

    def _read_stop_button_text(self, window) -> Optional[str]:
        stop_button_text = self._read_text_in_region(window, STOP_BUTTON_TEXT_REGION)
        self.logger.info("OCR current UU stop button region: %s", stop_button_text or "<none>")
        return stop_button_text

    def _read_stop_confirm_dialog_text(self, window) -> Optional[str]:
        dialog_text = self._read_text_in_region(window, STOP_CONFIRM_DIALOG_TEXT_REGION)
        self.logger.info("OCR current UU stop confirm dialog region: %s", dialog_text or "<none>")
        return dialog_text

    def _is_current_page_accelerating_any_game(self, window) -> bool:
        stop_button_text = self._read_stop_button_text(window)
        return self._has_stop_button_text(stop_button_text)

    def _is_current_page_target_game(self, window) -> bool:
        title_text = self._read_current_page_game_title(window)
        return self._is_target_game_title_text(title_text)

    def _wait_for_current_page_stop_state(self, timeout_seconds: float = 8.0) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            window = find_first_window_by_title_contains(self.config.uu_window_title)
            if window is not None:
                try:
                    if not self._is_current_page_accelerating_any_game(window):
                        return True
                except RuntimeError:
                    pass
            time.sleep(0.5)
        return False

    def _stop_current_page_acceleration(self, window) -> None:
        self._click_anchor(window, ACTION_BUTTON_CLICK_ANCHOR)
        time.sleep(0.5)

        if self._has_stop_confirm_dialog(window):
            self._click_anchor(window, STOP_CONFIRM_BUTTON_ANCHOR)

        if not self._wait_for_current_page_stop_state():
            raise RuntimeError("The stop button was clicked, but UU still looks like it is accelerating the current game page.")

    def _build_visual_status(self, window) -> Optional[UuStatus]:
        title_text = self._read_current_page_game_title(window)

        if not self._is_target_game_title_text(title_text):
            return None

        if self._is_current_page_accelerating_any_game(window):
            return UuStatus(
                process_running=True,
                window_attached=True,
                accelerating_target=True,
                active_game_name=self.config.target_game_name,
                message="Detected the target game acceleration page through window image anchors.",
            )

        return UuStatus(
            process_running=True,
            window_attached=True,
            accelerating_target=False,
            active_game_name=self.config.target_game_name,
            message="Detected the target game page through window image anchors, but acceleration is not active.",
        )

    def _click_anchor(self, window, anchor: UuAnchor) -> None:
        try:
            click_window_reference_point(window, anchor.x, anchor.y, REFERENCE_WIDTH, REFERENCE_HEIGHT)
        except RuntimeError as exc:
            raise RuntimeError("Failed to click the UU image anchor: " + str(exc)) from exc

    def _has_stop_confirm_dialog(self, window) -> bool:
        dialog_text = self._read_stop_confirm_dialog_text(window)
        return self._has_stop_confirm_dialog_text(dialog_text)

    def _open_target_game_page(self) -> None:
        window = self._find_attached_window()
        bring_window_to_front(window)
        self._click_anchor(window, SEARCH_BOX_ANCHOR)
        time.sleep(0.2)
        send_foreground_keys("^a")
        time.sleep(0.1)
        send_foreground_keys("{BACKSPACE}")
        time.sleep(0.1)
        send_foreground_text(self.config.target_game_name)
        time.sleep(0.8)
        self._click_anchor(window, SEARCH_FIRST_RESULT_ANCHOR)

    def _wait_for_target_game_page(self, timeout_seconds: float = 8.0) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            window = find_first_window_by_title_contains(self.config.uu_window_title)
            if window is not None:
                try:
                    visual_status = self._build_visual_status(window)
                except RuntimeError:
                    visual_status = None
                if visual_status is not None:
                    return True
            time.sleep(0.5)
        return False

    def _wait_for_accelerating_state(self, timeout_seconds: float = 8.0) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            window = find_first_window_by_title_contains(self.config.uu_window_title)
            if window is not None:
                try:
                    visual_status = self._build_visual_status(window)
                except RuntimeError:
                    visual_status = None
                if visual_status is not None and visual_status.accelerating_target is True:
                    return True
            time.sleep(0.5)
        return False

    def _wait_for_stopped_state(self, timeout_seconds: float = 8.0) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            status = self.get_status()
            if status.window_attached and status.accelerating_target is not True:
                return True
            time.sleep(0.5)
        return False

    def ensure_started(self, dry_run: bool = False) -> UuStatus:
        """Ensure that UU is running, launching it if needed."""

        if is_process_running(self.config.uu_process_name):
            return self.get_status()

        if dry_run:
            message = "dry-run: skipped launching UU"
            self.logger.info(message)
            return UuStatus(False, False, None, message=message)

        if not self.config.uu_exe_path.exists():
            raise FileNotFoundError("UU executable was not found: " + str(self.config.uu_exe_path))

        launch_process([str(self.config.uu_exe_path)])
        self.logger.info("UU launch command issued.")

        if not wait_for_process_start(self.config.uu_process_name, timeout_seconds=15):
            raise RuntimeError("UU launch command was issued, but the process did not appear in time.")

        return self.get_status()

    def attach_window(
        self,
        timeout_seconds: int = 10,
        bring_to_front_flag: bool = True,
        require_window: bool = False,
    ) -> UuStatus:
        """Attach to the UU main window by title."""

        window = wait_for_window(self.config.uu_window_title, timeout_seconds)
        if window is None:
            if require_window:
                raise RuntimeError("UU window was not found.")
            return UuStatus(
                process_running=is_process_running(self.config.uu_process_name),
                window_attached=False,
                accelerating_target=None,
                message="UU window was not found.",
            )

        if bring_to_front_flag:
            bring_window_to_front(window)

        return UuStatus(
            process_running=True,
            window_attached=True,
            accelerating_target=None,
            message="Attached to UU window: " + window.title,
        )

    def get_status(self) -> UuStatus:
        """Return the current coarse-grained UU state."""

        process_running = is_process_running(self.config.uu_process_name)
        window = find_first_window_by_title_contains(self.config.uu_window_title)
        if not process_running:
            message = "UU process is not running."
        elif window is None:
            message = "UU process is running, but the main window was not found."
        else:
            message = "Target acceleration detection is not implemented yet."
        accelerating_target = None
        active_game_name = None

        if window is not None and is_uia_available():
            control_names = list_uia_control_names(self.config.uu_window_title, limit=120)
            has_stop_button = any("停止加速" in name for name in control_names)
            has_target_game = any(self.config.target_game_name in name for name in control_names)

            if has_stop_button and has_target_game:
                accelerating_target = True
                active_game_name = self.config.target_game_name
                message = "Detected target acceleration page through UI Automation."
            elif has_stop_button:
                message = "Detected an acceleration page, but the target game name was not confirmed."
            else:
                message = "UI Automation is available, but the target acceleration controls were not found yet."

        if window is not None:
            try:
                visual_status = self._build_visual_status(window)
            except RuntimeError:
                visual_status = None

            if visual_status is not None:
                accelerating_target = visual_status.accelerating_target
                active_game_name = visual_status.active_game_name
                message = visual_status.message

        return UuStatus(
            process_running=process_running,
            window_attached=window is not None,
            accelerating_target=accelerating_target,
            message=message,
            active_game_name=active_game_name,
        )

    def ensure_target_accelerating(self, dry_run: bool = False) -> UuStatus:
        """Ensure that UU is accelerating the target game."""

        status = self.get_status()
        if status.accelerating_target is True:
            return status

        if dry_run:
            message = "dry-run: skipped UU target acceleration workflow"
            self.logger.info(message)
            return UuStatus(status.process_running, status.window_attached, None, message=message)

        self.attach_window(require_window=True)
        window = self._find_attached_window()

        if self._is_current_page_accelerating_any_game(window) and not self._is_current_page_target_game(window):
            self.logger.info("Current UU page is already accelerating another game, stopping it before opening the target game page.")
            self._stop_current_page_acceleration(window)

        self._open_target_game_page()

        if not self._wait_for_target_game_page():
            raise RuntimeError("Failed to open the target game page in UU.")

        self.logger.info("Target game page opened, waiting 1 second for the page state to settle.")
        time.sleep(1.0)

        window = self._find_attached_window()
        visual_status = self._build_visual_status(window)
        if visual_status is None:
            raise RuntimeError("The target game page could not be verified after the UU search flow.")
        if visual_status.accelerating_target is True:
            return visual_status

        self._click_anchor(window, ACTION_BUTTON_CLICK_ANCHOR)

        if not self._wait_for_accelerating_state():
            raise RuntimeError("The target game page was opened, but UU did not enter the accelerating state in time.")

        return self.get_status()

    def stop_target_acceleration(self, dry_run: bool = False) -> UuStatus:
        """Stop the target acceleration session after kaa finishes."""

        status = self.get_status()
        if dry_run:
            message = "dry-run: skipped stopping UU acceleration"
            self.logger.info(message)
            return UuStatus(status.process_running, status.window_attached, status.accelerating_target, message=message)

        self.attach_window(require_window=True)

        window = self._find_attached_window()
        visual_status = self._build_visual_status(window)
        if visual_status is not None and visual_status.accelerating_target is not True:
            return visual_status

        if visual_status is None:
            self.logger.info(
                "Stop flow could not re-verify the current page, assuming UU is still on the target acceleration page."
            )

        self._stop_current_page_acceleration(window)

        if not self._wait_for_stopped_state():
            raise RuntimeError("The stop button was clicked, but UU still looks like it is accelerating the target game.")

        return UuStatus(
            process_running=status.process_running,
            window_attached=True,
            accelerating_target=False,
            active_game_name=self.config.target_game_name,
            message="Clicked the stop acceleration anchor on the target game page.",
        )
