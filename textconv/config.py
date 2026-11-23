"""配置读写：~/Library/Application Support/TextConv/config.json"""

from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

from .core import DEFAULT_DELIMITERS, WHITESPACE

APP_NAME = "TextConv"

#: 各平台默认键位：Windows 用 Ctrl+Alt+Shift，macOS 用 ⌃⌥⌘
_WIN_KEYS = {
    "sql": "ctrl+alt+shift+s",
    "excel": "ctrl+alt+shift+e",
    "json": "ctrl+alt+shift+j",
    "tuple": "ctrl+alt+shift+p",
    "list": "ctrl+alt+shift+l",
    "column": "ctrl+alt+shift+k",
}
_MAC_KEYS = {
    "sql": "ctrl+alt+cmd+s",
    "excel": "ctrl+alt+cmd+e",
    "json": "ctrl+alt+cmd+j",
    "tuple": "ctrl+alt+cmd+p",
    "list": "ctrl+alt+cmd+l",
    "column": "ctrl+alt+cmd+k",
}


def default_hotkeys() -> Dict[str, str]:
    return dict(_WIN_KEYS if sys.platform == "win32" else _MAC_KEYS)


DEFAULT_HOTKEYS: Dict[str, str] = default_hotkeys()


def app_dir() -> str:
    """应用数据目录；TEXTCONV_HOME 可覆盖，便于测试。"""
    override = os.environ.get("TEXTCONV_HOME")
    if override:
        return override
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.join(
            os.path.expanduser("~"), "AppData", "Roaming"
        )
        return os.path.join(base, APP_NAME)
    if sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~/Library/Application Support"), APP_NAME)
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
        os.path.expanduser("~"), ".config"
    )
    return os.path.join(base, APP_NAME)


def config_path() -> str:
    return os.path.join(app_dir(), "config.json")


def state_path() -> str:
    """菜单栏 App 写出来的运行状态，给 tc --doctor 看。"""
    return os.path.join(app_dir(), ".menubar.state.json")


@dataclass
class Config:
    delimiters: List[str] = field(default_factory=lambda: list(DEFAULT_DELIMITERS))
    custom_delimiters: List[str] = field(default_factory=list)
    dedupe: bool = True
    auto_paste: bool = True
    play_sound: bool = True
    asked_permission: bool = False
    hotkeys: Dict[str, str] = field(default_factory=lambda: default_hotkeys())
    load_error: Optional[str] = field(default=None, compare=False)

    # ---------------------------------------------------------------- 读写
    @classmethod
    def load(cls, path: Optional[str] = None) -> "Config":
        path = path or config_path()
        if not os.path.exists(path):
            return cls()
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, ValueError) as exc:
            cfg = cls()
            cfg.load_error = f"读取配置失败（已使用默认值）：{exc}"
            return cfg

        cfg = cls()
        if isinstance(raw.get("delimiters"), list):
            cfg.delimiters = [d for d in raw["delimiters"] if isinstance(d, str)]
        if isinstance(raw.get("custom_delimiters"), list):
            cfg.custom_delimiters = [
                d for d in raw["custom_delimiters"] if isinstance(d, str) and d
            ]
        for attr in ("dedupe", "auto_paste", "play_sound", "asked_permission"):
            if isinstance(raw.get(attr), bool):
                setattr(cfg, attr, raw[attr])
        if isinstance(raw.get("hotkeys"), dict):
            merged = default_hotkeys()
            for key, combo in raw["hotkeys"].items():
                if key in merged and isinstance(combo, str):
                    merged[key] = combo
            cfg.hotkeys = merged
        return cfg

    def save(self, path: Optional[str] = None) -> None:
        path = path or config_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = asdict(self)
        data.pop("load_error", None)
        # 原子写入，避免菜单栏 App 读到写了一半的文件
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    # ---------------------------------------------------------------- 便捷
    @property
    def all_delimiters(self) -> List[str]:
        """实际参与切分的分隔符（内置 + 自定义，去重保序）。"""
        seen = set()
        result: List[str] = []
        for delim in list(self.delimiters) + list(self.custom_delimiters):
            if delim and delim not in seen:
                seen.add(delim)
                result.append(delim)
        return result

    def is_delimiter_enabled(self, delim: str) -> bool:
        return delim in self.delimiters

    def set_delimiter(self, delim: str, enabled: bool) -> None:
        current = list(self.delimiters)
        if enabled and delim not in current:
            current.append(delim)
        elif not enabled and delim in current:
            current.remove(delim)
        self.delimiters = current

    def toggle_delimiter(self, delim: str) -> None:
        self.set_delimiter(delim, not self.is_delimiter_enabled(delim))

    def copy(self) -> "Config":
        return copy.deepcopy(self)
