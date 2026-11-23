"""Windows 全局快捷键：keyboard 库（低级键盘钩子，普通权限即可）。"""

from __future__ import annotations

import logging
import time
from typing import Callable, Dict, List

log = logging.getLogger(__name__)

_ALIASES = {
    "cmd": "windows",
    "command": "windows",
    "opt": "alt",
    "option": "alt",
    "control": "ctrl",
    "win": "windows",
}

_DISPLAY = {
    "ctrl": "Ctrl",
    "alt": "Alt",
    "shift": "Shift",
    "windows": "Win",
}


def normalize_combo(combo: str) -> str:
    """把 'Ctrl + Alt + Shift + S' 之类的写法规整成 keyboard 库要的形式。"""
    tokens = []
    for token in (combo or "").replace(" ", "").split("+"):
        token = token.strip().lower()
        if not token:
            continue
        tokens.append(_ALIASES.get(token, token))
    return "+".join(tokens)


def describe_combo(combo: str) -> str:
    """Ctrl+Alt+Shift+S —— 菜单里展示用。"""
    normalized = normalize_combo(combo)
    if not normalized:
        return ""
    parts = normalized.split("+")
    return "+".join(_DISPLAY.get(p, p.upper()) for p in parts)


def validate_combo(combo: str) -> tuple[bool, str]:
    """返回 (是否合法, 错误说明)。"""
    normalized = normalize_combo(combo)
    if not normalized:
        return False, "快捷键不能为空"
    try:
        import keyboard
    except Exception as exc:  # pragma: no cover
        return False, f"缺少 keyboard 库：{exc}"
    try:
        keyboard.parse_hotkey(normalized)
    except Exception as exc:
        return False, f"无法识别的快捷键：{exc}"
    return True, ""


class WinHotKeyManager:
    """keyboard.add_hotkey 的薄封装。"""

    def __init__(self, min_interval: float = 0.3) -> None:
        self._handles: List[int] = []
        self._last_fired: Dict[str, float] = {}
        self._min_interval = min_interval

    def register(self, combo: str, callback: Callable[[], None]) -> bool:
        try:
            import keyboard
        except Exception as exc:  # pragma: no cover
            log.error("缺少 keyboard 库：%s", exc)
            return False
        normalized = normalize_combo(combo)
        if not normalized:
            return False
        def throttled():
            # 按住不放时系统会重复触发，这里去抖，避免一次按键转好几遍
            now = time.monotonic()
            if now - self._last_fired.get(normalized, 0.0) < self._min_interval:
                return
            self._last_fired[normalized] = now
            callback()

        try:
            handle = keyboard.add_hotkey(normalized, throttled, suppress=False)
            self._handles.append(handle)
            return True
        except Exception as exc:
            log.warning("注册快捷键 %s 失败：%s", combo, exc)
            return False

    def stop(self) -> None:
        try:
            import keyboard

            for handle in self._handles:
                keyboard.remove_hotkey(handle)
        except Exception:
            pass
        self._handles.clear()
        self._last_fired.clear()
