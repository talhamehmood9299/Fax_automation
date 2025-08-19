@echo off
REM Build a single-file Windows .exe using PyInstaller
REM Usage: package-win.bat

where pyinstaller >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
  echo PyInstaller not found. Install with: pip install pyinstaller
  exit /b 1
)

set APP_NAME=FaxAutomationClient
set ENTRY=frontend\client.py

pyinstaller --noconfirm --onefile --windowed --name %APP_NAME% %ENTRY%

echo Build complete. See dist\%APP_NAME%.exe

