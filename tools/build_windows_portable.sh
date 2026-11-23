#!/bin/bash
# 构建 Windows 自包含 exe：dist/TextConv-Portable-<version>.exe（需在 Windows 上跑）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-python}"
VERSION="$(sed -n 's/.*__version__ = "\(.*\)".*/\1/p' textconv/__init__.py | head -1)"
SEP="$("$PY" -c 'import os; print(os.pathsep)')"

"$PY" -m PyInstaller --noconfirm --clean --onefile --noconsole \
  --name TextConvPortable \
  --icon assets/textconv.ico \
  --add-data "assets${SEP}assets" \
  --hidden-import pystray._win32 \
  tools/win_entry.py

mkdir -p dist
mv -f "dist/TextConvPortable.exe" "dist/TextConv-Portable-$VERSION.exe"
echo "已生成：$ROOT/dist/TextConv-Portable-$VERSION.exe"
