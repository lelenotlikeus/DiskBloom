from __future__ import annotations

import os
from pathlib import Path
from time import perf_counter

from ..models import DiskItem, ScanResult, ScanStats
from .base import CancelCallback, ProgressCallback, ScanOptions, ScanProgress


class StandardScanner:
    """Fast, safe cross-platform scanner based on os.scandir."""

    name = "Standard"

    def __init__(
        self,
        progress_callback: ProgressCallback | None = None,
        cancel_callback: CancelCallback | None = None,
        options: ScanOptions | None = None,
    ) -> None:
        self.progress_callback = progress_callback
        self.cancel_callback = cancel_callback or (lambda: False)
        self.options = options or ScanOptions()
        self.stats = ScanStats(engine_name=self.name)
        self._seen_dirs: set[tuple[int, int]] = set()
        self._started = 0.0
        self._last_emit_count = 0

    def scan(self, path: str | Path) -> ScanResult:
        root_path = Path(path).expanduser().resolve()
        if not root_path.exists() or not root_path.is_dir():
            raise ValueError(f"Folder does not exist: {root_path}")

        self.stats = ScanStats(engine_name=self.name)
        self._seen_dirs.clear()
        self._started = perf_counter()
        self._last_emit_count = 0

        root = self._scan_dir(str(root_path), None)
        root.sort_children()
        self.stats.elapsed_seconds = max(perf_counter() - self._started, 0.000001)
        self._emit(str(root_path), force=True)
        return ScanResult(root=root, stats=self.stats)

    def _scan_dir(self, path: str, parent: DiskItem | None) -> DiskItem:
        name = os.path.basename(os.path.normpath(path)) or path
        item = DiskItem(name=name, path=Path(path), item_type="folder", parent=parent)
        self.stats.folders_scanned += 1

        try:
            stat = os.stat(path, follow_symlinks=False)
        except OSError as exc:
            self._record_error(path, exc)
            item.error = str(exc)
            return item

        item.modified = stat.st_mtime
        key = (stat.st_dev, stat.st_ino)
        if key in self._seen_dirs:
            item.error = "Skipped recursive link"
            self.stats.skipped_symlinks += 1
            return item
        self._seen_dirs.add(key)
        self._emit(path)

        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    if self.cancel_callback():
                        self.stats.cancelled = True
                        break
                    try:
                        if entry.is_symlink():
                            self.stats.skipped_symlinks += 1
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            child = self._scan_dir(entry.path, item)
                            item.children.append(child)
                            item.size += child.size
                        elif entry.is_file(follow_symlinks=False):
                            child = self._scan_file(entry, item)
                            item.children.append(child)
                            item.size += child.size
                    except OSError as exc:
                        self._record_error(entry.path, exc)
                    if self.stats.cancelled:
                        break
        except OSError as exc:
            self._record_error(path, exc)
            item.error = str(exc)
        return item

    def _scan_file(self, entry: os.DirEntry[str], parent: DiskItem) -> DiskItem:
        stat = entry.stat(follow_symlinks=False)
        size = stat.st_size
        item = DiskItem(
            name=entry.name,
            path=Path(entry.path),
            item_type="file",
            size=size,
            modified=stat.st_mtime,
            extension=os.path.splitext(entry.name)[1].lower(),
            parent=parent,
        )
        self.stats.files_scanned += 1
        self.stats.total_size += size
        if self.stats.largest_file is None or size > self.stats.largest_file.size:
            self.stats.largest_file = item
        self._emit(entry.path)
        return item

    def _record_error(self, path: str, exc: OSError) -> None:
        self.stats.permission_errors += 1
        if len(self.stats.errors) < 500:
            self.stats.errors.append(f"{path}: {exc}")

    def _emit(self, path: str, force: bool = False) -> None:
        if not self.progress_callback:
            return
        count = self.stats.files_scanned + self.stats.folders_scanned
        interval = max(1, self.options.progress_interval)
        if not force and count - self._last_emit_count < interval:
            return
        self._last_emit_count = count
        elapsed = max(perf_counter() - self._started, 0.000001)
        self.progress_callback(
            ScanProgress(
                current_path=Path(path),
                files_scanned=self.stats.files_scanned,
                folders_scanned=self.stats.folders_scanned,
                total_size=self.stats.total_size,
                elapsed_seconds=elapsed,
                files_per_second=self.stats.files_scanned / elapsed,
                folders_per_second=self.stats.folders_scanned / elapsed,
                bytes_per_second=self.stats.total_size / elapsed,
                engine_name=self.name,
            )
        )
