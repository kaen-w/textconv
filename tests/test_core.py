"""核心逻辑 + CLI 的单测：python -m unittest discover -s tests -v"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from textconv import config, core  # noqa: E402
from textconv.config import Config, DEFAULT_HOTKEYS  # noqa: E402


class SplitTests(unittest.TestCase):
    def test_whitespace(self):
        self.assertEqual(
            core.split_items("a b\nc\td  e", [core.WHITESPACE]), ["a", "b", "c", "d", "e"]
        )

    def test_chinese_enumeration_comma(self):
        self.assertEqual(
            core.split_items("苹果、香蕉、橘子", ["、"]), ["苹果", "香蕉", "橘子"]
        )

    def test_mixed_delimiters_and_trim(self):
        text = "a、 b, c ;d"
        self.assertEqual(
            core.split_items(text, [core.WHITESPACE, "、", ",", ";"]),
            ["a", "b", "c", "d"],
        )

    def test_dedupe_keeps_order(self):
        self.assertEqual(
            core.split_items("b,a,b,c,a", ["、", ","], dedupe=True), ["b", "a", "c"]
        )
        self.assertEqual(
            core.split_items("b,a,b,c,a", ["、", ","], dedupe=False),
            ["b", "a", "b", "c", "a"],
        )

    def test_empty_and_blank(self):
        self.assertEqual(core.split_items("", ["、"]), [])
        self.assertEqual(core.split_items("   \n\t ", [core.WHITESPACE]), [])

    def test_no_delimiter_keeps_whole_text(self):
        self.assertEqual(core.split_items("  a b  ", []), ["a b"])
        self.assertEqual(core.split_items("   ", []), [])

    def test_custom_multi_char_delimiter(self):
        self.assertEqual(core.split_items("a::b::c", ["::"], dedupe=False), ["a", "b", "c"])


class FormatTests(unittest.TestCase):
    def test_sql(self):
        self.assertEqual(core.convert("a、b", "sql", ["、"]), "('a', 'b')")
        self.assertEqual(core.convert("", "sql", ["、"]), "()")

    def test_sql_escapes_single_quote(self):
        self.assertEqual(core.convert("O'Brien、x", "sql", ["、"]), "('O''Brien', 'x')")

    def test_python_tuple(self):
        self.assertEqual(core.convert("a、b", "tuple", ["、"]), "('a', 'b')")
        # 单元素元组要带逗号，和原 GUI 一致
        self.assertEqual(core.convert("a", "tuple", ["、"]), "('a',)")
        self.assertEqual(core.convert("", "tuple", ["、"]), "()")

    def test_python_tuple_escapes(self):
        self.assertEqual(core.convert("a'b、c\\d", "tuple", ["、"]), "('a\\'b', 'c\\\\d')")

    def test_python_list(self):
        self.assertEqual(core.convert("a、b", "list", ["、"]), "['a', 'b']")
        self.assertEqual(core.convert("", "list", ["、"]), "[]")

    def test_json(self):
        self.assertEqual(core.convert("苹果、香蕉", "json", ["、"]), '["苹果", "香蕉"]')
        self.assertEqual(core.convert("", "json", ["、"]), "[]")

    def test_excel_paste_single_column(self):
        # 单列也按“粘贴原样”：一个值一行
        self.assertEqual(core.convert("a、b、c", "excel", ["、"]), "a\nb\nc")

    def test_excel_column(self):
        self.assertEqual(core.convert("a、b、c", "column", ["、"]), "a\nb\nc")

    def test_unknown_format(self):
        with self.assertRaises(core.FormatError):
            core.convert("a", "nope", ["、"])

    def test_default_delimiters_cover_common_chinese(self):
        text = "苹果、香蕉,橘子;葡萄，西瓜；"
        self.assertEqual(
            core.split_items(text, core.DEFAULT_DELIMITERS),
            ["苹果", "香蕉", "橘子", "葡萄", "西瓜"],
        )


class ConfigTests(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            cfg = Config()
            cfg.delimiters = [core.WHITESPACE, "、"]
            cfg.custom_delimiters = ["｜"]
            cfg.dedupe = False
            cfg.hotkeys["sql"] = "ctrl+alt+cmd+1"
            cfg.save(path)

            loaded = Config.load(path)
            self.assertEqual(loaded.delimiters, [core.WHITESPACE, "、"])
            self.assertEqual(loaded.custom_delimiters, ["｜"])
            self.assertFalse(loaded.dedupe)
            self.assertEqual(loaded.hotkeys["sql"], "ctrl+alt+cmd+1")

    def test_all_delimiters_dedupes(self):
        cfg = Config()
        cfg.delimiters = ["、", "、", core.WHITESPACE]
        cfg.custom_delimiters = [",", "、", "|"]
        self.assertEqual(cfg.all_delimiters, ["、", core.WHITESPACE, ",", "|"])

    def test_toggle_delimiter(self):
        cfg = Config()
        cfg.set_delimiter("|", True)
        self.assertTrue(cfg.is_delimiter_enabled("|"))
        cfg.toggle_delimiter("|")
        self.assertFalse(cfg.is_delimiter_enabled("|"))

    def test_missing_file_uses_defaults(self):
        cfg = Config.load("/nonexistent/path/config.json")
        self.assertEqual(cfg.hotkeys, DEFAULT_HOTKEYS)
        self.assertTrue(cfg.dedupe)

    def test_broken_json_falls_back(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            fh.write("{ not json")
            path = fh.name
        try:
            cfg = Config.load(path)
            self.assertIsNotNone(cfg.load_error)
            self.assertTrue(cfg.dedupe)
        finally:
            os.unlink(path)


class CliTests(unittest.TestCase):
    def _run(self, args, stdin="", env_extra=None):
        env = dict(os.environ)
        env["PYTHONPATH"] = ROOT
        env["TEXTCONV_HOME"] = tempfile.mkdtemp()
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            [sys.executable, "-m", "textconv.cli", *args],
            input=stdin,
            text=True,
            capture_output=True,
            env=env,
            cwd=ROOT,
        )

    def test_stdin_to_sql(self):
        result = self._run(["sql", "--delim", "、"], stdin="苹果、香蕉")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "('苹果', '香蕉')")

    def test_no_dedupe_flag(self):
        result = self._run(["sql", "--delim", "、", "--no-dedupe"], stdin="a、a")
        self.assertEqual(result.stdout.strip(), "('a', 'a')")

    def test_dedupe_flag(self):
        result = self._run(["sql", "--delim", "、", "--dedupe"], stdin="a、a、b")
        self.assertEqual(result.stdout.strip(), "('a', 'b')")

    def test_list_formats(self):
        result = self._run(["--formats"])
        self.assertIn("sql", result.stdout)
        self.assertIn("column", result.stdout)

    def test_bad_format(self):
        result = self._run(["nope"], stdin="a")
        self.assertEqual(result.returncode, 2)
        self.assertIn("未知格式", result.stderr)


if __name__ == "__main__":
    unittest.main()

class PlatformTests(unittest.TestCase):
    def test_windows_config_dir_uses_appdata(self):
        env = {k: v for k, v in os.environ.items() if k != "TEXTCONV_HOME"}
        env["APPDATA"] = r"C:\Users\me\AppData\Roaming"
        with mock.patch.dict(os.environ, env, clear=True), mock.patch("sys.platform", "win32"):
            path = config.app_dir()
        self.assertTrue(path.endswith("TextConv"))
        self.assertIn("Roaming", path)

    def test_windows_hotkeys_use_ctrl_alt_shift(self):
        with mock.patch("sys.platform", "win32"):
            keys = config.default_hotkeys()
        self.assertEqual(keys["sql"], "ctrl+alt+shift+s")
        self.assertEqual(keys["column"], "ctrl+alt+shift+k")

    def test_mac_hotkeys_use_cmd(self):
        with mock.patch("sys.platform", "darwin"):
            keys = config.default_hotkeys()
        self.assertEqual(keys["sql"], "ctrl+alt+cmd+s")

    def test_windows_state_and_config_share_dir(self):
        env = {k: v for k, v in os.environ.items() if k != "TEXTCONV_HOME"}
        env["APPDATA"] = r"C:\Users\me\AppData\Roaming"
        with mock.patch.dict(os.environ, env, clear=True), mock.patch("sys.platform", "win32"):
            self.assertEqual(
                os.path.dirname(config.config_path()), os.path.dirname(config.state_path())
            )


class WinHotkeyFormatTests(unittest.TestCase):
    def test_normalize(self):
        from textconv.win_hotkeys import normalize_combo

        self.assertEqual(normalize_combo("Ctrl + Alt + Shift + S"), "ctrl+alt+shift+s")
        self.assertEqual(normalize_combo("cmd+opt+s"), "windows+alt+s")

    def test_describe(self):
        from textconv.win_hotkeys import describe_combo

        self.assertEqual(describe_combo("ctrl+alt+shift+s"), "Ctrl+Alt+Shift+S")
        self.assertEqual(describe_combo(""), "")

    def test_validate_without_keyboard_lib(self):
        from textconv.win_hotkeys import validate_combo

        ok, error = validate_combo("")
        self.assertFalse(ok)
        self.assertTrue(error)


if __name__ == "__main__":
    unittest.main()

class FileConvTests(unittest.TestCase):
    """右键文件转换：内容读取（含 GBK）+ 写入剪贴板。"""

    def _run(self, content, encoding, fmt="sql"):
        from textconv import fileconv

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "sample.txt")
        with open(path, "wb") as fh:
            fh.write(content.encode(encoding))

        shown = []
        original_toast = fileconv._toast
        fileconv._toast = lambda message, *a, **k: shown.append(message)
        try:
            with mock.patch.dict(os.environ, {"TEXTCONV_HOME": tmp.name}), \
                    mock.patch.object(fileconv.clipboard, "set_text", return_value=True) as setter:
                code = fileconv.main([fmt, path])
        finally:
            fileconv._toast = original_toast
        return code, setter, shown

    def test_utf8_file(self):
        code, setter, shown = self._run("苹果、香蕉、橘子", "utf-8")
        self.assertEqual(code, 0)
        self.assertEqual(setter.call_args[0][0], "('苹果', '香蕉', '橘子')")
        self.assertIn("已复制", shown[-1])

    def test_gbk_file(self):
        code, setter, _ = self._run("甲、乙、丙", "gbk")
        self.assertEqual(code, 0)
        self.assertEqual(setter.call_args[0][0], "('甲', '乙', '丙')")

    def test_json_format(self):
        code, setter, _ = self._run("a、b", "utf-8", fmt="json")
        self.assertEqual(code, 0)
        self.assertEqual(setter.call_args[0][0], '["a", "b"]')

    def test_binary_file_is_refused(self):
        from textconv import fileconv

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "blob.bin")
        with open(path, "wb") as fh:
            fh.write(bytes(range(256)) * 8)

        shown = []
        original = fileconv._toast
        fileconv._toast = lambda message, *a, **k: shown.append(message)
        try:
            with mock.patch.dict(os.environ, {"TEXTCONV_HOME": tmp.name}), \
                    mock.patch.object(fileconv.clipboard, "set_text", return_value=True) as setter:
                code = fileconv.main(["sql", path])
        finally:
            fileconv._toast = original
        self.assertEqual(code, 1)
        setter.assert_not_called()
        self.assertIn("不是文本", shown[-1])

    def test_missing_file(self):
        from textconv import fileconv

        original = fileconv._toast
        fileconv._toast = lambda *a, **k: None
        try:
            code = fileconv.main(["sql", "/definitely/not/here.txt"])
        finally:
            fileconv._toast = original
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()

class RepeatGuardTests(unittest.TestCase):
    """连续按热键不能把引号越转越多。"""

    def test_first_conversion(self):
        source = core.resolve_source_text("a、b", None, None)
        self.assertEqual(source, "a、b")

    def test_second_press_reuses_original_input(self):
        first = core.convert("a、b", "sql", delimiters=["、"])
        source = core.resolve_source_text(first, "a、b", first)
        self.assertEqual(source, "a、b")
        self.assertEqual(core.convert(source, "sql", delimiters=["、"]), first)

    def test_new_copy_is_respected(self):
        first = core.convert("a、b", "sql", delimiters=["、"])
        source = core.resolve_source_text("x、y", "a、b", first)
        self.assertEqual(source, "x、y")

    def test_switching_format_uses_original_input(self):
        first = core.convert("a、b", "sql", delimiters=["、"])
        source = core.resolve_source_text(first, "a、b", first)
        self.assertEqual(core.convert(source, "json", delimiters=["、"]), '["a", "b"]')

    def test_ten_presses_stay_stable(self):
        last_input, last_output = None, None
        for _ in range(10):
            source = core.resolve_source_text(last_output or "a、b", last_input, last_output)
            last_input = source
            last_output = core.convert(source, "sql", delimiters=core.DEFAULT_DELIMITERS)
        self.assertEqual(last_output, "('a', 'b')")


if __name__ == "__main__":
    unittest.main()

class TableModeTests(unittest.TestCase):
    """从 Excel 复制多列：行是记录，保持粘贴原样，去重按整行。"""

    SAMPLE = "PG2203-M-FBA\tB08QRTTK6W\r\nPG2203-M-FBA\tB08QRTTK6W\r\n"

    def test_row_dedupe_like_paste(self):
        # 用户给的例子：两行完全相同，去重后只剩一行
        self.assertEqual(core.convert(self.SAMPLE, "excel", dedupe=True),
                         "PG2203-M-FBA\tB08QRTTK6W")

    def test_dedupe_off_keeps_both_rows(self):
        self.assertEqual(core.convert(self.SAMPLE, "excel", dedupe=False),
                         "PG2203-M-FBA\tB08QRTTK6W\nPG2203-M-FBA\tB08QRTTK6W")

    def test_crlf_and_trailing_blank_lines(self):
        text = "a\t1\r\n\r\nb\t2\r\n"
        self.assertEqual(core.convert(text, "excel"), "a\t1\nb\t2")

    def test_sql_emits_row_tuples(self):
        text = "a\t1\nb\t2"
        self.assertEqual(core.convert(text, "sql"), "('a', '1'),\n('b', '2')")

    def test_json_emits_array_of_arrays(self):
        text = "a\t1\nb\t2"
        self.assertEqual(core.convert(text, "json"), '[["a", "1"], ["b", "2"]]')

    def test_tuple_emits_tuple_of_tuples(self):
        text = "a\t1\nb\t2"
        self.assertEqual(core.convert(text, "tuple"), "(('a', '1'), ('b', '2'))")
        self.assertEqual(core.convert("a\t1", "tuple"), "(('a', '1'),)")

    def test_list_emits_list_of_lists(self):
        text = "a\t1\nb\t2"
        self.assertEqual(core.convert(text, "list"), "[['a', '1'], ['b', '2']]")

    def test_short_row_keeps_fewer_cells(self):
        text = "a\t1\nb"
        self.assertEqual(core.convert(text, "sql"), "('a', '1'),\n('b')")

    def test_column_takes_first_column(self):
        text = "a\t1\nb\t2"
        self.assertEqual(core.convert(text, "column"), "a\nb")

    def test_single_column_unchanged(self):
        # 没有 Tab 就不是表格，行为必须和以前完全一致
        self.assertEqual(core.convert("A001\nA002\nA001", "sql"), "('A001', 'A002')")
        self.assertEqual(core.convert("苹果、香蕉", "sql", delimiters=["、"]),
                         "('苹果', '香蕉')")

    def test_empty_table(self):
        self.assertEqual(core.convert("\t\t\n\t", "excel"), "")
        self.assertEqual(core.convert("\t\t\n\t", "sql"), "()")

    def test_partial_duplicate_rows(self):
        text = "a\t1\na\t2\na\t1"
        self.assertEqual(core.convert(text, "excel", dedupe=True), "a\t1\na\t2")


if __name__ == "__main__":
    unittest.main()
