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

REM Place chromedriver.exe next to the built .exe for consistent path
if exist chromedriver.exe (
  copy /Y chromedriver.exe dist\chromedriver.exe >nul
  if %ERRORLEVEL% EQU 0 (
    echo Copied chromedriver.exe to dist\chromedriver.exe
  ) else (
    echo Warning: Failed to copy chromedriver.exe to dist\
  )
) else (
  echo Note: chromedriver.exe not found in repo root. Skipping copy.
)

REM No .env needed; client now uses built-in settings
echo Note: .env is no longer required; client uses built-in settings.
echo Build complete. See dist\%APP_NAME%.exe
