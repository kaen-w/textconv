#!/bin/bash
# 双击把 TextConv 拉起来（已在运行则什么都不做）
LABEL="com.local.textconv.menubar"
ROOT="$(cd "$(dirname "$0")" && pwd)"
RUNNER="$ROOT/.venv/bin/python -m textconv.menubar"

if ps -Ao command= | grep -qxF "$RUNNER"; then
  echo "TextConv 已经在运行了 —— 看菜单栏。"
  exit 0
fi

if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
  launchctl kickstart "gui/$(id -u)/$LABEL" && echo "TextConv 已启动 —— 看菜单栏。"
  exit 0
fi

if [ -d /Applications/TextConv.app ]; then
  open -a /Applications/TextConv.app && echo "TextConv 已启动 —— 看菜单栏。"
  exit 0
fi

echo "前台启动（关掉终端就退出）..."
exec "$ROOT/.venv/bin/python" -m textconv.menubar
