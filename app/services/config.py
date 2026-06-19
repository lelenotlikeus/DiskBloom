from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import Any


LEGACY_APP_DIR = Path.home() / ".diskbloom"


def _default_app_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA")
        return Path(base) / "DiskBloom" if base else LEGACY_APP_DIR
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "DiskBloom"
    base = os.environ.get("XDG_CONFIG_HOME")
    return (Path(base) if base else Path.home() / ".config") / "diskbloom"


APP_DIR = _default_app_dir()
CONFIG_PATH = APP_DIR / "config.json"
LEGACY_CONFIG_PATH = LEGACY_APP_DIR / "config.json"


def _migrate_legacy_config() -> None:
    if CONFIG_PATH.exists() or not LEGACY_CONFIG_PATH.exists():
        return
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(LEGACY_CONFIG_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    except OSError:
        pass


def load_config() -> dict[str, Any]:
    _migrate_legacy_config()
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(config: dict[str, Any]) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
