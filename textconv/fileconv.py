"""资源管理器右键菜单用：读取文件 → 转成目标格式 → 复制到剪贴板。

由注册表里的右键菜单调用：
    pythonw -m textconv.fileconv sql "%1"
没有控制台窗口（pythonw），所以用右下角的小提示条给反馈。
"""

from __future__ import annotations

import logging
import os
import sys

from . import clipboard, core
from .config import Config, app_dir

log = logging.getLogger("textconv.fileconv")

MAX_BYTES = 8 * 1024 * 1024  # 再大就不当文本处理了
ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "utf-16", "latin-1")


def _looks_binary(text: str) -> bool:
    """解码后仍有大量控制字符 / NUL，基本就是二进制文件。"""
    sample = text[:4096]
    if not sample:
        return False
    if "\x00" in sample:
        return True
    controls = sum(
        1 for ch in sample if ord(ch) < 32 and ch not in "\t\n\r\f"
    )
    return controls / len(sample) > 0.02


def read_text(path: str) -> str:
    size = os.path.getsize(path)
    if size > MAX_BYTES:
        raise ValueError(f"文件太大（{size / 1024 / 1024:.1f} MB），只处理 8 MB 以内的文本")
    with open(path, "rb") as fh:
        raw = fh.read()
    for encoding in ENCODINGS:
        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        if _looks_binary(text):
            raise ValueError("看起来不是文本文件")
        return text
    raise ValueError("识别不了这个文件的编码，可能不是文本")


def _toast(message: str, seconds: float = 1.6) -> None:
    """右下角浮出一行提示，自动消失；失败就只响一声。"""
    try:
        import tkinter as tk

        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        try:
            root.attributes("-alpha", 0.95)
        except Exception:
            pass
        label = tk.Label(
            root,
            text=message,
            font=("Microsoft YaHei UI", 11),
            bg="#2f6bff",
            fg="white",
            padx=16,
            pady=10,
        )
        label.pack()
        root.update_idletasks()
        width = root.winfo_width()
        height = root.winfo_height()
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        root.geometry(f"+{screen_w - width - 40}+{screen_h - height - 80}")
        root.after(int(seconds * 1000), root.destroy)
        root.mainloop()
    except Exception:
        log.exception("提示条失败")
        _beep()


def _beep() -> None:
    try:
        import winsound

        winsound.MessageBeep(0x00000040)
    except Exception:
        pass


def main(argv=None) -> int:
    try:
        os.makedirs(app_dir(), exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
            filename=os.path.join(app_dir(), "fileconv.log"),
        )
    except Exception:
        pass

    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 2:
        print("用法: python -m textconv.fileconv <格式> <文件>", file=sys.stderr)
        return 2

    fmt_key, path = argv[0], argv[1]
    if not os.path.isfile(path):
        _toast("不是文件，跳过了")
        return 1

    config = Config.load()
    try:
        text = read_text(path)
        result = core.convert(
            text, fmt_key, delimiters=config.all_delimiters, dedupe=config.dedupe
        )
    except ValueError as exc:
        _toast(f"跳过：{exc}"[:80])
        return 1
    except Exception as exc:
        log.exception("转换失败")
        _toast(f"转换失败：{exc}"[:80])
        return 1

    clipboard.set_text(result)
    if config.play_sound:
        _beep()
    label = core.get_format(fmt_key).label
    _toast(f"✓ 已复制 {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
