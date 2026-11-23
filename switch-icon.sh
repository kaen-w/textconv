#!/bin/bash
# 切换 macOS 菜单栏图标
# 用法：./switch-icon.sh tile_ts | clipboard | document | document_ts | bubble
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
STYLE="${1:-document_ts}"
RUNNER="$ROOT/.venv/bin/python -m textconv.menubar"
LABEL="com.local.textconv.menubar"

cd "$ROOT"
"$ROOT/.venv/bin/python" tools/make_logo.py --menubar "$STYLE" | grep menubar

# 先杀掉正在跑的实例（不管它是 launchd 起的还是 .app 起的），否则新图标不会生效
ps -Ao pid=,command= | grep -F "$RUNNER" | grep -v grep | awk '{print $1}' | while read -r pid; do
  kill "$pid" 2>/dev/null || true
done
sleep 1

if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
  launchctl kickstart "gui/$(id -u)/$LABEL"
else
  open -a /Applications/TextConv.app 2>/dev/null || "$ROOT/run.sh" &
fi
echo "菜单栏图标已切换为：$STYLE"
