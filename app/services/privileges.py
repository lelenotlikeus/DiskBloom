from __future__ import annotations

import ctypes
import platform
import sys
from pathlib import Path


def is_admin() -> bool:
    if platform.system() != "Windows":
        return hasattr(__import__("os"), "geteuid") and __import__("os").geteuid() == 0
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> bool:
    if platform.system() != "Windows":
        return False
    executable = sys.executable
    script = Path(sys.argv[0]).resolve()
    params = f'"{script}"'
    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1)
    return int(result) > 32
