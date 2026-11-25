"""Windows 托盘 App：托盘菜单 + 全局热键 + 复制后自动粘贴。

启动：``pythonw -m textconv.win_tray``（用 pythonw 不会留控制台窗口）
自检：``python -m textconv.win_tray --self-test``
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time

from . import __version__, clipboard, core, paste, update
from .config import Config, app_dir, config_path, state_path
from .win_hotkeys import WinHotKeyManager, describe_combo, normalize_combo

log = logging.getLogger("textconv.tray")

APP_TITLE = "TextConv"


# ---------------------------------------------------------------- 小工具
def _asset_path(*parts: str) -> str:
    bundled = getattr(sys, "_MEIPASS", None)  # PyInstaller 打包后的解包目录
    if bundled:
        return os.path.join(bundled, "assets", *parts)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "assets", *parts)


def _make_icon():
    """优先用 assets 里设计好的图标，缺失时退回现画一个。"""
    from PIL import Image

    tray = _asset_path("logo-tray.png")
    if os.path.exists(tray):
        try:
            return Image.open(tray).convert("RGBA")
        except Exception:
            log.exception("读取托盘图标失败，改用内置绘制")

    from PIL import ImageDraw, ImageFont

    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((2, 2, size - 2, size - 2), radius=14, fill=(47, 107, 255, 255))

    font = None
    for path in (
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "segoeuib.ttf"),
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arialbd.ttf"),
    ):
        try:
            font = ImageFont.truetype(path, 30)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()
    draw.text((size / 2, size / 2 + 1), "TC", font=font, fill="white", anchor="mm")
    return image


def _beep() -> None:
    try:
        import winsound

        winsound.MessageBeep(0x00000040)  # MB_ICONASTERISK
    except Exception:
        pass


def _single_instance() -> bool:
    """命名互斥体：同一用户只跑一个托盘实例。"""
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CreateMutexW(None, False, "Local\\TextConvTray")
        return kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS
    except Exception:
        return True


# ---------------------------------------------------------------- 右键菜单
MENU_ITEMS = [
    ("01sql", "复制为 SQL IN 子句", "sql"),
    ("02excel", "复制为 Excel 粘贴", "excel"),
    ("03json", "复制为 JSON 数组", "json"),
    ("04tuple", "复制为 Python 元组", "tuple"),
    ("05list", "复制为 Python 列表", "list"),
    ("06column", "复制为 Excel 一列", "column"),
]
MENU_BASE = r"Software\Classes\*\shell\TextConv"


def _menu_command() -> str:
    """右键菜单调用的命令：自包含版是 exe 本身，源码版是 pythonw。"""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --file'
    exe = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return f'"{exe}" -m textconv.win_tray --file'


def register_context_menu() -> bool:
    try:
        import winreg

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, MENU_BASE) as key:
            winreg.SetValueEx(key, "MUIVerb", 0, winreg.REG_SZ, "TextConv 转换")
            winreg.SetValueEx(key, "SubCommands", 0, winreg.REG_SZ, "")
        for verb, label, fmt in MENU_ITEMS:
            path = rf"{MENU_BASE}\shell\{verb}"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
                winreg.SetValueEx(key, "MUIVerb", 0, winreg.REG_SZ, label)
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path + r"\command") as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f'{_menu_command()} {fmt} "%1"')
        log.info("右键菜单已注册")
        return True
    except Exception:
        log.exception("注册右键菜单失败")
        return False


def unregister_context_menu() -> bool:
    try:
        import winreg

        for verb, _, _ in MENU_ITEMS:
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"{MENU_BASE}\shell\{verb}\command")
            except FileNotFoundError:
                pass
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"{MENU_BASE}\shell\{verb}")
            except FileNotFoundError:
                pass
        for key in (rf"{MENU_BASE}\shell", MENU_BASE):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
            except FileNotFoundError:
                pass
        log.info("右键菜单已移除")
        return True
    except Exception:
        log.exception("移除右键菜单失败")
        return False


# ---------------------------------------------------------------- 托盘 App
class TrayApp:
    def __init__(self) -> None:
        import pystray

        self.pystray = pystray
        self.config = Config.load()
        self.hotkeys = WinHotKeyManager()
        self.hotkey_errors: list[str] = []
        self._last_input = None
        self._last_output = None
        self._last_action = 0.0
        self._paste_timer = None
        self._settings_proc = None
        self._icon = None
        self._create_icon()

    # -------------------------------------------------------- 菜单
    def _create_icon(self) -> None:
        self._icon = self.pystray.Icon(APP_TITLE, _make_icon(), APP_TITLE, self._menu())

    def _menu(self):
        pystray = self.pystray
        config = self.config
        items = []

        for fmt in core.FORMATS:
            combo = config.hotkeys.get(fmt.key, "")
            label = fmt.action
            if combo:
                label = f"{label}    {describe_combo(combo)}"
            items.append(pystray.MenuItem(label, self._convert_action(fmt.key)))

        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem("分隔符", pystray.Menu(*self._delimiter_items())))
        items.append(
            pystray.MenuItem(
                "去重（保持顺序）",
                self._toggle_dedupe,
                checked=lambda item: bool(self.config.dedupe),
            )
        )
        items.append(
            pystray.MenuItem(
                "转换后自动粘贴",
                self._toggle_auto_paste,
                checked=lambda item: bool(self.config.auto_paste),
            )
        )
        items.append(
            pystray.MenuItem(
                "提示音",
                self._toggle_sound,
                checked=lambda item: bool(self.config.play_sound),
            )
        )
        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem("注册资源管理器右键菜单", lambda icon, item: register_context_menu()))
        items.append(pystray.MenuItem("移除资源管理器右键菜单", lambda icon, item: unregister_context_menu()))
        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem("检查更新…", self._check_update))
        items.append(pystray.MenuItem("设置…", self._open_settings))
        items.append(pystray.MenuItem("打开配置文件", self._open_config))
        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem(f"版本 {__version__}", lambda icon, item: None, enabled=False))
        items.append(pystray.MenuItem("退出", self._quit))
        return pystray.Menu(*items)

    def _delimiter_items(self):
        pystray = self.pystray
        items = []
        for delimiter, title in core.BUILTIN_DELIMITERS:
            items.append(
                pystray.MenuItem(
                    title,
                    self._delimiter_action(delimiter),
                    checked=lambda item, d=delimiter: self.config.is_delimiter_enabled(d),
                )
            )
        if self.config.custom_delimiters:
            items.append(pystray.Menu.SEPARATOR)
            for delimiter in self.config.custom_delimiters:
                items.append(
                    pystray.MenuItem(
                        f"自定义：{delimiter}",
                        self._delimiter_action(delimiter),
                        checked=lambda item, d=delimiter: self.config.is_delimiter_enabled(d),
                    )
                )
        return items

    # -------------------------------------------------------- 动作工厂
    def _convert_action(self, fmt_key: str):
        def action(icon=None, item=None):
            self.perform_convert(fmt_key, from_menu=True)

        return action

    def _delimiter_action(self, delimiter: str):
        def action(icon=None, item=None):
            self.config.toggle_delimiter(delimiter)
            self.config.save()
            self._refresh()

        return action

    # -------------------------------------------------------- 转换
    def perform_convert(self, fmt_key: str, from_menu: bool = False) -> None:
        # 热键可能因为按住、双实例等原因被触发两次；这里再兜一层，
        # 0.4 秒内只处理第一次，避免“转换一次、粘贴两次”
        now = time.monotonic()
        if not from_menu and now - self._last_action < 0.4:
            log.info("忽略重复触发（间隔 %.2fs）", now - self._last_action)
            return
        self._last_action = now

        config = self.config
        text = clipboard.get_text()
        if not text.strip():
            self._notify("剪贴板是空的")
            return
        # 剪贴板里如果正是我们上次的输出，就换回原始输入再转，
        # 否则连续按会把引号越转越多（SQL 转义会翻倍单引号）
        source = core.resolve_source_text(text, self._last_input, self._last_output)
        try:
            result = core.convert(
                source, fmt_key, delimiters=config.all_delimiters, dedupe=config.dedupe
            )
        except Exception:
            log.exception("转换失败")
            self._notify("转换失败，见日志")
            return

        if not clipboard.set_text(result):
            log.warning("写入剪贴板失败（可能被其它程序占用）")
            self._notify("写入剪贴板失败，请重试")
            return
        log.info("转换 %s：%d 字 -> %d 字", fmt_key, len(source), len(result))
        self._last_input = source
        self._last_output = result
        if config.play_sound:
            _beep()

        label = core.get_format(fmt_key).label
        if config.auto_paste:
            # 热键是“按下瞬间”触发的，用户手还没松开：等一会儿、并主动松开修饰键，
            # 否则合成的 Ctrl+V 会变成 Ctrl+Alt+Shift+V，粘不进去
            self._paste_after(0.30 if from_menu else 0.25)
            self._notify(f"✓ {label}")
        else:
            self._notify(f"已复制：{label}")

    def _paste_after(self, delay: float) -> None:
        # 只允许一个待执行的粘贴，避免叠加
        if self._paste_timer is not None:
            self._paste_timer.cancel()

        def task():
            try:
                import keyboard

                for key in ("ctrl", "alt", "shift", "windows"):
                    try:
                        keyboard.release(key)
                    except Exception:
                        pass
            except Exception:
                pass
            time.sleep(0.03)
            log.info("发送 Ctrl+V")
            paste.send_paste()

        self._paste_timer = threading.Timer(delay, task)
        self._paste_timer.daemon = True
        self._paste_timer.start()

    # -------------------------------------------------------- 开关
    def _toggle_dedupe(self, icon=None, item=None):
        self.config.dedupe = not self.config.dedupe
        self.config.save()
        self._refresh()

    def _toggle_auto_paste(self, icon=None, item=None):
        self.config.auto_paste = not self.config.auto_paste
        self.config.save()
        self._refresh()

    def _toggle_sound(self, icon=None, item=None):
        self.config.play_sound = not self.config.play_sound
        self.config.save()
        self._refresh()

    # -------------------------------------------------------- 设置等
    def _open_settings(self, icon=None, item=None):
        if self._settings_proc is not None and self._settings_proc.poll() is None:
            return
        self._settings_proc = subprocess.Popen(
            [sys.executable, "-m", "textconv.win_settings"]
        )
        threading.Thread(target=self._wait_settings, args=(self._settings_proc,), daemon=True).start()

    def _wait_settings(self, proc):
        proc.wait()
        self.config = Config.load()
        self._register_hotkeys()
        self._refresh()

    def _open_config(self, icon=None, item=None):
        path = config_path()
        if not os.path.exists(path):
            self.config.save()
        os.startfile(path)  # noqa: S606 - Windows 专用

    def _quit(self, icon=None, item=None):
        self.hotkeys.stop()
        try:
            self._icon.stop()
        finally:
            # keyboard 的钩子线程有可能不是 daemon，直接结束进程免得“退出了还在跑”
            os._exit(0)

    # -------------------------------------------------------- 内部
    def _refresh(self) -> None:
        self._icon.update_menu()
        self._write_state()

    def _notify(self, message: str) -> None:
        try:
            self._icon.notify(message[:120], APP_TITLE)
        except Exception:
            pass

    def _write_state(self) -> None:
        state = {
            "pid": os.getpid(),
            "trusted": True,
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
            pass

    def _register_hotkeys(self) -> None:
        bindings = []
        self.hotkey_errors = []
        used: dict[str, str] = {}
        for fmt in core.FORMATS:
            combo = self.config.hotkeys.get(fmt.key, "")
            if not combo:
                continue
            normalized = normalize_combo(combo)
            if normalized in used:
                # 两个格式绑了同一个键：RegisterHotKey 只允许注册一次
                self.hotkey_errors.append(f"{describe_combo(combo)}（与{used[normalized]}重复）")
                continue
            used[normalized] = fmt.label
            bindings.append((combo, self._hotkey_action(fmt.key)))

        for combo in self.hotkeys.apply(bindings):
            if describe_combo(combo) not in self.hotkey_errors:
                self.hotkey_errors.append(f"{describe_combo(combo)}（可能被占用）")
        self._write_state()

    def _hotkey_action(self, fmt_key: str):
        def action():
            self.perform_convert(fmt_key, from_menu=False)

        return action

    # -------------------------------------------------------- 更新
    def _check_update(self, icon=None, item=None) -> None:
        threading.Thread(target=self._check_update_worker, args=(True,), daemon=True).start()

    def _check_update_worker(self, manual: bool) -> None:
        import ctypes

        import datetime

        release = update.fetch_latest()
        self.config.last_update_check = datetime.datetime.now().isoformat(timespec="seconds")
        try:
            self.config.save()
        except Exception:
            log.exception("保存检查时间失败")

        if release is None:
            if manual:
                ctypes.windll.user32.MessageBoxW(
                    None, "检查失败：连不上 GitHub。\n可以手动打开 Releases 页面下载。", "TextConv", 0x40
                )
            return

        if not update.is_newer(release.version, __version__):
            if manual:
                ctypes.windll.user32.MessageBoxW(
                    None, f"已经是最新版本（{__version__}）。", "TextConv", 0x40
                )
            return

        if not manual:
            try:
                self._icon.notify(f"新版本 {release.version} 可用，右键托盘 → 检查更新", "TextConv")
            except Exception:
                pass
            return

        answer = ctypes.windll.user32.MessageBoxW(
            None,
            f"发现新版本 {release.version}（当前 {__version__}）。\n\n现在下载并运行安装程序？",
            "TextConv 更新",
            0x04 | 0x40,  # MB_YESNO | MB_ICONINFORMATION
        )
        if answer != 6:  # IDYES
            return
        self._download_update(release)

    def _download_update(self, release) -> None:
        import ctypes
        import tempfile

        url = update.pick_asset(release, "win32")
        if not url:
            ctypes.windll.user32.MessageBoxW(None, "这个版本没有 Windows 安装包。", "TextConv", 0x30)
            return
        name = url.rsplit("/", 1)[-1]
        dest = os.path.join(tempfile.gettempdir(), name)

        def worker():
            try:
                update.download(url, dest)
                os.startfile(dest)  # noqa: S606 - Windows 专用
            except Exception as exc:
                log.exception("下载更新失败")
                ctypes.windll.user32.MessageBoxW(None, f"下载失败：{exc}", "TextConv", 0x30)

        threading.Thread(target=worker, daemon=True).start()

    # -------------------------------------------------------- 运行
    def run(self) -> None:
        log.info("TextConv 托盘启动，pid=%s", os.getpid())
        self._register_hotkeys()
        if self.config.check_updates and update.due_for_check(self.config.last_update_check):
            threading.Thread(target=self._check_update_worker, args=(False,), daemon=True).start()
        if self.hotkey_errors:
            self._notify("部分快捷键注册失败：" + "，".join(self.hotkey_errors))
        self._icon.run()


# ---------------------------------------------------------------- 自检
def self_test() -> int:
    checks = []

    def check(name, func):
        try:
            func()
            checks.append((name, True))
        except Exception as exc:
            print(f"{name} FAILED: {exc}", file=sys.stderr)
            checks.append((name, False))

    check("pystray", lambda: __import__("pystray"))
    check("PIL", lambda: __import__("PIL"))
    check("keyboard", lambda: __import__("keyboard"))
    check("pyperclip", lambda: __import__("pyperclip"))

    def clipboard_roundtrip():
        original = clipboard.get_text()
        try:
            clipboard.set_text("TextConv 自检 123")
            assert clipboard.get_text() == "TextConv 自检 123", "回读不一致"
        finally:
            clipboard.set_text(original)

    check("clipboard", clipboard_roundtrip)

    def menu_build():
        app = TrayApp()
        assert app._menu() is not None

    check("menu", menu_build)

    def hotkey_register():
        app = TrayApp()
        failed = app.hotkeys.apply([("ctrl+alt+shift+9", lambda: None)])
        app.hotkeys.stop()
        assert not failed, f"注册失败：{failed}"

    check("hotkey", hotkey_register)

    def convert():
        from .core import convert as do_convert

        result = do_convert("苹果、香蕉, 橘子", "sql", delimiters=["whitespace", "、", ","])
        assert result == "('苹果', '香蕉', '橘子')", result

    check("convert", convert)

    print("SELFTEST " + " ".join(f"{name}={'ok' if ok else 'FAIL'}" for name, ok in checks))
    return 0 if all(ok for _, ok in checks) else 1


# ---------------------------------------------------------------- 开机自启
def _startup_dir() -> str:
    return os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")),
        "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
    )


def install_autostart() -> int:
    """在“启动”文件夹里建一个指向 pythonw 的快捷方式。"""
    startup = _startup_dir()
    os.makedirs(startup, exist_ok=True)
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable
    link = os.path.join(startup, "TextConv.lnk")
    workdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$lnk = $ws.CreateShortcut('{link}'); "
        f"$lnk.TargetPath = '{pythonw}'; "
        "$lnk.Arguments = '-m textconv.win_tray'; "
        f"$lnk.WorkingDirectory = '{workdir}'; "
        "$lnk.Save()"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            check=True,
            capture_output=True,
        )
    except Exception as exc:
        print(f"创建开机自启失败：{exc}", file=sys.stderr)
        return 1
    print(f"已添加开机自启：{link}")
    return 0


def remove_autostart() -> int:
    link = os.path.join(_startup_dir(), "TextConv.lnk")
    try:
        os.remove(link)
        print(f"已移除开机自启：{link}")
        return 0
    except FileNotFoundError:
        print("没有设置开机自启。")
        return 0
    except Exception as exc:
        print(f"移除失败：{exc}", file=sys.stderr)
        return 1


def main(argv=None) -> int:
    try:
        os.makedirs(app_dir(), exist_ok=True)
        log_file = os.path.join(app_dir(), "tray.log")
    except Exception:
        log_file = None
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        filename=log_file,
    )
    argv = list(sys.argv[1:] if argv is None else argv)

    if "--file" in argv:
        index = argv.index("--file")
        try:
            fmt_key, path = argv[index + 1], argv[index + 2]
        except IndexError:
            print("用法: TextConv --file <format> <path>", file=sys.stderr)
            return 2
        from .fileconv import main as file_main

        return file_main([fmt_key, path])

    if "--register-menu" in argv:
        return 0 if register_context_menu() else 1
    if "--unregister-menu" in argv:
        return 0 if unregister_context_menu() else 1
    if "--self-test" in argv:
        return self_test()
    if "--install-autostart" in argv:
        return install_autostart()
    if "--remove-autostart" in argv:
        return remove_autostart()
    if sys.platform != "win32":
        print("textconv.win_tray 只能在 Windows 上运行。", file=sys.stderr)
        return 2
    if not _single_instance():
        print("TextConv 已经在运行。", file=sys.stderr)
        return 0

    # 自包含版没有安装脚本，首次启动时自己把右键菜单登记好
    if getattr(sys, "frozen", False) and "--no-register" not in argv:
        register_context_menu()

    app = TrayApp()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
