"""Windows 快捷键解析的单元测试（纯函数，任何平台都能跑）。"""

import unittest

from textconv.win_hotkeys import describe_combo, normalize_combo, parse_combo, validate_combo

CTRL, ALT, SHIFT, WIN = 0x0002, 0x0001, 0x0004, 0x0008


class NormalizeTest(unittest.TestCase):
    def test_aliases(self):
        self.assertEqual(normalize_combo("Control + Opt + Cmd + S"), "ctrl+alt+windows+s")

    def test_describe(self):
        self.assertEqual(describe_combo("ctrl+alt+shift+s"), "Ctrl+Alt+Shift+S")


class ParseComboTest(unittest.TestCase):
    def test_letter(self):
        self.assertEqual(parse_combo("ctrl+alt+shift+s"), (CTRL | ALT | SHIFT, 0x53))

    def test_digit(self):
        self.assertEqual(parse_combo("ctrl+alt+1"), (CTRL | ALT, 0x31))

    def test_function_key(self):
        self.assertEqual(parse_combo("ctrl+f12"), (CTRL, 0x7B))

    def test_named_key(self):
        self.assertEqual(parse_combo("alt+space"), (ALT, 0x20))

    def test_win_modifier(self):
        self.assertEqual(parse_combo("cmd+shift+p"), (WIN | SHIFT, 0x50))

    def test_requires_modifier(self):
        with self.assertRaises(ValueError):
            parse_combo("s")

    def test_requires_key(self):
        with self.assertRaises(ValueError):
            parse_combo("ctrl+alt")

    def test_unknown_key(self):
        with self.assertRaises(ValueError):
            parse_combo("ctrl+alt+shift+?")

    def test_two_keys(self):
        with self.assertRaises(ValueError):
            parse_combo("ctrl+a+b")


class ValidateTest(unittest.TestCase):
    def test_valid(self):
        ok, error = validate_combo("ctrl+alt+shift+k")
        self.assertTrue(ok)
        self.assertEqual(error, "")

    def test_empty(self):
        ok, error = validate_combo("")
        self.assertFalse(ok)
        self.assertTrue(error)


if __name__ == "__main__":
    unittest.main()
