"""设置窗口：勾选分隔符、自定义分隔符、开关、全局快捷键。

用 AppKit 原生控件，和菜单栏 App 同进程，避免再引入 tkinter。
"""

from __future__ import annotations

from typing import Callable, Dict

import objc
from AppKit import (
    NSAlert,
    NSBackingStoreBuffered,
    NSBezelStyleRounded,
    NSButton,
    NSColor,
    NSFont,
    NSMakeRect,
    NSSwitchButton,
    NSTextField,
    NSView,
    NSWindow,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskTitled,
)
from Foundation import NSObject

from . import paste
from .config import Config
from .core import BUILTIN_DELIMITERS, WHITESPACE
from .hotkeys import HotKeyError, describe_combo, parse_combo

WIDTH = 620
HEIGHT = 640
PAD = 24

HOTKEY_ROWS = [
    ("sql", "SQL IN 子句"),
    ("excel", "Excel 粘贴"),
    ("json", "JSON 数组"),
    ("tuple", "Python 元组"),
    ("list", "Python 列表"),
    ("column", "Excel 一列"),
]


def _font(size: float, bold: bool = False):
    if bold:
        return NSFont.boldSystemFontOfSize_(size)
    return NSFont.systemFontOfSize_(size)


def _label(text: str, frame, size: float = 13, bold: bool = False, dim: bool = False):
    field = NSTextField.alloc().initWithFrame_(frame)
    field.setStringValue_(text)
    field.setBezeled_(False)
    field.setDrawsBackground_(False)
    field.setEditable_(False)
    field.setSelectable_(False)
    field.setFont_(_font(size, bold))
    if dim:
        field.setTextColor_(NSColor.secondaryLabelColor())
    return field


def _checkbox(title: str, frame):
    button = NSButton.alloc().initWithFrame_(frame)
    button.setButtonType_(NSSwitchButton)
    button.setTitle_(title)
    button.setFont_(_font(13))
    return button


