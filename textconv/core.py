"""核心转换逻辑：把一段文本按分隔符切开，再渲染成 SQL / Excel / JSON / Python 等格式。

这一层是纯标准库，不依赖 macOS，方便单测和被 CLI、菜单栏 App、右键服务复用。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable, Iterable, List, Sequence

#: 特殊的“分隔符”，表示任意连续空白（空格 / 换行 / 制表符）
WHITESPACE = "whitespace"

#: 首次使用时默认开启的分隔符：空白、顿号、半角/全角逗号、半角/全角分号
DEFAULT_DELIMITERS: List[str] = [WHITESPACE, "、", ",", ";", "，", "；"]

#: 可以在设置界面里勾选的内置分隔符（顺序即展示顺序）
BUILTIN_DELIMITERS: List[tuple] = [
    (WHITESPACE, "空白 / 换行"),
    ("、", "顿号 、"),
    (",", "逗号 ,"),
    ("，", "全角逗号 ，"),
    (";", "分号 ;"),
    ("；", "全角分号 ；"),
    ("|", "竖线 |"),
    ("/", "斜杠 /"),
]


class FormatError(ValueError):
    """未知的输出格式。"""


def _py_escape(text: str) -> str:
    """转义为 Python 单引号字符串字面量内部可用的文本。"""
    return (
        text.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )


def _sql_escape(text: str) -> str:
    """SQL 标准做法：单引号翻倍。"""
    return text.replace("'", "''")


@dataclass(frozen=True)
class Format:
    key: str
    label: str          # 界面里的格式名
    action: str         # 菜单 / 服务里的动作名
    render: Callable[[Sequence[str]], str]
    hint: str = ""      # 菜单里显示的示例


def _render_sql(items: Sequence[str]) -> str:
    return "(" + ", ".join("'" + _sql_escape(i) + "'" for i in items) + ")"


def _render_tuple(items: Sequence[str]) -> str:
    if not items:
        return "()"
    body = ", ".join("'" + _py_escape(i) + "'" for i in items)
    return "(" + body + ",)" if len(items) == 1 else "(" + body + ")"


def _render_list(items: Sequence[str]) -> str:
    return "[" + ", ".join("'" + _py_escape(i) + "'" for i in items) + "]"


def _render_json(items: Sequence[str]) -> str:
    return json.dumps(list(items), ensure_ascii=False)


def _render_excel(items: Sequence[str]) -> str:
    # 单列用空格连接：Excel 的筛选搜索框是按空格分隔做多值筛选的
    # （要往单元格里一列一列贴，用「Excel 一列」格式）
    return " ".join(items)


def _render_column(items: Sequence[str]) -> str:
    # 一列一个值：换行分隔，可以直接粘进一列单元格
    return "\n".join(items)


FORMATS: List[Format] = [
    Format("sql", "SQL IN 子句", "SQL IN 子句", _render_sql, "('a', 'b')"),
    Format("excel", "Excel 粘贴", "Excel 粘贴", _render_excel, "空格分隔，多列保留表格"),
    Format("json", "JSON 数组", "JSON 数组", _render_json, '["a", "b"]'),
    Format("tuple", "Python 元组", "Python 元组", _render_tuple, "('a', 'b')"),
    Format("list", "Python 列表", "Python 列表", _render_list, "['a', 'b']"),
    Format("column", "Excel 一列", "Excel 一列", _render_column, "a\\nb\\nc"),
]

FORMAT_BY_KEY = {f.key: f for f in FORMATS}


def get_format(key: str) -> Format:
    try:
        return FORMAT_BY_KEY[key]
    except KeyError:
        raise FormatError(
            f"未知格式 {key!r}，可选：{', '.join(f.key for f in FORMATS)}"
        ) from None


def build_pattern(delimiters: Iterable[str]) -> "re.Pattern[str] | None":
    """把分隔符列表编译成一个正则；空白分隔符会展开成 ``\\s+``。"""
    parts = []
    for delim in delimiters:
        if delim == WHITESPACE:
            parts.append(r"\s+")
        elif delim:
            parts.append(re.escape(delim))
    if not parts:
        return None
    return re.compile("|".join(parts))


def split_items(
    text: str,
    delimiters: Iterable[str] = DEFAULT_DELIMITERS,
    dedupe: bool = True,
) -> List[str]:
    """按分隔符切分文本，去掉空项，可选保持顺序去重。"""
    text = text or ""
    pattern = build_pattern(delimiters)
    if pattern is None:
        items = [text.strip()] if text.strip() else []
    else:
        items = [part.strip() for part in pattern.split(text)]
        items = [part for part in items if part]
    if dedupe:
        items = list(dict.fromkeys(items))
    return items


def resolve_source_text(
    clipboard_text: str,
    last_input: "str | None",
    last_output: "str | None",
) -> str:
    """决定这次要转换的源文本。

    转换结果会被写回剪贴板，所以连续按两次时，第二次读到的就是上次的结果。
    如果直接拿结果再转一次，SQL 的单引号会被翻倍、越转越多引号。
    这里记住上次的“原始输入”，发现剪贴板正是上次的输出时就换回原始输入。
    """
    if last_output is not None and last_input is not None and clipboard_text == last_output:
        return last_input
    return clipboard_text


def parse_table(text: str) -> "List[List[str]] | None":
    """把 Excel 复制出来的内容识别成表格（Tab 分列、换行分行）。

    没有 Tab 就不是表格，返回 None，调用方继续走普通文本逻辑。
    """
    if "\t" not in (text or ""):
        return None
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    rows = [line.split("\t") for line in normalized.split("\n")]
    # 整行都是空白的不算
    rows = [row for row in rows if any(cell.strip() for cell in row)]
    return rows


def _dedupe_rows(rows: "List[List[str]]") -> "List[List[str]]":
    """按整行去重，保持顺序。"""
    seen = set()
    result = []
    for row in rows:
        key = tuple(row)
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def _render_table(rows: "List[List[str]]", format_key: str, dedupe: bool) -> str:
    """表格模式：一行是一条记录。"""
    fmt = get_format(format_key)
    if not rows:
        return fmt.render([])

    if dedupe:
        rows = _dedupe_rows(rows)

    if format_key == "excel":
        # 保持“粘贴原样”：行内 Tab、行间换行
        return "\n".join("\t".join(row) for row in rows)

    if format_key == "column":
        values = [row[0] for row in rows]
        if dedupe:
            values = list(dict.fromkeys(values))
        return "\n".join(values)

    if format_key == "sql":
        return ",\n".join(_render_sql(row) for row in rows)

    if format_key == "json":
        return json.dumps([list(row) for row in rows], ensure_ascii=False)

    if format_key == "tuple":
        body = ", ".join(_render_tuple(row) for row in rows)
        return "(" + body + ",)" if len(rows) == 1 else "(" + body + ")"

    if format_key == "list":
        return "[" + ", ".join(_render_list(row) for row in rows) + "]"

    return fmt.render(["\t".join(row) for row in rows])


def convert(
    text: str,
    format_key: str,
    delimiters: Iterable[str] = DEFAULT_DELIMITERS,
    dedupe: bool = True,
) -> str:
    """一步到位：文本 -> 目标格式字符串。

    多列粘贴（含 Tab）走表格模式：行是记录，去重按整行；
    单列/纯文本仍按分隔符切分，行为和以前一致。
    """
    fmt = get_format(format_key)
    table = parse_table(text)
    if table is not None:
        return _render_table(table, format_key, dedupe)
    return fmt.render(split_items(text, delimiters=delimiters, dedupe=dedupe))
