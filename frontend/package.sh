#!/usr/bin/env bash
set -euo pipefail

# Build a single-file desktop app for the frontend using PyInstaller
# Usage:
#   bash frontend/package.sh

HERE=$(cd "$(dirname "$0")" && pwd)
cd "$HERE/.."

if ! command -v pyinstaller >/dev/null 2>&1; then
  echo "PyInstaller not found. Install with: pip install pyinstaller" >&2
  exit 1
fi

echo "PyInstaller version: $(pyinstaller --version || echo unknown)"
echo "setuptools version: $(python - <<'PY'
import pkg_resources
try:
    print(pkg_resources.get_distribution('setuptools').version)
except Exception:
    print('unknown')
PY
)"
echo "If build fails, try: pip install --upgrade 'pyinstaller>=6.10.0' 'setuptools>=71.0.0'"

APP_NAME="FaxAutomationClient"
ENTRY="frontend/client.py"

pyinstaller \
  --noconfirm \
  --clean \
  --onefile \
  --windowed \
  --hidden-import six \
  --hidden-import pkg_resources \
  --hidden-import appdirs \
  --hidden-import packaging \
  --hidden-import pyparsing \
  --hidden-import setuptools \
  --hidden-import markupsafe \
  --name "$APP_NAME" \
  "$ENTRY"

echo "Build complete. Single file is in dist/$APP_NAME (Linux/mac) or dist/$APP_NAME.exe (Windows)"
