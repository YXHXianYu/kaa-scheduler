"""Minimal Win32 window helpers used by the scheduler."""

import ctypes
import re
import time
from ctypes import wintypes
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

user32 = ctypes.windll.user32
SW_RESTORE = 9

try:
    from pywinauto import Desktop, keyboard, mouse
except ImportError:  # pragma: no cover - depends on local environment
    Desktop = None
    keyboard = None
    mouse = None

try:
    import win32clipboard
except ImportError:  # pragma: no cover - depends on local environment
    win32clipboard = None


@dataclass
class WindowInfo:
    """Simple window descriptor returned by the Win32 helpers."""

    hwnd: int
    title: str


@dataclass(frozen=True)
class WindowRect:
    """Screen-space rectangle for one attached window."""

    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


def _get_window_text(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def list_visible_windows() -> List[WindowInfo]:
    """Return all visible windows with non-empty titles."""

    windows: List[WindowInfo] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_proc(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        title = _get_window_text(hwnd)
        if title:
            windows.append(WindowInfo(hwnd=hwnd, title=title))
        return True

    user32.EnumWindows(enum_proc, 0)
    return windows


def find_windows_by_title_contains(title_fragment: str) -> List[WindowInfo]:
    """Return visible windows whose title contains the given fragment."""

    needle = title_fragment.lower()
    return [window for window in list_visible_windows() if needle in window.title.lower()]


def find_first_window_by_title_contains(title_fragment: str) -> Optional[WindowInfo]:
    """Return the first matching window, if any."""

    matches = find_windows_by_title_contains(title_fragment)
    if not matches:
        return None
    return matches[0]


def find_first_window_by_title_contains_including_invisible(title_fragment: str) -> Optional[WindowInfo]:
    """Return the first matching window (visible or not), if any."""

    needle = title_fragment.lower()
    windows: List[WindowInfo] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_proc(hwnd: int, _lparam: int) -> bool:
        title = _get_window_text(hwnd)
        if title and needle in title.lower():
            windows.append(WindowInfo(hwnd=hwnd, title=title))
            return False  # stop at first match
        return True

    user32.EnumWindows(enum_proc, 0)
    return windows[0] if windows else None


def wait_for_window(title_fragment: str, timeout_seconds: int, poll_interval: float = 0.5) -> Optional[WindowInfo]:
    """Poll until a matching window appears or the timeout is reached."""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        window = find_first_window_by_title_contains(title_fragment)
        if window is not None:
            return window
        time.sleep(poll_interval)
    return None


WM_SYSCOMMAND = 0x0112
SC_RESTORE = 0xF120


def bring_window_to_front(window: WindowInfo) -> None:
    """Restore a window and try to move it to the foreground."""

    # Some applications (e.g., UU加速器) ignore the synchronous ShowWindow call
    # when minimized to the system tray. Use WM_SYSCOMMAND SC_RESTORE as a
    # more reliable way to bring the window back.
    if user32.IsIconic(window.hwnd):
        user32.SendMessageW(window.hwnd, WM_SYSCOMMAND, SC_RESTORE, 0)
    else:
        user32.ShowWindow(window.hwnd, SW_RESTORE)

    # AttachThreadInput is required to reliably call SetForegroundWindow from
    # a background process on Windows.
    foreground_hwnd = user32.GetForegroundWindow()
    foreground_thread = user32.GetWindowThreadProcessId(foreground_hwnd, None)
    target_thread = user32.GetWindowThreadProcessId(window.hwnd, None)

    if foreground_thread != target_thread:
        user32.AttachThreadInput(foreground_thread, target_thread, True)

    user32.SetForegroundWindow(window.hwnd)

    if foreground_thread != target_thread:
        user32.AttachThreadInput(foreground_thread, target_thread, False)


def get_window_rect(window: WindowInfo) -> WindowRect:
    """Return the outer bounds of the attached window."""

    rect = wintypes.RECT()
    if not user32.GetWindowRect(window.hwnd, ctypes.byref(rect)):
        raise RuntimeError("Failed to read the window bounds for hwnd=" + str(window.hwnd))
    return WindowRect(rect.left, rect.top, rect.right, rect.bottom)


def window_reference_point_to_screen(
    window: WindowInfo,
    x: int,
    y: int,
    reference_width: int,
    reference_height: int,
) -> Tuple[int, int]:
    """Map a point from a reference screenshot into screen coordinates."""

    rect = get_window_rect(window)
    screen_x = rect.left + round((x / reference_width) * rect.width)
    screen_y = rect.top + round((y / reference_height) * rect.height)
    return screen_x, screen_y


def click_window_reference_point(
    window: WindowInfo,
    x: int,
    y: int,
    reference_width: int,
    reference_height: int,
) -> None:
    """Click a point derived from the reference screenshot coordinates."""

    if mouse is None:
        raise RuntimeError("pywinauto mouse support is not available.")

    screen_point = window_reference_point_to_screen(window, x, y, reference_width, reference_height)
    try:
        mouse.click(button="left", coords=screen_point)
    except Exception as exc:
        raise RuntimeError(
            "Desktop mouse control is unavailable in the current session. "
            "Try running the scheduler from an interactive desktop session with input control permission."
        ) from exc


def send_foreground_keys(keys: str) -> None:
    """Send raw key strokes to the current foreground window."""

    if keyboard is None:
        raise RuntimeError("pywinauto keyboard support is not available.")
    keyboard.send_keys(keys, pause=0.02)


def send_foreground_text(text: str) -> None:
    """Send text to the current foreground window, preferring clipboard paste."""

    if keyboard is None:
        raise RuntimeError("pywinauto keyboard support is not available.")

    if not text:
        return

    if win32clipboard is not None:
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            keyboard.send_keys("^v", pause=0.02)
            return
        except Exception:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass

    keyboard.send_keys(text, pause=0.02, with_spaces=True)


def capture_window_image(window: WindowInfo):
    """Capture the current window into a Pillow image when available."""

    if Desktop is None:
        raise RuntimeError("pywinauto is not installed.")

    image = Desktop(backend="win32").window(handle=window.hwnd).capture_as_image()
    if image is None:
        raise RuntimeError("Window capture returned no image. Pillow may be missing.")
    return image


def is_uia_available() -> bool:
    """Return whether the optional UI Automation dependency is available."""

    return Desktop is not None


def _find_uia_window(title_fragment: str):
    if Desktop is None:
        return None

    win32_window = find_first_window_by_title_contains(title_fragment)
    if win32_window is None:
        return None
    return Desktop(backend="uia").window(handle=win32_window.hwnd)


def list_uia_control_names(title_fragment: str, limit: int = 100) -> List[str]:
    """Return readable UIA control names from the first matching window."""

    window = _find_uia_window(title_fragment)
    if window is None:
        return []

    names: List[str] = []
    seen = set()
    for control in window.descendants():
        name = ""
        try:
            name = control.window_text().strip()
        except Exception:
            name = ""
        if not name or name in seen:
            continue
        names.append(name)
        seen.add(name)
        if len(names) >= limit:
            break
    return names


def has_uia_control(title_fragment: str, control_title_fragment: str) -> bool:
    """Return whether the matching UIA window exposes a named control."""

    needle = control_title_fragment.lower()
    return any(needle in name.lower() for name in list_uia_control_names(title_fragment))


def click_uia_control(title_fragment: str, control_title_fragment: str) -> bool:
    """Click the first UIA control whose visible text contains the given fragment."""

    window = _find_uia_window(title_fragment)
    if window is None:
        return False

    needle = control_title_fragment.lower()
    for control in window.descendants():
        name = ""
        try:
            name = control.window_text().strip()
        except Exception:
            name = ""
        if not name or needle not in name.lower():
            continue
        try:
            control.click_input()
        except Exception:
            try:
                control.invoke()
            except Exception:
                return False
        return True
    return False


WM_SYSCOMMAND = 0x0112
SC_CLOSE = 0xF060


def close_window_by_title(title_fragment: str) -> Optional[WindowInfo]:
    """Close the first visible window whose title contains the given fragment."""

    window = find_first_window_by_title_contains(title_fragment)
    if window is None:
        return None
    user32.PostMessageW(window.hwnd, WM_SYSCOMMAND, SC_CLOSE, 0)
    return window


def close_window_by_title_predicate(predicate: Callable[[str], bool]) -> Optional[WindowInfo]:
    """Close the first visible window whose title passes the given predicate."""

    for window in list_visible_windows():
        if predicate(window.title):
            user32.PostMessageW(window.hwnd, WM_SYSCOMMAND, SC_CLOSE, 0)
            return window
    return None


SW_MINIMIZE = 6


def minimize_window_by_title(title_fragment: str) -> Optional[WindowInfo]:
    """Minimize the first visible window whose title contains the given fragment."""

    window = find_first_window_by_title_contains(title_fragment)
    if window is None:
        return None
    user32.ShowWindow(window.hwnd, SW_MINIMIZE)
    return window


def minimize_window_by_title_predicate(predicate: Callable[[str], bool]) -> Optional[WindowInfo]:
    """Minimize the first visible window whose title passes the given predicate."""

    for window in list_visible_windows():
        if predicate(window.title):
            user32.ShowWindow(window.hwnd, SW_MINIMIZE)
            return window
    return None
