#!/usr/bin/env bash
set -euo pipefail
PYTHON="${PYTHON:-python}"
if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi
"$PYTHON" -m PyInstaller --noconfirm --windowed --name DiskBloom --add-data "assets:assets" main.py
echo "Build complete. See dist/DiskBloom."
