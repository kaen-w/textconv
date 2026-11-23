#!/bin/bash
# TextConv 安装脚本：建虚拟环境 -> 装依赖 -> 安装右键服务 ->（可选）开机自启
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv"
PY="$VENV/bin/python"
PLIST="$HOME/Library/LaunchAgents/com.local.textconv.menubar.plist"
LABEL="com.local.textconv.menubar"

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m错误:\033[0m %s\n' "$*" >&2; }

UV="$(command -v uv || true)"

install_deps() {
  if [ ! -x "$PY" ]; then
    log "创建虚拟环境 $VENV"
    if [ -n "$UV" ]; then
      UV_CACHE_DIR="${UV_CACHE_DIR:-$ROOT/.uv-cache}" "$UV" venv --python 3.12 "$VENV"
    else
      python3 -m venv "$VENV"
    fi
  fi
  log "安装依赖（PyObjC）"
  if [ -n "$UV" ]; then
    UV_CACHE_DIR="${UV_CACHE_DIR:-$ROOT/.uv-cache}" "$UV" pip install \
      --python "$PY" -e "$ROOT" \
      pyobjc-framework-Cocoa pyobjc-framework-Quartz pyobjc-framework-ApplicationServices
  else
    "$PY" -m pip install --quiet --upgrade pip
    "$PY" -m pip install --quiet -e "$ROOT"
  fi
}

install_services() {
  log "安装右键服务到 ~/Library/Services"
  "$PY" -m textconv.services install --root "$ROOT" --python "$PY"
}

install_autostart() {
  log "注册开机自启（LaunchAgent）"
  mkdir -p "$HOME/Library/LaunchAgents"
  "$PY" - "$PLIST" "$ROOT" "$PY" <<'PYCODE'
import plistlib, sys
path, root, python = sys.argv[1:4]
data = {
    "Label": "com.local.textconv.menubar",
    "ProgramArguments": [python, "-m", "textconv.menubar"],
    "WorkingDirectory": root,
    "EnvironmentVariables": {"PYTHONPATH": root},
    "RunAtLoad": True,
    "ProcessType": "Interactive",
    "StandardOutPath": f"{root}/menubar.log",
    "StandardErrorPath": f"{root}/menubar.err.log",
}
with open(path, "wb") as fh:
    plistlib.dump(data, fh)
PYCODE
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null || launchctl load -w "$PLIST"
  log "已启动，菜单栏应该出现 TextConv 图标"
}

install_app() {
  log "生成 TextConv.app"
  if "$ROOT/tools/make_app.sh" /Applications >/dev/null 2>&1; then
    log "已生成 /Applications/TextConv.app（启动台/应用程序里可双击打开）"
  elif "$ROOT/tools/make_app.sh" "$HOME/Applications" >/dev/null 2>&1; then
    log "已生成 ~/Applications/TextConv.app"
  else
    log "App 生成失败（不影响菜单栏，可用 run.sh 启动）"
  fi
}

uninstall() {
  log "移除右键服务"
  "$PY" -m textconv.services uninstall || true
  log "移除开机自启"
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  rm -rf /Applications/TextConv.app "$HOME/Applications/TextConv.app"
  log "完成（虚拟环境 $VENV 未删除）"
}

case "${1:-}" in
  --autostart)
    install_deps && install_services && install_autostart && install_app
    ;;
  --uninstall)
    uninstall
    ;;
  "")
    install_deps && install_services && install_app
    cat <<EOF

下一步：
  1. 启动：双击 /Applications/TextConv.app（或 $ROOT/run.sh）
  2. 想要开机自启再跑：  $ROOT/install.sh --autostart
  3. 复制一段文本，按 ⌃⌥⌘S 试试（第一次会要求辅助功能权限）

EOF
    ;;
  *)
    echo "用法: $0 [--autostart|--uninstall]" >&2
    exit 1
    ;;
esac
