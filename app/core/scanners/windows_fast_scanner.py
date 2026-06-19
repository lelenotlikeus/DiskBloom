from __future__ import annotations

import ctypes
import os
import platform
from dataclasses import dataclass
from pathlib import Path

from ..models import ScanResult
from .base import CancelCallback, ProgressCallback, ScanOptions, ScannerUnavailable


@dataclass(slots=True)
class WindowsFastCapability:
    is_windows: bool
    volume_root: str
    filesystem: str
    is_ntfs: bool
    is_admin: bool
    available: bool
    reason: str


def _is_admin() -> bool:
    if platform.system() != "Windows":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _volume_root(path: Path) -> str:
    if platform.system() != "Windows":
        return ""
    buffer = ctypes.create_unicode_buffer(260)
    ok = ctypes.windll.kernel32.GetVolumePathNameW(str(path), buffer, len(buffer))
    return buffer.value if ok else path.anchor


def _filesystem_name(volume_root: str) -> str:
    if not volume_root:
        return ""
    fs_name = ctypes.create_unicode_buffer(64)
    ok = ctypes.windll.kernel32.GetVolumeInformationW(
        ctypes.c_wchar_p(volume_root),
        None,
        0,
        None,
        None,
        None,
        fs_name,
        len(fs_name),
    )
    return fs_name.value if ok else ""


def detect_capability(path: str | Path) -> WindowsFastCapability:
    if platform.system() != "Windows":
        return WindowsFastCapability(False, "", "", False, False, False, "Windows Fast is Windows-only.")
    root = _volume_root(Path(path).expanduser().resolve())
    fs = _filesystem_name(root)
    is_ntfs = fs.upper() == "NTFS"
    admin = _is_admin()
    if not is_ntfs:
        return WindowsFastCapability(True, root, fs, False, admin, False, f"Volume filesystem is {fs or 'unknown'}, not NTFS.")
    reason = (
        "NTFS detected, but the MFT/USN backend is not implemented safely yet. "
        "DiskBloom falls back to the optimized Standard scanner."
    )
    return WindowsFastCapability(True, root, fs, True, admin, False, reason)


class WindowsFastScanner:
    """Experimental placeholder for future read-only NTFS MFT/USN scanning.

    This class intentionally refuses to scan until a real MFT/USN implementation exists.
    Falling back is handled by the scanner selector; this avoids pretending that a normal
    recursive walk is an MFT scanner.
    """

    name = "Windows Fast / Experimental"

    def __init__(
        self,
        progress_callback: ProgressCallback | None = None,
        cancel_callback: CancelCallback | None = None,
        options: ScanOptions | None = None,
    ) -> None:
        self.progress_callback = progress_callback
        self.cancel_callback = cancel_callback or (lambda: False)
        self.options = options or ScanOptions(engine="windows_fast")

    def scan(self, path: str | Path) -> ScanResult:
        capability = detect_capability(path)
        raise ScannerUnavailable(capability.reason)
