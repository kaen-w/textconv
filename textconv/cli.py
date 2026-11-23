"""命令行入口：``tc <格式>``，给右键服务、终端和脚本用。"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import List, Optional

from . import clipboard, core
from .config import Config, config_path


def _read_input(kind: str) -> str:
    if kind == "clipboard":
        return clipboard.get_text()
    if kind == "stdin":
        return sys.stdin.read()
    # auto：有管道就读管道，否则读剪贴板
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return clipboard.get_text()


def play_sound(name: str = "Tink") -> None:
    """后台播放系统提示音，不阻塞。"""
    try:
        subprocess.Popen(
            ["afplay", f"/System/Library/Sounds/{name}.aiff"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tc",
        description="把零散文本转成 SQL IN / Excel 粘贴 / JSON 数组 / Python 字面量。",
        epilog="示例：tc sql --clipboard --copy   # 剪贴板内容转成 SQL IN 并写回剪贴板",
    )
    parser.add_argument("format", nargs="?", help="输出格式，见 --formats")
    parser.add_argument(
        "--input",
        choices=("auto", "stdin", "clipboard"),
        default="auto",
        help="输入来源，默认：有管道读 stdin，否则读剪贴板",
    )
    parser.add_argument(
        "--output",
        choices=("stdout", "clipboard", "both"),
        default="stdout",
        help="输出去向，默认 stdout",
    )
    parser.add_argument("--copy", action="store_true", help="等价于 --output clipboard")
    parser.add_argument(
        "--paste", action="store_true", help="写回剪贴板并模拟 ⌘V 粘贴到前台 App"
    )
    parser.add_argument(
        "--delim",
        action="append",
        metavar="CHAR",
        help="自定义分隔符，可重复；指定后不再使用配置里的分隔符",
    )
    parser.add_argument("--no-whitespace", action="store_true", help="不按空白切分")
    parser.add_argument("--whitespace", action="store_true", help="强制按空白切分")
    parser.add_argument("--dedupe", dest="dedupe", action="store_true", default=None)
    parser.add_argument("--no-dedupe", dest="dedupe", action="store_false")
    parser.add_argument("--sound", action="store_true", help="结束后播放提示音")
    parser.add_argument("--formats", action="store_true", help="列出全部格式")
    parser.add_argument("--open-config", action="store_true", help="打开配置文件")
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="检查安装状态：权限 / 配置 / 右键服务 / 菜单栏进程",
    )
    parser.add_argument(
        "--service",
        action="store_true",
        help=argparse.SUPPRESS,  # 右键服务内部用：stdin -> 剪贴板 + stdout
    )
    return parser


def _resolve_delimiters(args: argparse.Namespace, cfg: Config) -> List[str]:
    if args.delim:
        delims = list(args.delim)
        if not args.no_whitespace:
            delims.insert(0, core.WHITESPACE)
        return delims
    delims = list(cfg.all_delimiters)
    if args.no_whitespace:
        delims = [d for d in delims if d != core.WHITESPACE]
    elif args.whitespace and core.WHITESPACE not in delims:
        delims.insert(0, core.WHITESPACE)
    return delims


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.doctor:
        return doctor()

    if args.formats:
        width = max(len(f.key) for f in core.FORMATS)
        for fmt in core.FORMATS:
            print(f"{fmt.key:<{width}}  {fmt.label:<14}  {fmt.hint}")
        return 0

    if args.open_config:
        path = config_path()
        if os.path.exists(path):
            subprocess.run(["open", "-t", path], check=False)
            return 0
        print(f"配置文件不存在：{path}", file=sys.stderr)
        return 1

    if not args.format:
        parser.print_help()
        return 2

    cfg = Config.load()
    try:
        core.get_format(args.format)
    except core.FormatError as exc:
        print(exc, file=sys.stderr)
        return 2

    text = _read_input(args.input)
    delimiters = _resolve_delimiters(args, cfg)
    dedupe = cfg.dedupe if args.dedupe is None else args.dedupe
    result = core.convert(text, args.format, delimiters=delimiters, dedupe=dedupe)

    # 右键服务：静默写剪贴板 + 输出（Automator 用它替换选中文本）
    if args.service:
        clipboard.set_text(result)
        if cfg.play_sound:
            play_sound()
        if result:
            sys.stdout.write(result)
        return 0

    output = args.output
    if args.copy:
        output = "clipboard"
    if output in ("clipboard", "both"):
        clipboard.set_text(result)
    if output in ("stdout", "both"):
        if not sys.stdout.isatty() or output == "both":
            sys.stdout.write(result + ("\n" if result else ""))
        else:
            print(result)
    if args.paste:
        from . import paste as paste_mod

        if paste_mod.is_trusted():
            paste_mod.send_paste()
        else:
            print(
                "未获得辅助功能权限，结果已复制到剪贴板，按 ⌘V 即可。",
                file=sys.stderr,
            )
    if args.sound:
        play_sound()
    return 0


def _describe_combo(combo: str) -> str:
    """按平台选展示方式（macOS 用 ⌃⌥⌘，Windows 用 Ctrl+Alt+Shift）。"""
    if sys.platform == "win32":
        from .win_hotkeys import describe_combo
    else:
        from .hotkeys import describe_combo
    return describe_combo(combo)


def doctor() -> int:
    """把“为什么不好使”需要用到的信息一次列出来。"""
    import os as _os
    import sys as _sys

    from . import paste as paste_mod
    from .config import app_dir, config_path, state_path

    from . import __version__ as code_version

    ok = True
    print(f"版本          {code_version}")
    print(f"当前解释器    {_sys.executable}")
    if _os.path.realpath(_sys.executable) != _sys.executable:
        print(f"  实际可执行   {_os.path.realpath(_sys.executable)}")

    path = config_path()
    print(f"配置文件      {path} {'（存在）' if _os.path.exists(path) else '（不存在，用默认值）'}")
    cfg = Config.load()
    print(f"分隔符        {cfg.all_delimiters}")
    print(f"去重          {'开' if cfg.dedupe else '关'}")

    # 菜单栏 App 的真实状态（不是本进程的）
    state = {}
    running = False
    try:
        import json as _json

        with open(state_path(), "r", encoding="utf-8") as fh:
            state = _json.load(fh)
        _os.kill(int(state.get("pid", 0)), 0)
        running = True
    except Exception:
        running = False

    if running:
        print(f"菜单栏 App    ✓ 正在运行 (pid={state.get('pid')})")
        running_version = state.get("version")
        if running_version and running_version != code_version:
            ok = False
            print(
                f"  [注意] 跑着的是 v{running_version}，代码是 v{code_version}；"
                "退出托盘重新启动才会生效"
            )
        trusted = bool(state.get("trusted"))
        print(f"  辅助功能     {'✓ 已授权，自动粘贴可用' if trusted else '✗ 未授权，只复制不粘贴'}")
        if not trusted:
            ok = False
            print(f"  去“系统设置 → 隐私与安全性 → 辅助功能”加入：{state.get('python')}")
        errors = state.get("hotkey_errors") or []
        print(f"  快捷键       {'✓ 全部注册成功' if not errors else '✗ 失败：' + '，'.join(errors)}")
        if errors:
            ok = False
        for key, combo in (state.get("hotkeys") or {}).items():
            print(f"    {key:<7} {_describe_combo(combo) if combo else '（未设置）'}")
    else:
        ok = False
        print("菜单栏 App    ✗ 未运行（./run.sh 或 ./install.sh --autostart）" if sys.platform == "darwin" else "托盘 App      ✗ 未运行（双击 run.bat）")

    if _sys.platform == "darwin":
        from .services import installed

        bundles = installed()
        print(f"右键服务      {len(bundles)}/{len(core.FORMATS)} 个已安装")
        if len(bundles) != len(core.FORMATS):
            ok = False
    else:
        print("右键服务      （仅 macOS 提供；Windows 用托盘菜单 + 全局热键）")

    print(f"本进程权限    {'✓' if paste_mod.is_trusted() else '✗'}（从终端跑时可能继承终端的权限）")
    return 0 if ok else 1

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
