"""全局快捷键：Carbon RegisterEventHotKey（ctypes 调用，无需任何权限）。

两个实测结论（macOS 26）决定了这里的写法：

1. RegisterEventHotKey 注册本身不需要辅助功能权限，而且会把组合键从系统层面
   截走（前台 App 收不到），正是我们要的效果；
2. 但**从未被激活过的后台 App 收不到 kEventHotKeyPressed**——系统不会把热键
   事件派发给它。一旦它成为过前台 App（哪怕只有 0.2 秒），之后退到后台也照常
   收得到。所以 menubar 启动时会做一次“激活 → 立刻还给原前台 App”的动作。
"""

from __future__ import annotations

import ctypes
import ctypes.util
import logging
from typing import Callable, Dict, List, Tuple

log = logging.getLogger(__name__)

_CARBON_PATH = ctypes.util.find_library("Carbon") or (
    "/System/Library/Frameworks/Carbon.framework/Carbon"
)

carbon = ctypes.CDLL(_CARBON_PATH)

carbon.GetApplicationEventTarget.restype = ctypes.c_void_p
carbon.GetApplicationEventTarget.argtypes = []


class EventHotKeyID(ctypes.Structure):
    _fields_ = [("signature", ctypes.c_uint32), ("id", ctypes.c_uint32)]


class EventTypeSpec(ctypes.Structure):
    _fields_ = [("eventClass", ctypes.c_uint32), ("eventKind", ctypes.c_uint32)]


_HANDLER = ctypes.CFUNCTYPE(
    ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
)

carbon.InstallEventHandler.argtypes = [
    ctypes.c_void_p,
    _HANDLER,
    ctypes.c_ulong,
    ctypes.POINTER(EventTypeSpec),
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_void_p),
]
carbon.InstallEventHandler.restype = ctypes.c_int32
carbon.RemoveEventHandler.argtypes = [ctypes.c_void_p]
carbon.RemoveEventHandler.restype = ctypes.c_int32
carbon.RegisterEventHotKey.argtypes = [
    ctypes.c_uint32,
    ctypes.c_uint32,
    EventHotKeyID,
    ctypes.c_void_p,
    ctypes.c_uint32,
    ctypes.POINTER(ctypes.c_void_p),
]
carbon.RegisterEventHotKey.restype = ctypes.c_int32
carbon.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]
carbon.UnregisterEventHotKey.restype = ctypes.c_int32
carbon.GetEventParameter.argtypes = [
    ctypes.c_void_p,
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.c_uint32,
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.c_void_p,
]
carbon.GetEventParameter.restype = ctypes.c_int32

SIGNATURE = 0x54435631  # 'TCV1'

K_EVENT_CLASS_KEYBOARD = 0x6B657962  # 'keyb'
K_EVENT_HOT_KEY_PRESSED = 5
K_EVENT_PARAM_DIRECT_OBJECT = 0x2D2D2D2D  # '----'
TYPE_EVENT_HOT_KEY_ID = 0x686B6964  # 'hkid'

# Carbon 修饰位
FLAG_CMD = 0x0100
FLAG_SHIFT = 0x0200
FLAG_OPTION = 0x0800
FLAG_CONTROL = 0x1000

MODIFIERS: Dict[str, int] = {
    "cmd": FLAG_CMD,
    "command": FLAG_CMD,
    "⌘": FLAG_CMD,
    "shift": FLAG_SHIFT,
    "⇧": FLAG_SHIFT,
    "alt": FLAG_OPTION,
    "opt": FLAG_OPTION,
    "option": FLAG_OPTION,
    "⌥": FLAG_OPTION,
    "ctrl": FLAG_CONTROL,
    "control": FLAG_CONTROL,
    "⌃": FLAG_CONTROL,
}

MODIFIER_ORDER = [("ctrl", "⌃"), ("alt", "⌥"), ("shift", "⇧"), ("cmd", "⌘")]
SYMBOL_CHARS = "⌃⌥⌘⇧"

# 物理键位（US 布局），不随输入法变化
KEYCODES: Dict[str, int] = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9,
    "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
    "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23, "=": 24, "9": 25,
    "7": 26, "-": 27, "8": 28, "0": 29, "]": 30, "o": 31, "u": 32, "[": 33,
    "i": 34, "p": 35, "l": 37, "j": 38, "'": 39, "k": 40, ";": 41, "\\": 42,
    ",": 43, "/": 44, "n": 45, "m": 46, ".": 47, "`": 50,
    "space": 49, "tab": 48, "return": 36, "enter": 36, "escape": 53, "esc": 53,
    "left": 123, "right": 124, "down": 125, "up": 126,
    "home": 115, "end": 119, "pageup": 116, "pagedown": 121, "delete": 51,
}


