#!/bin/bash
# 启动菜单栏 App（前台运行，Ctrl+C 退出）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "还没装依赖，先运行 $ROOT/install.sh" >&2
  exit 1
fi
cd "$ROOT"
exec "$ROOT/.venv/bin/python" -m textconv.menubar "$@"
