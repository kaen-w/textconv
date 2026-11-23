"""Windows 设置窗口（tkinter，独立进程启动）。"""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import messagebox, ttk

from .config import Config
from .core import BUILTIN_DELIMITERS, WHITESPACE
from .win_hotkeys import describe_combo, normalize_combo, validate_combo

HOTKEY_ROWS = [
    ("sql", "SQL IN 子句"),
    ("excel", "Excel 粘贴"),
    ("json", "JSON 数组"),
    ("tuple", "Python 元组"),
    ("list", "Python 列表"),
    ("column", "Excel 一列"),
]


class SettingsWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.config = Config.load()

        root.title("TextConv 设置")
        root.resizable(False, False)

        frame = ttk.Frame(root, padding=16)
        frame.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frame, text="分隔符：粘贴的文本会按这些符号切开", font=("", 11, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 8)
        )

        self.delimiter_vars: dict[str, tk.BooleanVar] = {}
        for index, (delimiter, title) in enumerate(BUILTIN_DELIMITERS):
            var = tk.BooleanVar(value=self.config.is_delimiter_enabled(delimiter))
            self.delimiter_vars[delimiter] = var
            row, col = divmod(index, 2)
            ttk.Checkbutton(frame, text=title, variable=var).grid(
                row=1 + row, column=col * 2, columnspan=2, sticky="w", pady=2
            )

        ttk.Label(frame, text="自定义分隔符（用空格分隔，可填多个字符）").grid(
            row=6, column=0, columnspan=4, sticky="w", pady=(12, 2)
        )
        self.custom_var = tk.StringVar(value=" ".join(self.config.custom_delimiters))
        ttk.Entry(frame, textvariable=self.custom_var, width=40).grid(
            row=7, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(frame, text="例如：·  ::  |").grid(row=7, column=2, columnspan=2, sticky="w")

        ttk.Label(frame, text="选项", font=("", 11, "bold")).grid(
            row=8, column=0, columnspan=4, sticky="w", pady=(16, 6)
        )
        self.dedupe_var = tk.BooleanVar(value=self.config.dedupe)
        self.auto_paste_var = tk.BooleanVar(value=self.config.auto_paste)
        self.sound_var = tk.BooleanVar(value=self.config.play_sound)
        ttk.Checkbutton(frame, text="去重（保持顺序）", variable=self.dedupe_var).grid(
            row=9, column=0, columnspan=2, sticky="w"
        )
        ttk.Checkbutton(frame, text="转换后自动粘贴", variable=self.auto_paste_var).grid(
            row=9, column=2, columnspan=2, sticky="w"
        )
        ttk.Checkbutton(frame, text="提示音", variable=self.sound_var).grid(
            row=10, column=0, columnspan=2, sticky="w", pady=(4, 0)
        )

        ttk.Label(frame, text="全局快捷键", font=("", 11, "bold")).grid(
            row=11, column=0, columnspan=4, sticky="w", pady=(16, 6)
        )
        self.hotkey_vars: dict[str, tk.StringVar] = {}
        for index, (key, title) in enumerate(HOTKEY_ROWS):
            ttk.Label(frame, text=title).grid(row=12 + index, column=0, sticky="w", pady=2)
            var = tk.StringVar(value=self.config.hotkeys.get(key, ""))
            self.hotkey_vars[key] = var
            ttk.Entry(frame, textvariable=var, width=24).grid(
                row=12 + index, column=1, columnspan=2, sticky="w", padx=(8, 8)
            )
            ttk.Label(frame, text="例：Ctrl+Alt+Shift+S", foreground="#777").grid(
                row=12 + index, column=3, sticky="w"
            )

        buttons = ttk.Frame(frame)
        buttons.grid(row=19, column=0, columnspan=4, sticky="e", pady=(18, 0))
        ttk.Button(buttons, text="保存", command=self.save).pack(side="right")
        ttk.Button(buttons, text="取消", command=self.root.destroy).pack(side="right", padx=(0, 8))

        root.bind("<Return>", lambda event: self.save())
        root.bind("<Escape>", lambda event: self.root.destroy())

    # ---------------------------------------------------------------- 保存
    def save(self):
        config = self.config.copy()
        config.delimiters = [d for d, var in self.delimiter_vars.items() if var.get()]
        if WHITESPACE in config.delimiters:
            config.delimiters.remove(WHITESPACE)
            config.delimiters.insert(0, WHITESPACE)
        config.custom_delimiters = [
            token for token in (self.custom_var.get() or "").split() if token
        ]
        config.dedupe = self.dedupe_var.get()
        config.auto_paste = self.auto_paste_var.get()
        config.play_sound = self.sound_var.get()

        for key, var in self.hotkey_vars.items():
            combo = (var.get() or "").strip()
            if not combo:
                config.hotkeys[key] = ""
                continue
            ok, error = validate_combo(combo)
            if not ok:
                messagebox.showerror("快捷键不可用", f"“{combo}”\n\n{error}")
                return
            config.hotkeys[key] = normalize_combo(combo)

        config.save()
        self.root.destroy()


def main() -> int:
    if sys.platform != "win32":
        print("设置窗口只用于 Windows。", file=sys.stderr)
        return 2
    root = tk.Tk()
    SettingsWindow(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
