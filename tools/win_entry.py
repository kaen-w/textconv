"""Windows 打包入口：托盘 App（同时处理 --file / --register-menu 等参数）。"""

import sys

from textconv.win_tray import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
