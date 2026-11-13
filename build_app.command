#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
command -v uv >/dev/null 2>&1 || {
  echo "uv is required. Install it: https://docs.astral.sh/uv/getting-started/installation/"
  exit 1
}

app="$HOME/Applications/Frame.app"

rm -rf build dist
mkdir -p build
/usr/bin/iconutil --convert icns --output build/Frame.icns Frame.iconset
uv run --isolated --no-managed-python --python 3.12 --group build python setup.py py2app
/usr/bin/codesign --force --deep --sign - dist/Frame.app

mkdir -p "$HOME/Applications"
rm -rf "$app"
/usr/bin/ditto dist/Frame.app "$app"
/usr/bin/open "$app"
