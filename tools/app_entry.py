"""打包入口：菜单栏 App 和 CLI（右键服务）共用一个可执行文件。"""

import sys


def main() -> int:
    argv = sys.argv[1:]
    if any(flag in argv for flag in ("--service", "--doctor", "--formats", "--check-update")):
        from textconv.cli import main as cli_main

        return cli_main(argv)

    from textconv.menubar import main as menubar_main

    return menubar_main()


if __name__ == "__main__":
    raise SystemExit(main())
