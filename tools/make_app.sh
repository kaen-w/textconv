#!/bin/bash
# 生成 /Applications/TextConv.app（轻量包装：内部直接跑项目 venv 里的 Python）
# 用法：tools/make_app.sh [输出目录，默认 /Applications]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET_DIR="${1:-/Applications}"
APP="$TARGET_DIR/TextConv.app"
VERSION="$(sed -n 's/.*__version__ = "\(.*\)".*/\1/p' "$ROOT/textconv/__init__.py" | head -1)"
LABEL="com.local.textconv.menubar"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# 图标
cp "$ROOT/assets/TextConv.icns" "$APP/Contents/Resources/TextConv.icns"

# 启动脚本：已在跑就直接退出，否则用项目 venv 启动
cat > "$APP/Contents/MacOS/TextConv" <<LAUNCHER
#!/bin/bash
ROOT="$ROOT"
# 已经在跑（不管是 launchd 还是 App 启动的）就什么都不做。
# 用整行精确匹配：pgrep -f 是子串匹配，会把命令行里带这几个字的 shell 也误判成"已在运行"。
if ps -Ao command= | grep -qxF "\$ROOT/.venv/bin/python -m textconv.menubar"; then
  exit 0
fi
cd "\$ROOT"
exec "\$ROOT/.venv/bin/python" -m textconv.menubar
LAUNCHER
chmod +x "$APP/Contents/MacOS/TextConv"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleName</key><string>TextConv</string>
	<key>CFBundleDisplayName</key><string>TextConv</string>
	<key>CFBundleIdentifier</key><string>com.local.textconv</string>
	<key>CFBundleExecutable</key><string>TextConv</string>
	<key>CFBundlePackageType</key><string>APPL</string>
	<key>CFBundleShortVersionString</key><string>$VERSION</string>
	<key>CFBundleVersion</key><string>$VERSION</string>
	<key>CFBundleIconFile</key><string>TextConv</string>
	<key>LSUIElement</key><true/>
	<key>LSMinimumSystemVersion</key><string>11.0</string>
	<key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

printf 'APPL????' > "$APP/Contents/PkgInfo"
codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || true

echo "已生成：$APP"
echo "  版本：$VERSION"
echo "  项目路径：$ROOT"
