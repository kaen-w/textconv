"""GUI 层单测：设置窗口保存逻辑 + 快捷键解析。

需要 macOS 图形会话；没有 AppKit 时自动跳过。
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    from AppKit import NSApplication

    HAVE_APPKIT = True
except Exception:  # pragma: no cover
    HAVE_APPKIT = False

from textconv.config import Config  # noqa: E402
from textconv.hotkeys import (  # noqa: E402
    FLAG_CMD,
    FLAG_CONTROL,
    FLAG_OPTION,
    HotKeyError,
    describe_combo,
    parse_combo,
)


class HotkeyParseTests(unittest.TestCase):
    def test_parse(self):
        keycode, modifiers = parse_combo("ctrl+alt+cmd+s")
        self.assertEqual(keycode, 1)  # S
        self.assertEqual(modifiers, FLAG_CONTROL | FLAG_OPTION | FLAG_CMD)

    def test_symbol_aliases(self):
        self.assertEqual(parse_combo("⌃⌥⌘S"), parse_combo("ctrl+alt+cmd+s"))

    def test_attribute_order_does_not_matter(self):
        self.assertEqual(parse_combo("cmd+ctrl+s"), parse_combo("ctrl+cmd+s"))

    def test_requires_modifier(self):
        with self.assertRaises(HotKeyError):
            parse_combo("s")

    def test_unknown_key(self):
        with self.assertRaises(HotKeyError):
            parse_combo("ctrl+alt+f13")

    def test_describe(self):
        self.assertEqual(describe_combo("ctrl+alt+cmd+s"), "⌃⌥⌘S")
        # 解析不了就原样返回，方便菜单里提示
        self.assertEqual(describe_combo("garbage"), "garbage")


@unittest.skipUnless(HAVE_APPKIT, "需要 macOS AppKit")
class SettingsWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = NSApplication.sharedApplication()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["TEXTCONV_HOME"] = self.tmp.name

    def tearDown(self):
        os.environ.pop("TEXTCONV_HOME", None)
        self.tmp.cleanup()

    def _make_window(self):
        from textconv.settings_window import SettingsWindow

        saved = {}
        window = SettingsWindow.alloc().initWithConfig_callback_(
            Config(), lambda cfg: saved.__setitem__("cfg", cfg)
        )
        return window, saved

    def test_save_writes_config_and_calls_back(self):
        window, saved = self._make_window()
        window._delimiter_buttons["、"].setState_(0)
        window._custom_field.setStringValue_("| ::")
        window._dedupe_box.setState_(0)
        window._auto_paste_box.setState_(0)
        window._hotkey_fields["sql"].setStringValue_("ctrl+alt+cmd+1")
        window.saveSettings_(None)

        path = os.path.join(self.tmp.name, "config.json")
        self.assertTrue(os.path.exists(path))
        loaded = Config.load(path)
        self.assertNotIn("、", loaded.delimiters)
        self.assertEqual(loaded.custom_delimiters, ["|", "::"])
        self.assertFalse(loaded.dedupe)
        self.assertFalse(loaded.auto_paste)
        self.assertEqual(loaded.hotkeys["sql"], "ctrl+alt+cmd+1")
        self.assertIn("cfg", saved)

    def test_whitespace_stays_first(self):
        window, _ = self._make_window()
        window._delimiter_buttons["、"].setState_(0)
        window.saveSettings_(None)
        loaded = Config.load(os.path.join(self.tmp.name, "config.json"))
        self.assertEqual(loaded.delimiters[0], "whitespace")

    def test_empty_hotkey_is_allowed(self):
        window, _ = self._make_window()
        window._hotkey_fields["sql"].setStringValue_("")
        window.saveSettings_(None)
        loaded = Config.load(os.path.join(self.tmp.name, "config.json"))
        self.assertEqual(loaded.hotkeys["sql"], "")


if __name__ == "__main__":
    unittest.main()
