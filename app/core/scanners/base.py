from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from ..models import ScanResult


@dataclass(slots=True)
class ScanProgress:
    current_path: Path
    files_scanned: int
    folders_scanned: int
    total_size: int
    elapsed_seconds: float = 0.0
    files_per_second: float = 0.0
    folders_per_second: float = 0.0
    bytes_per_second: float = 0.0
    engine_name: str = "Standard"


ProgressCallback = Callable[[ScanProgress], None]
CancelCallback = Callable[[], bool]


@dataclass(slots=True)
class ScanOptions:
    engine: str = "auto"
    progress_interval: int = 80
    detailed_metadata: bool = True
    follow_symlinks: bool = False
    parallel: bool = False
    workers: int = 0
    everything_cli_path: str = ""
    prefer_indexed: bool = True


class ScannerUnavailable(RuntimeError):
    """Raised when a requested scan engine cannot run on this path/system."""


class ScannerBackend(Protocol):
    name: str

    def scan(self, path: str | Path) -> ScanResult:
        ...
