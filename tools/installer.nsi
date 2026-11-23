; TextConv Windows 安装程序
; 由 tools/build_windows.sh 调用：makensis -DVERSION=... -DSTAGE=... -DOUT=... installer.nsi
Unicode true
!include "MUI2.nsh"

!ifndef VERSION
  !define VERSION "0.0.0"
!endif
!ifndef STAGE
  !error "缺少 -DSTAGE"
!endif
!ifndef OUT
  !define OUT "TextConv-Setup.exe"
!endif

!define APP_NAME "TextConv"
Name "${APP_NAME} ${VERSION}"
OutFile "${OUT}"
InstallDir "$LOCALAPPDATA\Programs\TextConv"
RequestExecutionLevel user
SetCompressor /SOLID lzma
ShowInstDetails show

!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN "$INSTDIR\run.bat"
!define MUI_FINISHPAGE_RUN_TEXT "启动 TextConv（托盘）"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "English"

Section "TextConv" SecMain
  SetOutPath "$INSTDIR"
  File /r "${STAGE}\*.*"

  DetailPrint "正在安装依赖并注册右键菜单（首次需要联网）..."
  ExecWait 'powershell -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\install.ps1" -NoStart' $0
  DetailPrint "install.ps1 退出码：$0"

  CreateDirectory "$SMPROGRAMS\TextConv"
  CreateShortCut "$SMPROGRAMS\TextConv\TextConv.lnk" "$INSTDIR\run.bat" "" "$INSTDIR\assets\textconv.ico"
  CreateShortCut "$SMPROGRAMS\TextConv\卸载 TextConv.lnk" "$INSTDIR\uninstall.bat"
SectionEnd
