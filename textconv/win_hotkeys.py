"""Windows 全局快捷键。

用 Win32 的 RegisterHotKey，而不是 keyboard 库的低级键盘钩子。

原因：低级钩子（SetWindowsHookEx + WH_KEYBOARD_LL）的回调必须很快返回，
系统有个 LowLevelHooksTimeout（默认几百毫秒）。Python 回调一旦被 GIL、
休眠唤醒或后台限速拖慢，Windows 会**静默摘掉**这个钩子且不通知进程，
表现就是"用久了快捷键没反应，重启才好"。RegisterHotKey 是系统级的
热键注册，不依赖用户态钩子，长时间空闲、睡眠唤醒后都还在。
"""

from __future__ import annotations

import ctypes
import logging
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

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

# --- Win32 常量 ---------------------------------------------------------
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

_MODIFIERS = {
    "ctrl": MOD_CONTROL,
    "alt": MOD_ALT,
    "shift": MOD_SHIFT,
    "windows": MOD_WIN,
}

#: 单键 -> 虚拟键码
_VK_SINGLE = {chr(code).lower(): code for code in range(0x41, 0x5B)}  # a-z
_VK_SINGLE.update({str(digit): 0x30 + digit for digit in range(10)})
_VK_NAMED = {
    "space": 0x20,
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "esc": 0x1B,
    "escape": 0x1B,
    "backspace": 0x08,
    "delete": 0x2E,
    "insert": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    ",": 0xBC,
    ".": 0xBE,
    "/": 0xBF,
    ";": 0xBA,
    "-": 0xBD,
    "=": 0xBB,
    "[": 0xDB,
    "]": 0xDD,
    "\\": 0xDC,
    "'": 0xDE,
    "`": 0xC0,
}


def normalize_combo(combo: str) -> str:
    """把 'Ctrl + Alt + Shift + S' 之类的写法规整成统一形式。"""
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


def parse_combo(combo: str) -> Tuple[int, int]:
    """把快捷键字符串解析成 (修饰键, 虚拟键码)。

    纯函数，不依赖 Windows，方便在别的平台上做单元测试。
    不合法时抛 ValueError。
    """
    normalized = normalize_combo(combo)
    if not normalized:
        raise ValueError("快捷键不能为空")

    tokens = normalized.split("+")
    modifiers = 0
    key_token: Optional[str] = None

    for token in tokens:
        if token in _MODIFIERS:
            modifiers |= _MODIFIERS[token]
        elif key_token is None:
            key_token = token
        else:
            raise ValueError(f"只能有一个主键：{combo}")

    if key_token is None:
        raise ValueError(f"缺少主键：{combo}")
    if modifiers == 0:
        raise ValueError(f"至少要带一个修饰键（Ctrl/Alt/Shift/Win）：{combo}")

    key = key_token.lower()
    if key in _VK_SINGLE:
        vk = _VK_SINGLE[key]
    elif key in _VK_NAMED:
        vk = _VK_NAMED[key]
    elif key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x70 + int(key[1:]) - 1
    else:
        raise ValueError(f"不支持的按键：{key_token}")

    return modifiers, vk


def validate_combo(combo: str) -> tuple[bool, str]:
    """返回 (是否合法, 错误说明)。"""
    try:
        parse_combo(combo)
    except ValueError as exc:
        return False, str(exc)
    return True, ""


class WinHotKeyManager:
    """用 RegisterHotKey 注册全局热键，单独线程跑消息循环。"""

    BASE_ID = 0xB000

    def __init__(self, min_interval: float = 0.3) -> None:
        self._min_interval = min_interval
        self._bindings: List[Tuple[str, Callable[[], None]]] = []
        self._errors: List[str] = []
        self._thread: Optional[threading.Thread] = None
        self._thread_id = 0
        self._ready = threading.Event()
        self._last_fired: Dict[int, float] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------ 对外接口
    def apply(self, bindings: List[Tuple[str, Callable[[], None]]]) -> List[str]:
        """注册一组快捷键，返回注册失败的 combo 列表。会先停掉旧的。"""
        self.stop()
        self._bindings = list(bindings)
        self._errors = []
        self._thread = threading.Thread(target=self._run, name="TextConvHotkeys", daemon=True)
        self._ready.clear()
        self._thread.start()
        self._ready.wait(3.0)
        return list(self._errors)

    def stop(self) -> None:
        thread, thread_id = self._thread, self._thread_id
        self._thread = None
        self._thread_id = 0
        if thread is None or thread_id == 0:
            return
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.PostThreadMessageW(thread_id, WM_QUIT, 0, 0)
        except Exception:
            log.exception("停止快捷键线程失败")
        thread.join(timeout=1.5)

    # ------------------------------------------------------------ 内部
    def _run(self) -> None:
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
        user32.RegisterHotKey.restype = wintypes.BOOL
        user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.UnregisterHotKey.restype = wintypes.BOOL
        user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, ctypes.c_uint, ctypes.c_uint]
        user32.GetMessageW.restype = wintypes.BOOL
        user32.PostThreadMessageW.argtypes = [wintypes.DWORD, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
        user32.PostThreadMessageW.restype = wintypes.BOOL
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._thread_id = kernel32.GetCurrentThreadId()

        callbacks: Dict[int, Callable[[], None]] = {}
        registered: List[int] = []

        for index, (combo, callback) in enumerate(self._bindings):
            try:
                modifiers, vk = parse_combo(combo)
            except ValueError as exc:
                log.warning("快捷键无效 %s：%s", combo, exc)
                self._errors.append(combo)
                continue
            hotkey_id = self.BASE_ID + index
            if not user32.RegisterHotKey(None, hotkey_id, modifiers | MOD_NOREPEAT, vk):
                error = ctypes.get_last_error()
                log.warning("注册快捷键 %s 失败（WinError %s），可能被别的程序占用", combo, error)
                self._errors.append(combo)
                continue
            callbacks[hotkey_id] = callback
            registered.append(hotkey_id)

        self._ready.set()

        msg = wintypes.MSG()
        try:
            while True:
                result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result == 0 or result == -1:
                    break
                if msg.message == WM_HOTKEY:
                    hotkey_id = int(msg.wParam)
                    callback = callbacks.get(hotkey_id)
                    if callback is None:
                        continue
                    now = time.monotonic()
                    with self._lock:
                        if now - self._last_fired.get(hotkey_id, 0.0) < self._min_interval:
                            continue
                        self._last_fired[hotkey_id] = now
                    # 放到独立线程执行，别让转换卡住热键消息循环
                    threading.Thread(target=self._safe_call, args=(callback,), daemon=True).start()
        finally:
            for hotkey_id in registered:
                try:
                    user32.UnregisterHotKey(None, hotkey_id)
                except Exception:
                    pass
            log.info("快捷键消息循环已退出")

    @staticmethod
    def _safe_call(callback: Callable[[], None]) -> None:
        try:
            callback()
        except Exception:
            log.exception("快捷键回调执行失败")
