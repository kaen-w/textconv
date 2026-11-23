#!/bin/bash
# 构建 Windows 安装包：dist/TextConv-Setup-<version>.exe（需要 makensis）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="$(sed -n 's/.*__version__ = "\(.*\)".*/\1/p' textconv/__init__.py | head -1)"
STAGE="$ROOT/build/win-staging"

if ! command -v makensis >/dev/null; then
  echo "缺少 makensis。macOS: brew install nsis；Debian: apt install nsis" >&2
  exit 1
fi

rm -rf "$STAGE" && mkdir -p "$STAGE"
FILES=(
  install.bat uninstall.bat install.ps1 run.bat debug.bat
  requirements-win.txt pyproject.toml README-Windows.md 更新说明.txt
  assets/textconv.ico assets/logo-tray.png assets/logo-64.png assets/logo.svg
)
for f in textconv/*.py; do FILES+=("$f"); done
for f in "${FILES[@]}"; do
  mkdir -p "$STAGE/$(dirname "$f")"
  cp "$f" "$STAGE/$f"
done

mkdir -p "$ROOT/dist"
makensis -V2 -DVERSION="$VERSION" -DSTAGE="$STAGE" \
  -DOUT="$ROOT/dist/TextConv-Setup-$VERSION.exe" "$ROOT/tools/installer.nsi"

echo "已生成：$ROOT/dist/TextConv-Setup-$VERSION.exe"
