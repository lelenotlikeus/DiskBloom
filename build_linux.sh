#!/usr/bin/env bash
set -euo pipefail
python -m PyInstaller --noconfirm --windowed --name DiskBloom --add-data "assets:assets" main.py
echo "Build complete. See dist/DiskBloom."
