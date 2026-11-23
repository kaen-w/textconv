#!/bin/bash
# 构建 macOS 安装包：dist/TextConv.app + dist/TextConv-<version>.dmg
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# CI 里没有 .venv，退回系统 python
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"

VERSION="$(sed -n 's/.*__version__ = "\(.*\)".*/\1/p' textconv/__init__.py | head -1)"
APP="dist/TextConv.app"
DMG="dist/TextConv-$VERSION.dmg"

rm -rf build dist .pyinstaller
PYINSTALLER_CONFIG_DIR="$ROOT/.pyinstaller" \
  "$PY" -m PyInstaller \
  --windowed --noconfirm --clean \
  --name TextConv \
  --icon assets/TextConv.icns \
  --add-data "assets:assets" \
  --osx-bundle-identifier com.local.textconv \
  --paths "$ROOT" --collect-submodules textconv \
  --hidden-import objc --hidden-import AppKit --hidden-import Quartz --hidden-import ApplicationServices \
  tools/app_entry.py

# 菜单栏 App：不显示 Dock 图标
plutil -insert LSUIElement -bool YES "$APP/Contents/Info.plist" 2>/dev/null || \
  plutil -replace LSUIElement -bool YES "$APP/Contents/Info.plist"

codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || true

# 打包 dmg
STAGE="$(mktemp -d)"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "TextConv" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
rm -rf "$STAGE"

echo "已生成："
echo "  $ROOT/$APP"
echo "  $ROOT/$DMG"
