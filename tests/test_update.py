"""更新检查的纯逻辑测试（不联网）。"""

import unittest

from textconv import update


class VersionTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(update.parse_version("v0.2.13"), (0, 2, 13))
        self.assertEqual(update.parse_version("0.2"), (0, 2))
        self.assertEqual(update.parse_version(""), (0,))

    def test_is_newer(self):
        self.assertTrue(update.is_newer("0.2.14", "0.2.13"))
        self.assertFalse(update.is_newer("0.2.13", "0.2.13"))
        self.assertFalse(update.is_newer("0.2.9", "0.2.13"))

    def test_due_for_check(self):
        self.assertTrue(update.due_for_check(""))
        self.assertTrue(update.due_for_check("2020-01-01T00:00:00"))
        self.assertFalse(update.due_for_check("2999-01-01T00:00:00"))


class AssetTest(unittest.TestCase):
    def _release(self):
        return update.Release(
            version="0.2.14",
            tag="v0.2.14",
            page_url="https://example.com",
            assets={
                "TextConv-0.2.14.dmg": "https://example.com/a.dmg",
                "TextConv-Setup-0.2.14.exe": "https://example.com/a.exe",
                "TextConv-Portable-0.2.14.exe": "https://example.com/p.exe",
            },
        )

    def test_windows_picks_setup(self):
        self.assertTrue(update.pick_asset(self._release(), "win32").endswith("a.exe"))

    def test_macos_picks_dmg(self):
        self.assertTrue(update.pick_asset(self._release(), "darwin").endswith("a.dmg"))

    def test_missing(self):
        empty = update.Release(version="1", tag="v1", page_url="", assets={})
        self.assertIsNone(update.pick_asset(empty, "win32"))


if __name__ == "__main__":
    unittest.main()
