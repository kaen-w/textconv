"""菜单栏 App：⌃⌥⌘ 全局快捷键 + 菜单，把剪贴板文本转成目标格式并自动粘贴。

启动方式：
    python -m textconv.menubar
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import subprocess
import sys
import threading

import objc
from AppKit import (
    NSApp,
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSMenu,
    NSMenuItem,
    NSAlert,
    NSStatusBar,
    NSVariableStatusItemLength,
    NSWorkspace,
    NSOnState,
    NSSound,
)
from Foundation import NSObject
from PyObjCTools import AppHelper

from . import clipboard, core, paste
from .config import Config, config_path, app_dir, state_path
from . import __version__, update
from .hotkeys import HotKeyManager, describe_combo
from .settings_window import SettingsWindow

log = logging.getLogger("textconv.menubar")

ICON_TITLE = "TC"


def _assets_dir() -> str:
    bundled = getattr(sys, "_MEIPASS", None)  # PyInstaller 打包后的解包目录
    if bundled:
        return os.path.join(bundled, "assets")
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


def load_status_image():
    """菜单栏模板图：只有 alpha，颜色交给系统（浅色/深色菜单栏都适配）。"""
    try:
        from AppKit import NSImage

        path = os.path.join(_assets_dir(), "menubar.png")
        if not os.path.exists(path):
            log.info("没有 assets/menubar.png，菜单栏退回文字 %s", ICON_TITLE)
            return None
        image = NSImage.alloc().initWithContentsOfFile_(path)
        if image is None:
            return None
        width, height = image.size().width, image.size().height
        if not width or not height:
            log.warning("菜单栏图标尺寸异常：%sx%s", width, height)
            return None
        target_height = 17.0
        image.setSize_((target_height * width / height, target_height))
        image.setTemplate_(True)
        log.info("菜单栏图标已加载：%s（%.1f x %.1f pt）", path, image.size().width, image.size().height)
        return image
    except Exception:
        log.exception("加载菜单栏图标失败，退回文字")
        return None


def _setup_logging() -> None:
    handlers = [logging.StreamHandler(sys.stderr)]
    try:
        os.makedirs(os.path.expanduser("~/Library/Logs"), exist_ok=True)
        handlers.append(
            logging.FileHandler(os.path.expanduser("~/Library/Logs/TextConv.log"), encoding="utf-8")
        )
    except Exception:
        pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
    )


class MenuBarApp(NSObject):
    # ------------------------------------------------------------ 生命周期
    def init(self):
        self = objc.super(MenuBarApp, self).init()
        if self is None:
            return None
        self.config = Config.load()
        self.status_item = None
        self.menu = None
        self.hotkey_manager = None
        self.hotkey_errors = []
        self.settings_window = None
        self._flash_token = 0
        self._status_image = None
        self._update_hint = ""
        self._updating = False
        self._last_input = None
        self._last_output = None
        return self

    def applicationDidFinishLaunching_(self, notification):
        log.info("TextConv 启动：pid=%s 辅助功能权限=%s", os.getpid(), paste.is_trusted())
        self._create_status_item()
        self._register_hotkeys()
        self._prime_activation()
        log.info("菜单栏=%s 已注册快捷键=%s 失败=%s",
                 "图标" if self._status_image is not None else f"文字 {ICON_TITLE}",
                 list(self.config.hotkeys.values()), self.hotkey_errors)
        self._write_state()
        if self.config.load_error:
            log.error(self.config.load_error)
            self._flash("配置有误，已用默认值")
        self._maybe_request_permission()
        if self.config.check_updates and update.due_for_check(self.config.last_update_check):
            threading.Thread(target=self._update_worker, args=(False,), daemon=True).start()

    def applicationWillTerminate_(self, notification):
        if self.hotkey_manager is not None:
            self.hotkey_manager.close()

    # ------------------------------------------------------------ 状态栏
    @objc.python_method
    def _create_status_item(self):
        self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength
        )
        button = self.status_item.button()
        self._status_image = load_status_image()
        if self._status_image is not None:
            button.setImage_(self._status_image)
            button.setTitle_("")
        else:
            button.setTitle_(ICON_TITLE)
        button.setToolTip_("TextConv：剪贴板格式转换")
        self._rebuild_menu()

    @objc.python_method
    def _set_icon(self):
        button = self.status_item.button()
        image = getattr(self, "_status_image", None) or load_status_image()
        if image is not None:
            self._status_image = image
            button.setTitle_("")
            button.setImage_(image)
        else:
            button.setImage_(None)
            button.setTitle_(ICON_TITLE)

    @objc.python_method
    def _flash(self, text: str, seconds: float = 1.6):
        """在状态栏短暂显示提示文字。"""
        if self.status_item is None:
            return
        self._flash_token += 1
        token = self._flash_token
        button = self.status_item.button()
        button.setImage_(None)
        button.setTitle_(text)
        self.performSelector_withObject_afterDelay_("restoreIcon:", token, seconds)

    def restoreIcon_(self, token):
        # token 是 NSNumber 或 int，只有最后一次 flash 能恢复图标
        try:
            value = int(token)
        except (TypeError, ValueError):
            value = -1
        if value == self._flash_token:
            self._set_icon()

    # ------------------------------------------------------------ 更新
    def checkUpdates_(self, sender):
        self._flash("检查更新…", 5)
        threading.Thread(target=self._update_worker, args=(True,), daemon=True).start()

    @objc.python_method
    def _update_worker(self, manual: bool) -> None:
        release = update.fetch_latest()
        self.config.last_update_check = datetime.datetime.now().isoformat(timespec="seconds")
        try:
            self.config.save()
        except Exception:
            log.exception("保存检查时间失败")

        if release is None:
            if manual:
                AppHelper.callAfter(self._alert, "检查更新失败", "连不上 GitHub，请稍后再试。")
            return

        if update.is_newer(release.version, __version__):
            self._update_hint = release.version
            AppHelper.callAfter(self._on_update_found, release, manual)
        elif manual:
            AppHelper.callAfter(self._alert, "已经是最新版本", f"当前版本 {__version__}。")

    @objc.python_method
    def _on_update_found(self, release, manual: bool) -> None:
        if not manual:
            self._rebuild_menu()
            return

        NSApp.activateIgnoringOtherApps_(True)
        alert = NSAlert.alloc().init()
        alert.setMessageText_(f"发现新版本 {release.version}")
        alert.setInformativeText_(f"当前版本 {__version__}。下载安装包并打开？")
        alert.addButtonWithTitle_("下载并安装")
        alert.addButtonWithTitle_("稍后")
        if alert.runModal() != NSAlertFirstButtonReturn:
            return
        if self._updating:
            return
        self._updating = True
        self._flash("正在下载更新…", 8)
        threading.Thread(target=self._perform_update, args=(release,), daemon=True).start()

    @objc.python_method
    def _perform_update(self, release) -> None:
        """后台：下载 dmg → 覆盖安装 → 回主线程提示重启。"""
        try:
            url = update.pick_asset(release, "darwin")
            if not url:
                raise RuntimeError("这个版本没有 macOS 安装包")
            name = url.rsplit("/", 1)[-1]
            dest = os.path.join(app_dir(), "updates", name)
            log.info("开始下载更新：%s", url)

            last_logged = -1

            def progress(done: int, total: int) -> None:
                nonlocal last_logged
                if not total:
                    return
                percent = int(done * 100 / total)
                if percent >= last_logged + 10 or percent >= 100:
                    last_logged = percent
                    log.info("下载进度 %s%%（%s/%s）", percent, done, total)
                AppHelper.callAfter(self._flash, f"下载 {percent}%", 8)

            update.download(url, dest, progress=progress)
            log.info("下载完成：%s", dest)
            AppHelper.callAfter(self._flash, "正在安装…", 8)
            installed = update.install_dmg(dest)
            log.info("已安装到：%s", installed)
            AppHelper.callAfter(self._update_ready, release, installed)
        except Exception as exc:
            log.exception("更新失败")
            AppHelper.callAfter(self._update_failed, exc)

    @objc.python_method
    def _update_ready(self, release, installed: str) -> None:
        self._updating = False
        alert = NSAlert.alloc().init()
        alert.setMessageText_(f"已更新到 {release.version}")
        alert.setInformativeText_("现在重启 TextConv 以使用新版本？")
        alert.addButtonWithTitle_("立即重启")
        alert.addButtonWithTitle_("稍后")
        if alert.runModal() == NSAlertFirstButtonReturn:
            subprocess.Popen(["/usr/bin/open", installed])
            NSApp.terminate_(None)

    @objc.python_method
    def _update_failed(self, exc: Exception) -> None:
        self._updating = False
        self._flash("更新失败")
        self._alert(
            "更新失败",
            f"{exc}\n\n可以手动到 GitHub Releases 下载：\nhttps://github.com/kaen-w/textconv/releases/latest",
        )

    @objc.python_method
    def _alert(self, title: str, message: str) -> None:
        NSApp.activateIgnoringOtherApps_(True)
        alert = NSAlert.alloc().init()
        alert.setMessageText_(title)
        alert.setInformativeText_(message)
        alert.addButtonWithTitle_("好")
        alert.runModal()

    # ------------------------------------------------------------ 菜单
    @objc.python_method
    def _rebuild_menu(self):
        cfg = self.config
        menu = NSMenu.alloc().init()
        menu.setAutoenablesItems_(False)

        for fmt in core.FORMATS:
            combo = describe_combo(cfg.hotkeys.get(fmt.key, ""))
            title = f"{fmt.action}    {combo}" if combo else fmt.action
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, "convertFromMenu:", "")
            item.setTarget_(self)
            item.setRepresentedObject_(fmt.key)
            menu.addItem_(item)

        menu.addItem_(NSMenuItem.separatorItem())

        delimiter_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("分隔符", None, "")
        delimiter_item.setSubmenu_(self._build_delimiter_menu())
        menu.addItem_(delimiter_item)

        for title, selector, value in (
            ("去重", "toggleDedupe:", cfg.dedupe),
            ("转换后自动粘贴", "toggleAutoPaste:", cfg.auto_paste),
            ("提示音", "toggleSound:", cfg.play_sound),
        ):
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, selector, "")
            item.setTarget_(self)
            item.setState_(NSOnState if value else 0)
            menu.addItem_(item)

        menu.addItem_(NSMenuItem.separatorItem())

        update_title = "检查更新…"
        if self._update_hint:
            update_title = f"有新版本 {self._update_hint} · 检查更新…"
        update_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(update_title, "checkUpdates:", "")
        update_item.setTarget_(self)
        menu.addItem_(update_item)

        settings_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("设置…", "openSettings:", ",")
        settings_item.setTarget_(self)
        menu.addItem_(settings_item)

        config_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "打开配置文件", "openConfigFile:", ""
        )
        config_item.setTarget_(self)
        menu.addItem_(config_item)

        if not paste.is_trusted():
            trust_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "授予“自动粘贴”权限…", "requestAccessibility:", ""
            )
            trust_item.setTarget_(self)
            menu.addItem_(trust_item)

        if self.hotkey_errors:
            error_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "⚠️ 快捷键被占用：" + "，".join(self.hotkey_errors), None, ""
            )
            error_item.setEnabled_(False)
            menu.addItem_(error_item)

        menu.addItem_(NSMenuItem.separatorItem())
        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("退出 TextConv", "quitApp:", "q")
        quit_item.setTarget_(self)
        menu.addItem_(quit_item)

        self.menu = menu
        self.status_item.setMenu_(menu)

    @objc.python_method
    def _build_delimiter_menu(self):
        submenu = NSMenu.alloc().initWithTitle_("分隔符")
        submenu.setAutoenablesItems_(False)
        for delim, title in core.BUILTIN_DELIMITERS:
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, "toggleDelimiter:", "")
            item.setTarget_(self)
            item.setRepresentedObject_(delim)
            item.setState_(NSOnState if self.config.is_delimiter_enabled(delim) else 0)
            submenu.addItem_(item)
        if self.config.custom_delimiters:
            submenu.addItem_(NSMenuItem.separatorItem())
            for delim in self.config.custom_delimiters:
                item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(f"自定义：{delim}", None, "")
                item.setEnabled_(False)
                submenu.addItem_(item)
        return submenu

    # ------------------------------------------------------------ 动作
    def convertFromMenu_(self, sender):
        fmt_key = sender.representedObject()
        self.perform_convert(str(fmt_key), from_menu=True)

    @objc.python_method
    def perform_convert(self, fmt_key: str, from_menu: bool = False):
        cfg = self.config
        text = clipboard.get_text()
        if not text.strip():
            self._flash("剪贴板为空")
            return
        # 连续按同一个热键时，剪贴板里已经是上次的结果；用原始输入重新转，
        # 避免 SQL 的单引号被反复转义、越转越多
        source = core.resolve_source_text(text, self._last_input, self._last_output)
        try:
            result = core.convert(
                source, fmt_key, delimiters=cfg.all_delimiters, dedupe=cfg.dedupe
            )
        except Exception as exc:  # 不让异常打断主循环
            log.exception("转换失败")
            self._flash("转换失败")
            return

        clipboard.set_text(result)
        self._last_input = source
        self._last_output = result
        if cfg.play_sound:
            self._play_sound()

        label = core.get_format(fmt_key).label
        if cfg.auto_paste:
            if paste.is_trusted():
                self._flash(f"✓ {label}")
                # 菜单还开着时立刻发 ⌘V 会被菜单吞掉，延迟一点
                self.performSelector_withObject_afterDelay_(
                    "doPaste:", None, 0.30 if from_menu else 0.22
                )
            else:
                self._flash("已复制，⌘V 粘贴")
        else:
            self._flash(f"✓ {label}")

    def doPaste_(self, sender):
        paste.send_paste()

    def toggleDelimiter_(self, sender):
        self.config.toggle_delimiter(str(sender.representedObject()))
        self.config.save()
        self._rebuild_menu()

    def toggleDedupe_(self, sender):
        self.config.dedupe = not self.config.dedupe
        self.config.save()
        self._rebuild_menu()

    def toggleAutoPaste_(self, sender):
        self.config.auto_paste = not self.config.auto_paste
        self.config.save()
        self._rebuild_menu()

    def toggleSound_(self, sender):
        self.config.play_sound = not self.config.play_sound
        self.config.save()
        self._rebuild_menu()

    def openSettings_(self, sender):
        if self.settings_window is None:
            self.settings_window = SettingsWindow.alloc().initWithConfig_callback_(
                self.config, self._apply_config
            )
        self.settings_window.show()

    @objc.python_method
    def _apply_config(self, cfg: Config):
        self.config = cfg
        self._register_hotkeys()
        self._write_state()
        self._rebuild_menu()

    def openConfigFile_(self, sender):
        path = config_path()
        if os.path.exists(path):
            NSWorkspace.sharedWorkspace().openFile_(path)
        else:
            self.config.save()
            NSWorkspace.sharedWorkspace().openFile_(path)

    def requestAccessibility_(self, sender):
        paste.request_trust()
        self._flash("请在系统设置里勾选 TextConv")

    def quitApp_(self, sender):
        NSApp.terminate_(None)

    # ------------------------------------------------------------ 快捷键
    @objc.python_method
    def _register_hotkeys(self):
        if self.hotkey_manager is None:
            self.hotkey_manager = HotKeyManager()
        else:
            self.hotkey_manager.unregister_all()
        self.hotkey_errors = []
        for fmt in core.FORMATS:
            combo = self.config.hotkeys.get(fmt.key, "")
            if not combo:
                continue
            ok = self.hotkey_manager.register(
                combo, lambda key=fmt.key: self.perform_convert(key)
            )
            if not ok:
                self.hotkey_errors.append(describe_combo(combo))

        # 兜底：菜单栏图标被挤出屏幕时，用 ⌃⌥⌘T 直接把菜单弹出来
        if self.hotkey_manager is not None:
            self.hotkey_manager.register("ctrl+alt+cmd+t", self._popup_menu)

        self._rebuild_menu()

    @objc.python_method
    def _popup_menu(self):
        """弹出状态栏菜单；图标不可见时退回到鼠标位置。"""
        try:
            item = self.status_item
            if item is None or self.menu is None:
                return
            button = item.button()
            if button is not None and button.window() is not None:
                button.performClick_(None)
                return
            from AppKit import NSEvent

            point = NSEvent.mouseLocation()
            self.menu.popUpMenuPositioningItem_atLocation_inView_(None, point, None)
        except Exception:
            log.exception("弹出菜单失败")

    @objc.python_method
    def _write_state(self):
        """把真实运行状态写盘，`tc --doctor` 读它来判断。"""
        state = {
            "pid": os.getpid(),
            "trusted": paste.is_trusted(),
            "hotkeys": dict(self.config.hotkeys),
            "hotkey_errors": list(self.hotkey_errors),
            "python": sys.executable,
            "version": __version__,
        }
        try:
            os.makedirs(app_dir(), exist_ok=True)
            with open(state_path(), "w", encoding="utf-8") as fh:
                json.dump(state, fh, ensure_ascii=False, indent=2)
        except Exception:
            log.exception("写状态文件失败")

    @objc.python_method
    def _maybe_request_permission(self):
        """自动粘贴需要辅助功能权限；没有就提示一次（不反复打扰）。"""
        if paste.is_trusted() or self.config.asked_permission:
            return
        self.config.asked_permission = True
        self.config.save()
        log.warning(
            "缺少辅助功能权限，自动粘贴不可用。需要给这个可执行文件授权：%s", sys.executable
        )
        paste.request_trust()

    @objc.python_method
    def _prime_activation(self):
        """让本 App 在 WindowServer 里“活跃过一次”。

        实测：从未激活过的后台 App 收不到 Carbon 热键事件；激活过一次之后
        即使退回后台也正常。这里激活 0.25 秒后把前台还给原来的 App。
        """
        try:
            front = NSWorkspace.sharedWorkspace().frontmostApplication()
        except Exception:
            front = None
        NSApp.activateIgnoringOtherApps_(True)
        if front is not None and front.processIdentifier() != os.getpid():
            self.performSelector_withObject_afterDelay_("restoreFrontApp:", front, 0.25)

    def restoreFrontApp_(self, app):
        try:
            if app is not None:
                app.activateWithOptions_(0)
        except Exception:
            pass

    # ------------------------------------------------------------ 其他
    @objc.python_method
    def _play_sound(self):
        for name in ("Tink", "Glass", "Pop"):
            sound = NSSound.soundNamed_(name)
            if sound is not None:
                sound.play()
                return

    # ------------------------------------------------------------ 自检
    def runSelfTest_(self, sender):
        checks = [
            ("status_item", self.status_item is not None),
            ("menu_items", len(self.menu.itemArray()) > 0),
            ("hotkeys", not self.hotkey_errors),
        ]
        try:
            window = SettingsWindow.alloc().initWithConfig_callback_(
                self.config, lambda cfg: None
            )
            checks.append(("settings_window", window is not None))
        except Exception as exc:  # pragma: no cover - 仅自检用
            print(f"settings_window FAILED: {exc}", file=sys.stderr)
            checks.append(("settings_window", False))

        # 顺便验证一次转换链路（不碰剪贴板）
        try:
            sample = core.convert(
                "苹果、香蕉, 橘子; 苹果", "sql", delimiters=self.config.all_delimiters, dedupe=True
            )
            checks.append(("convert", sample == "('苹果', '香蕉', '橘子')"))
        except Exception:
            log.exception("自检转换失败")
            checks.append(("convert", False))

        # 状态栏提示文字 + 恢复图标的路径
        try:
            self._flash("✓ 自检", 0.4)
            self.restoreIcon_(self._flash_token)
            checks.append(("flash", True))
        except Exception:
            log.exception("自检提示失败")
            checks.append(("flash", False))

        # 走一遍真实的“剪贴板 -> 转换 -> 写回剪贴板”，临时关掉自动粘贴
        original = clipboard.get_text()
        try:
            clipboard.set_text("苹果、香蕉、橘子")
            auto_paste = self.config.auto_paste
            self.config.auto_paste = False
            try:
                self.perform_convert("sql")
            finally:
                self.config.auto_paste = auto_paste
            checks.append(("roundtrip", clipboard.get_text() == "('苹果', '香蕉', '橘子')"))
        except Exception:
            log.exception("自检剪贴板链路失败")
            checks.append(("roundtrip", False))
        finally:
            clipboard.set_text(original)

        print(
            "SELFTEST " + " ".join(f"{name}={'ok' if ok else 'FAIL'}" for name, ok in checks),
            flush=True,
        )
        NSApp.terminate_(None)


def _acquire_single_instance():
    """同一个用户只允许一个菜单栏实例，避免出现两个图标/快捷键冲突。"""
    path = os.path.join(app_dir(), ".menubar.lock")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        handle = open(path, "w")
        import fcntl

        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        handle.write(str(os.getpid()))
        handle.flush()
        return handle
    except OSError:
        return None


def main(argv=None) -> int:
    _setup_logging()
    argv = list(sys.argv[1:] if argv is None else argv)
    self_test = "--self-test" in argv

    if not self_test:
        lock = _acquire_single_instance()
        if lock is None:
            print("TextConv 已经在运行了。", file=sys.stderr)
            return 0

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    delegate = MenuBarApp.alloc().init()
    app.setDelegate_(delegate)

    if self_test:
        delegate.performSelector_withObject_afterDelay_("runSelfTest:", None, 0.6)

    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
