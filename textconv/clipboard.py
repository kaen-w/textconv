"""剪贴板读写：macOS 用 NSPasteboard/pbpaste，Windows 用 Win32，其他用 pyperclip。"""

from __future__ import annotations

import subprocess
import sys
import time

if sys.platform == "darwin":
    try:  # 菜单栏 App / CLI 里都有 PyObjC
        from AppKit import NSPasteboard, NSPasteboardTypeString
    except Exception:  # pragma: no cover
        NSPasteboard = None
        NSPasteboardTypeString = None


def _win_clipboard():
    """Windows：优先 pyperclip，没有就直接调 Win32 API。"""
    try:
        import pyperclip

        return pyperclip
    except Exception:
        return None


def get_text() -> str:
    """读取剪贴板纯文本，失败返回空串。"""
    if sys.platform == "win32":
        return _win_get_with_retry()

    if sys.platform == "darwin":
        if NSPasteboard is not None:
            try:
                value = NSPasteboard.generalPasteboard().stringForType_(
                    NSPasteboardTypeString
                )
                return value or ""
            except Exception:
                pass
        try:
            out = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5)
            return out.stdout
        except Exception:
            return ""

    try:
        import pyperclip

        return pyperclip.paste() or ""
    except Exception:
        return ""


def set_text(text: str) -> bool:
    """把文本写入剪贴板，成功返回 True。

    Windows 上别的程序（尤其 Excel）会短暂占用剪贴板，OpenClipboard 会失败，
    所以这里要重试 + 回读校验，不能“调用了就算成功”。
    """
    if sys.platform == "win32":
        return _win_set_with_retry(text)

    if sys.platform == "darwin":
        if NSPasteboard is not None:
            try:
                pasteboard = NSPasteboard.generalPasteboard()
                pasteboard.clearContents()
                return bool(pasteboard.setString_forType_(text, NSPasteboardTypeString))
            except Exception:
                pass
        try:
            subprocess.run(["pbcopy"], input=text, text=True, timeout=5, check=True)
            return True
        except Exception:
            return False

    try:
        import pyperclip

        pyperclip.copy(text)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- Win32 兜底
def _win_get_text_ctypes() -> str:
    import ctypes
    from ctypes import wintypes

    CF_UNICODETEXT = 13
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    if not user32.OpenClipboard(None):
        return ""
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        kernel32.GlobalLock.restype = ctypes.c_void_p
        pointer = kernel32.GlobalLock(wintypes.HANDLE(handle))
        if not pointer:
            return ""
        try:
            return ctypes.wstring_at(pointer)
        finally:
            kernel32.GlobalUnlock(wintypes.HANDLE(handle))
    finally:
        user32.CloseClipboard()


def _win_set_text_ctypes(text: str) -> bool:
    import ctypes
    from ctypes import wintypes

    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    data = (text + "\0").encode("utf-16-le")
    if not user32.OpenClipboard(None):
        return False
    try:
        user32.EmptyClipboard()
        kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            return False
        kernel32.GlobalLock.restype = ctypes.c_void_p
        pointer = kernel32.GlobalLock(wintypes.HANDLE(handle))
        if not pointer:
            return False
        try:
            ctypes.memmove(pointer, data, len(data))
        finally:
            kernel32.GlobalUnlock(wintypes.HANDLE(handle))
        return bool(user32.SetClipboardData(CF_UNICODETEXT, wintypes.HANDLE(handle)))
    finally:
        user32.CloseClipboard()


# ---------------------------------------------------------------- 重试 + 校验
def _win_get_with_retry(attempts: int = 3, delay: float = 0.02) -> str:
    module = _win_clipboard()
    for _ in range(attempts):
        if module is not None:
            try:
                value = module.paste()
                if value:
                    return value
            except Exception:
                pass
        try:
            value = _win_get_text_ctypes()
            if value:
                return value
        except Exception:
            pass
        time.sleep(delay)
    return ""


def _win_set_with_retry(text: str, attempts: int = 10, delay: float = 0.03) -> bool:
    module = _win_clipboard()
    for _ in range(attempts):
        if module is not None:
            try:
                module.copy(text)
                if _win_get_text_ctypes() == text:
                    return True
            except Exception:
                pass
        try:
            if _win_set_text_ctypes(text) and _win_get_text_ctypes() == text:
                return True
        except Exception:
            pass
        time.sleep(delay)
    return False
