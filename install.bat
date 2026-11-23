@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Unblock-File -Path '%~dp0install.ps1' -ErrorAction SilentlyContinue" >nul 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
echo.
pause
exit /b 0
