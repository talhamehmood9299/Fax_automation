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

# Place chromedriver next to the built binary so the path is consistent across OSes
OS_NAME=$(uname -s || echo unknown)
if [ "$OS_NAME" = "Darwin" ]; then
  DEST_DIR="dist/$APP_NAME.app/Contents/MacOS"
else
  DEST_DIR="dist"
fi

if [ -f ./chromedriver ]; then
  mkdir -p "$DEST_DIR"
  cp -f ./chromedriver "$DEST_DIR/chromedriver"
  echo "Copied chromedriver to $DEST_DIR/chromedriver"
else
  echo "Note: ./chromedriver not found in repo root. Skipping copy."
fi

# Copy frontend/.env to the build output so the packaged app picks it up
if [ -f ./frontend/.env ]; then
  mkdir -p "$DEST_DIR"
  cp -f ./frontend/.env "$DEST_DIR/.env"
  echo "Copied frontend/.env to $DEST_DIR/.env"
else
  echo "Note: frontend/.env not found. The app will default to http://localhost:8000 unless a .env is placed next to the binary."
fi

echo "Build complete. Binary and (optional) chromedriver are in $DEST_DIR"
