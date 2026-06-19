from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import platform

from .base import CancelCallback, ProgressCallback, ScanOptions
from .everything_scanner import EverythingScanner, is_available as everything_available
from .parallel_scanner import ParallelScanner
from .standard_scanner import StandardScanner
from .windows_fast_scanner import WindowsFastScanner, detect_capability


@dataclass(slots=True)
class ScannerCapability:
    key: str
    name: str
    available: bool
    reason: str = ""


def get_scanner_capabilities(path: str | Path | None = None) -> list[ScannerCapability]:
    everything_ok, everything_reason, _ = everything_available()
    capabilities = [
        ScannerCapability("standard", StandardScanner.name, True, "Cross-platform os.scandir scanner."),
        ScannerCapability("parallel", ParallelScanner.name, True, "Directory-level threaded filesystem scanner."),
        ScannerCapability("everything", EverythingScanner.name, everything_ok, everything_reason),
        ScannerCapability("windows_fast", "Windows Fast / Experimental", False, "Not implemented. Future MFT/USN backend."),
    ]
    return capabilities


def choose_scanner(
    path: str | Path,
    options: ScanOptions | None = None,
    progress_callback: ProgressCallback | None = None,
    cancel_callback: CancelCallback | None = None,
):
    options = options or ScanOptions()
    engine = options.engine.lower().replace("-", "_").replace(" ", "_")
    if engine in {"standard", "safe"}:
        return StandardScanner(progress_callback, cancel_callback, options)
    if engine == "parallel":
        return ParallelScanner(progress_callback, cancel_callback, options)
    if engine == "everything":
        ok, _, _ = everything_available(options.everything_cli_path)
        if ok:
            return EverythingScanner(progress_callback, cancel_callback, options)
        return StandardScanner(progress_callback, cancel_callback, options)
    if engine in {"windows_fast", "windows", "fast"}:
        fast = detect_capability(path)
        if fast.available:
            return WindowsFastScanner(progress_callback, cancel_callback, options)
        return StandardScanner(progress_callback, cancel_callback, options)
    if options.prefer_indexed:
        ok, _, _ = everything_available(options.everything_cli_path)
        if ok:
            return EverythingScanner(progress_callback, cancel_callback, options)
    if platform.system() == "Windows":
        return ParallelScanner(progress_callback, cancel_callback, options)
    return StandardScanner(progress_callback, cancel_callback, options)
