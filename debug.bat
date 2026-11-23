@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo 还没安装，先双击 install.bat
    pause
    exit /b 1
)
echo 以控制台模式启动，日志会直接打印在这里。Ctrl+C 退出。
".venv\Scripts\python.exe" -m textconv.win_tray
pause
