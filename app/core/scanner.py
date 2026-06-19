from __future__ import annotations

from pathlib import Path

from .models import ScanResult, ScanStats
from .scanners.base import CancelCallback, ProgressCallback, ScanOptions, ScanProgress
from .scanners.capabilities import choose_scanner


class DiskScanner:
    """Compatibility facade that selects the configured scan backend."""

    def __init__(
        self,
        progress_callback: ProgressCallback | None = None,
        cancel_callback: CancelCallback | None = None,
        progress_interval: int = 80,
        engine: str = "auto",
        everything_cli_path: str = "",
        parallel_workers: int = 0,
        prefer_indexed: bool = True,
        options: ScanOptions | None = None,
    ) -> None:
        self.progress_callback = progress_callback
        self.cancel_callback = cancel_callback or (lambda: False)
        self.options = options or ScanOptions(
            engine=engine,
            progress_interval=progress_interval,
            everything_cli_path=everything_cli_path,
            workers=parallel_workers,
            prefer_indexed=prefer_indexed,
        )
        self.stats = ScanStats()
        self.backend_name = "Auto"

    def scan(self, path: str | Path) -> ScanResult:
        backend = choose_scanner(path, self.options, self.progress_callback, self.cancel_callback)
        self.backend_name = backend.name
        result = backend.scan(path)
        self.stats = result.stats
        return result
