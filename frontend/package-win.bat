@echo off
REM Build the Windows .exe using the shared PyInstaller spec
REM Usage: package-win.bat

where pyinstaller >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
  echo PyInstaller not found. Install with: pip install pyinstaller
  exit /b 1
)

set APP_NAME=FaxAutomationClient

REM Use the .spec so hiddenimports and options match other OS builds
pyinstaller --noconfirm FaxAutomationClient.spec

if %ERRORLEVEL% NEQ 0 (
  echo Build failed.
  exit /b %ERRORLEVEL%
)

echo Build complete. See dist\%APP_NAME%.exe
