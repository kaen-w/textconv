@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "LOG=%APPDATA%\TextConv\install.log"

if exist "%LOG%" (
    echo ===== 安装日志 %LOG% =====
    type "%LOG%"
    echo ================================
    echo.
)

if exist ".venv\Scripts\python.exe" (
    echo 以控制台模式启动托盘，日志直接打印在这里。Ctrl+C 退出。
    ".venv\Scripts\python.exe" -m textconv.win_tray
    pause
    exit /b 0
)

echo 没有找到 .venv（说明上次安装没走完），改为重新运行安装脚本。
echo 下面会显示完整报错，装完可以按任意键关闭。
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -NoStart
echo.
echo 安装脚本退出码：%ERRORLEVEL%
pause
exit /b 0
