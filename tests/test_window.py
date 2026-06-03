import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from kaa_scheduler.infra import window


class _FakeClipboard:
    CF_UNICODETEXT = 13

    def __init__(self) -> None:
        self.calls = []

    def OpenClipboard(self) -> None:
        self.calls.append(("OpenClipboard",))

    def EmptyClipboard(self) -> None:
        self.calls.append(("EmptyClipboard",))

    def SetClipboardText(self, text: str, clipboard_format: int) -> None:
        self.calls.append(("SetClipboardText", text, clipboard_format))

    def CloseClipboard(self) -> None:
        self.calls.append(("CloseClipboard",))


class _FakeKeyboard:
    def __init__(self) -> None:
        self.calls = []

    def send_keys(self, keys: str, pause: float = 0.0, with_spaces: bool = False) -> None:
        self.calls.append((keys, pause, with_spaces))


class WindowHelpersTests(unittest.TestCase):
    def test_send_foreground_text_uses_unicode_clipboard(self) -> None:
        fake_clipboard = _FakeClipboard()
        fake_keyboard = _FakeKeyboard()

        with patch.object(window, "win32clipboard", fake_clipboard), patch.object(window, "keyboard", fake_keyboard):
            window.send_foreground_text("学园偶像大师")

        self.assertIn(
            ("SetClipboardText", "学园偶像大师", fake_clipboard.CF_UNICODETEXT),
            fake_clipboard.calls,
        )
        self.assertEqual(fake_keyboard.calls, [("^v", 0.02, False)])


if __name__ == "__main__":
    unittest.main()