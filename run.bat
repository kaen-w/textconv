@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo 还没安装，先双击 install.bat
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m textconv.win_tray
exit /b 0