class SettingsWindow(NSObject):
    """持有窗口与控件，保存时回写 Config。"""

    def initWithConfig_callback_(self, config: Config, callback: Callable[[Config], None]):
        self = objc.super(SettingsWindow, self).init()
        if self is None:
            return None
        self._config = config.copy()
        self._callback = callback
        self._window = None
        self._delimiter_buttons: Dict[str, object] = {}
        self._hotkey_fields: Dict[str, object] = {}
        self._custom_field = None
        self._dedupe_box = None
        self._auto_paste_box = None
        self._sound_box = None
        self._trust_label = None
        self._build()
        return self

    # ------------------------------------------------------------ 构建界面
    @objc.python_method
    def _frame(self, x, top, width, height):
        return NSMakeRect(x, HEIGHT - top - height, width, height)

    @objc.python_method
    def _build(self):
        window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, WIDTH, HEIGHT),
            NSWindowStyleMaskTitled | NSWindowStyleMaskClosable,
            NSBackingStoreBuffered,
            False,
        )
        window.setTitle_("TextConv 设置")
        window.setReleasedWhenClosed_(False)
        window.setDelegate_(self)
        window.center()
        self._window = window

        view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, WIDTH, HEIGHT))
        window.setContentView_(view)

        view.addSubview_(
            _label("分隔符：粘贴的文本会按这些符号切开", self._frame(PAD, 18, 500, 20), 14, True)
        )

        top = 50
        for index, (delim, title) in enumerate(BUILTIN_DELIMITERS):
            row, col = divmod(index, 2)
            button = _checkbox(title, self._frame(PAD + col * 280, top + row * 28, 260, 24))
            button.setState_(1 if delim in self._config.delimiters else 0)
            self._delimiter_buttons[delim] = button
            view.addSubview_(button)

        top += 4 * 28 + 10
        view.addSubview_(_label("自定义分隔符（用空格分隔，可填多个字符）", self._frame(PAD, top, 400, 20), 13))
        self._custom_field = NSTextField.alloc().initWithFrame_(self._frame(PAD, top + 24, 360, 26))
        self._custom_field.setStringValue_(" ".join(self._config.custom_delimiters))
        self._custom_field.setPlaceholderString_("例如：· :: |")
        view.addSubview_(self._custom_field)

        top += 66
        view.addSubview_(_label("选项", self._frame(PAD, top, 200, 20), 14, True))
        self._dedupe_box = _checkbox("去重（保持顺序）", self._frame(PAD, top + 26, 180, 24))
        self._dedupe_box.setState_(1 if self._config.dedupe else 0)
        view.addSubview_(self._dedupe_box)

        self._auto_paste_box = _checkbox("转换后自动粘贴 ⌘V", self._frame(PAD + 220, top + 26, 200, 24))
        self._auto_paste_box.setState_(1 if self._config.auto_paste else 0)
        view.addSubview_(self._auto_paste_box)

        self._sound_box = _checkbox("提示音", self._frame(PAD + 440, top + 26, 120, 24))
        self._sound_box.setState_(1 if self._config.play_sound else 0)
        view.addSubview_(self._sound_box)

        top += 70
        view.addSubview_(_label("全局快捷键（修饰键用 + 连接，例如 ctrl+alt+cmd+s）", self._frame(PAD, top, 520, 20), 14, True))
        top += 28
        for key, title in HOTKEY_ROWS:
            view.addSubview_(_label(title, self._frame(PAD, top + 2, 150, 20), 13))
            field = NSTextField.alloc().initWithFrame_(self._frame(PAD + 160, top, 210, 24))
            field.setStringValue_(self._config.hotkeys.get(key, ""))
            self._hotkey_fields[key] = field
            view.addSubview_(field)
            top += 30

        top += 8
        self._trust_label = _label("", self._frame(PAD, top, 560, 20), 12, dim=True)
        view.addSubview_(self._trust_label)

        trust_button = NSButton.alloc().initWithFrame_(self._frame(PAD, top + 24, 200, 28))
        trust_button.setTitle_("打开辅助功能设置…")
        trust_button.setBezelStyle_(NSBezelStyleRounded)
        trust_button.setTarget_(self)
        trust_button.setAction_("openAccessibility:")
        view.addSubview_(trust_button)

        save_button = NSButton.alloc().initWithFrame_(self._frame(WIDTH - PAD - 100, HEIGHT - 62, 100, 32))
        save_button.setTitle_("保存")
        save_button.setBezelStyle_(NSBezelStyleRounded)
        save_button.setTarget_(self)
        save_button.setAction_("saveSettings:")
        save_button.setKeyEquivalent_("\r")
        view.addSubview_(save_button)

        cancel_button = NSButton.alloc().initWithFrame_(self._frame(WIDTH - PAD - 220, HEIGHT - 62, 100, 32))
        cancel_button.setTitle_("取消")
        cancel_button.setBezelStyle_(NSBezelStyleRounded)
        cancel_button.setTarget_(self)
        cancel_button.setAction_("cancelSettings:")
        cancel_button.setKeyEquivalent_("\x1b")
        view.addSubview_(cancel_button)

        self._refresh_trust_label()

    @objc.python_method
    def _refresh_trust_label(self):
        if self._trust_label is None:
            return
        if paste.is_trusted():
            self._trust_label.setStringValue_("✓ 已获得辅助功能权限，可以使用自动粘贴")
        else:
            self._trust_label.setStringValue_(
                "⚠️ 未获得辅助功能权限：转换结果只会复制到剪贴板，需手动 ⌘V"
            )

    # ------------------------------------------------------------ 动作
    @objc.python_method
    def show(self):
        self._refresh_trust_label()
        self._window.makeKeyAndOrderFront_(None)
        from AppKit import NSApp

        NSApp.activateIgnoringOtherApps_(True)

    @objc.python_method
    def close(self):
        self._window.close()

    def windowWillClose_(self, notification):
        pass

    def openAccessibility_(self, sender):
        paste.open_accessibility_settings()

    def saveSettings_(self, sender):
        cfg = self._config.copy()
        cfg.delimiters = [
            delim for delim, button in self._delimiter_buttons.items() if button.state() == 1
        ]
        if WHITESPACE in cfg.delimiters:
            cfg.delimiters.remove(WHITESPACE)
            cfg.delimiters.insert(0, WHITESPACE)
        raw_custom = self._custom_field.stringValue() or ""
        cfg.custom_delimiters = [token for token in raw_custom.split() if token]

        cfg.dedupe = self._dedupe_box.state() == 1
        cfg.auto_paste = self._auto_paste_box.state() == 1
        cfg.play_sound = self._sound_box.state() == 1

        for key, field in self._hotkey_fields.items():
            combo = (field.stringValue() or "").strip().lower()
            if not combo:
                cfg.hotkeys[key] = ""
                continue
            try:
                parse_combo(combo)
            except HotKeyError as exc:
                self._alert(f"快捷键“{combo}”不可用：{exc}")
                return
            cfg.hotkeys[key] = combo

        cfg.save()
        if self._callback is not None:
            self._callback(cfg)
        self._window.close()

    def cancelSettings_(self, sender):
        self._window.close()

    @objc.python_method
    def _alert(self, message: str):
        alert = NSAlert.alloc().init()
        alert.setMessageText_("无法保存")
        alert.setInformativeText_(message)
        alert.addButtonWithTitle_("好")
        alert.runModal()