class HotKeyError(ValueError):
    pass


def parse_combo(combo: str) -> Tuple[int, int]:
    """'ctrl+alt+cmd+s' 或 '⌃⌥⌘S' -> (keycode, Carbon 修饰位)"""
    if not combo or not combo.strip():
        raise HotKeyError("快捷键为空")
    text = combo.strip().replace(" ", "")
    modifiers = 0

    if "+" in text:
        tokens = [t.lower() for t in text.split("+") if t]
        if not tokens:
            raise HotKeyError(f"无法解析快捷键：{combo}")
        key = tokens[-1]
        for token in tokens[:-1]:
            if token not in MODIFIERS:
                raise HotKeyError(f"不认识的修饰键：{token}")
            modifiers |= MODIFIERS[token]
    else:
        index = 0
        while index < len(text) and text[index] in SYMBOL_CHARS:
            modifiers |= MODIFIERS[text[index]]
            index += 1
        key = text[index:].lower()

    if key not in KEYCODES:
        raise HotKeyError(f"不支持的按键：{key}")
    if modifiers == 0:
        raise HotKeyError("全局快捷键必须带至少一个修饰键")
    return KEYCODES[key], modifiers


def describe_combo(combo: str) -> str:
    """把 combo 渲染成 macOS 风格的 ⌃⌥⌘S，解析失败时原样返回。"""
    try:
        keycode, modifiers = parse_combo(combo)
    except HotKeyError:
        return combo
    parts = [symbol for name, symbol in MODIFIER_ORDER if modifiers & MODIFIERS[name]]
    key = next((k for k, v in KEYCODES.items() if v == keycode), "?")
    return "".join(parts) + key.upper()


class HotKeyManager:
    """管理一组全局快捷键；回调在主线程的 RunLoop 里触发。"""

    def __init__(self) -> None:
        self._callbacks: Dict[int, Callable[[], None]] = {}
        self._refs: List[ctypes.c_void_p] = []
        self._next_id = 1
        self._target = carbon.GetApplicationEventTarget()
        self._upp = _HANDLER(self._dispatch)
        spec = EventTypeSpec(K_EVENT_CLASS_KEYBOARD, K_EVENT_HOT_KEY_PRESSED)
        handler_ref = ctypes.c_void_p()
        status = carbon.InstallEventHandler(
            self._target, self._upp, 1, ctypes.byref(spec), None, ctypes.byref(handler_ref)
        )
        if status != 0:
            raise HotKeyError(f"InstallEventHandler 失败，OSStatus={status}")
        self._handler_ref = handler_ref

    def _dispatch(self, call_ref, event, user_data) -> int:
        hotkey_id = EventHotKeyID()
        actual_type = ctypes.c_uint32(0)
        actual_size = ctypes.c_uint32(0)
        status = carbon.GetEventParameter(
            event,
            K_EVENT_PARAM_DIRECT_OBJECT,
            TYPE_EVENT_HOT_KEY_ID,
            ctypes.byref(actual_type),
            ctypes.sizeof(hotkey_id),
            ctypes.byref(actual_size),
            ctypes.byref(hotkey_id),
        )
        if status == 0:
            callback = self._callbacks.get(hotkey_id.id)
            if callback is not None:
                try:
                    callback()
                except Exception:
                    log.exception("快捷键回调出错")
        return 0

    def register(self, combo: str, callback: Callable[[], None]) -> bool:
        try:
            keycode, modifiers = parse_combo(combo)
        except HotKeyError as exc:
            log.warning("快捷键 %s 无效：%s", combo, exc)
            return False
        hotkey_id = self._next_id
        self._next_id += 1
        ref = ctypes.c_void_p()
        status = carbon.RegisterEventHotKey(
            keycode,
            modifiers,
            EventHotKeyID(SIGNATURE, hotkey_id),
            self._target,
            0,
            ctypes.byref(ref),  # 传 None 会得到 -50 (paramErr)
        )
        if status != 0 or not ref.value:
            log.warning("注册快捷键 %s 失败，OSStatus=%s", combo, status)
            return False
        self._callbacks[hotkey_id] = callback
        self._refs.append(ref)
        return True

    def unregister_all(self) -> None:
        for ref in self._refs:
            try:
                carbon.UnregisterEventHotKey(ref)
            except Exception:
                pass
        self._refs.clear()
        self._callbacks.clear()

    def close(self) -> None:
        self.unregister_all()
        if getattr(self, "_handler_ref", None) is not None:
            try:
                carbon.RemoveEventHandler(self._handler_ref)
            except Exception:
                pass
            self._handler_ref = None
