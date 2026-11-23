"""模拟 ⌘V 自动粘贴，以及辅助功能权限检查。

只做一件事：把转换结果直接“贴”到光标处，省掉再按一次 ⌘V。
没有辅助功能权限时调用方应退化为“只复制到剪贴板”。
"""

from __future__ import annotations

import subprocess
import sys

try:
    import Quartz
except Exception:  # pragma: no cover
    Quartz = None


def is_trusted() -> bool:
    """当前进程是否已获得辅助功能（Accessibility）权限。

    Windows 没有这一层限制，合成按键本来就是允许的。
    """
    if sys.platform == "win32":
        return True
    try:
        from ApplicationServices import AXIsProcessTrusted

        return bool(AXIsProcessTrusted())
    except Exception:
        pass
    try:
        import ctypes

        lib = ctypes.CDLL(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
        )
        lib.AXIsProcessTrusted.restype = ctypes.c_bool
        return bool(lib.AXIsProcessTrusted())
    except Exception:
        return False


def request_trust() -> None:
    """弹出系统自带的“授予辅助功能权限”提示。"""
    try:
        from ApplicationServices import (
            AXIsProcessTrustedWithOptions,
            kAXTrustedCheckOptionPrompt,
        )

        AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})
        return
    except Exception:
        pass
    try:
        import ctypes

        lib = ctypes.CDLL(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
        )
        cf = ctypes.CDLL(
            "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
        )
        cf.CFDictionaryCreate.restype = ctypes.c_void_p
        lib.AXIsProcessTrustedWithOptions(ctypes.c_void_p())
    except Exception:
        pass


def open_accessibility_settings() -> None:
    """打开系统设置的辅助功能面板。"""
    subprocess.run(
        [
            "open",
            "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
        ],
        check=False,
    )


def send_paste() -> bool:
    """向前台窗口发送一次粘贴：Windows 是 Ctrl+V，macOS 是 ⌘V。"""
    if sys.platform == "win32":
        return _win_paste()
    if Quartz is None:
        return False
    try:
        source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
        keycode_v = 9  # 物理键位 V，与键盘布局无关
        for down in (True, False):
            event = Quartz.CGEventCreateKeyboardEvent(source, keycode_v, down)
            Quartz.CGEventSetFlags(event, Quartz.kCGEventFlagMaskCommand)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
        return True
    except Exception:
        return False


def _win_paste() -> bool:
    """Windows：优先用 keyboard 库，没有就用 keybd_event 兜底。"""
    try:
        import keyboard

        keyboard.send("ctrl+v")
        return True
    except Exception:
        pass
    try:
        import ctypes

        user32 = ctypes.windll.user32
        VK_CONTROL = 0x11
        VK_V = 0x56
        KEYEVENTF_KEYUP = 0x0002
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(VK_V, 0, 0, 0)
        user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        return True
    except Exception:
        return False
