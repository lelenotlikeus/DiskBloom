from __future__ import annotations

import os
import queue
import threading
from pathlib import Path
from time import perf_counter

from ..models import DiskItem, ScanResult, ScanStats
from .base import CancelCallback, ProgressCallback, ScanOptions, ScanProgress


class ParallelScanner:
    """Directory-level parallel scanner for large Windows/Linux/macOS trees."""

    name = "Parallel"

    def __init__(
        self,
        progress_callback: ProgressCallback | None = None,
        cancel_callback: CancelCallback | None = None,
        options: ScanOptions | None = None,
    ) -> None:
        self.progress_callback = progress_callback
        self.cancel_callback = cancel_callback or (lambda: False)
        self.options = options or ScanOptions(engine="parallel")
        self.stats = ScanStats(engine_name=self.name, source="filesystem")
        self._started = 0.0
        self._last_emit_count = 0
        self._lock = threading.Lock()
        self._seen_lock = threading.Lock()
        self._seen_dirs: set[tuple[int, int]] = set()

    def scan(self, path: str | Path) -> ScanResult:
        root_path = Path(path).expanduser().resolve()
        if not root_path.exists() or not root_path.is_dir():
            raise ValueError(f"Folder does not exist: {root_path}")

        self.stats = ScanStats(engine_name=self.name, source="filesystem")
        self._seen_dirs.clear()
        self._started = perf_counter()
        self._last_emit_count = 0
        root = DiskItem(root_path.name or str(root_path), root_path, "folder")
        work: queue.Queue[DiskItem | None] = queue.Queue()
        work.put(root)
        workers = self._worker_count()
        threads = [threading.Thread(target=self._worker, args=(work,), daemon=True) for _ in range(workers)]
        for thread in threads:
            thread.start()
        work.join()
        for _ in threads:
            work.put(None)
        for thread in threads:
            thread.join()

        root.recalculate_size()
        root.sort_children()
        self.stats.elapsed_seconds = max(perf_counter() - self._started, 0.000001)
        self._emit(str(root_path), force=True)
        return ScanResult(root, self.stats)

    def _worker_count(self) -> int:
        if self.options.workers > 0:
            return max(1, min(32, self.options.workers))
        cpu = os.cpu_count() or 2
        return max(2, min(8, cpu * 2))

    def _worker(self, work: queue.Queue[DiskItem | None]) -> None:
        while True:
            item = work.get()
            try:
                if item is None:
                    return
                if self.cancel_callback():
                    with self._lock:
                        self.stats.cancelled = True
                    continue
                self._scan_directory(item, work)
            finally:
                work.task_done()

    def _scan_directory(self, item: DiskItem, work: queue.Queue[DiskItem | None]) -> None:
        path = str(item.path)
        try:
            stat = os.stat(path, follow_symlinks=False)
        except OSError as exc:
            self._record_error(path, exc)
            item.error = str(exc)
            return

        item.modified = stat.st_mtime
        key = (stat.st_dev, stat.st_ino)
        with self._seen_lock:
            if key in self._seen_dirs:
                item.error = "Skipped recursive link"
                with self._lock:
                    self.stats.skipped_symlinks += 1
                return
            self._seen_dirs.add(key)

        with self._lock:
            self.stats.folders_scanned += 1
        self._emit(path)

        try:
            with os.scandir(path) as entries:
                local_files = 0
                local_size = 0
                local_largest: DiskItem | None = None
                local_skipped = 0
                for entry in entries:
                    if self.cancel_callback():
                        with self._lock:
                            self.stats.cancelled = True
                        break
                    try:
                        if entry.is_symlink():
                            local_skipped += 1
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            child = DiskItem(entry.name, Path(entry.path), "folder", parent=item)
                            item.children.append(child)
                            work.put(child)
                        elif entry.is_file(follow_symlinks=False):
                            child = self._scan_file(entry, item)
                            item.children.append(child)
                            local_files += 1
                            local_size += child.size
                            if local_largest is None or child.size > local_largest.size:
                                local_largest = child
                    except OSError as exc:
                        self._record_error(entry.path, exc)
                if local_files or local_size or local_largest or local_skipped:
                    with self._lock:
                        self.stats.files_scanned += local_files
                        self.stats.total_size += local_size
                        self.stats.skipped_symlinks += local_skipped
                        if local_largest and (self.stats.largest_file is None or local_largest.size > self.stats.largest_file.size):
                            self.stats.largest_file = local_largest
        except OSError as exc:
            self._record_error(path, exc)
            item.error = str(exc)

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
        self._emit(entry.path)
        return item

    def _record_error(self, path: str, exc: OSError) -> None:
        with self._lock:
            self.stats.permission_errors += 1
            if len(self.stats.errors) < 500:
                self.stats.errors.append(f"{path}: {exc}")

    def _emit(self, path: str, force: bool = False) -> None:
        if not self.progress_callback:
            return
        with self._lock:
            count = self.stats.files_scanned + self.stats.folders_scanned
            if not force and count - self._last_emit_count < max(1, self.options.progress_interval):
                return
            self._last_emit_count = count
            files = self.stats.files_scanned
            folders = self.stats.folders_scanned
            total_size = self.stats.total_size
        elapsed = max(perf_counter() - self._started, 0.000001)
        self.progress_callback(
            ScanProgress(
                current_path=Path(path),
                files_scanned=files,
                folders_scanned=folders,
                total_size=total_size,
                elapsed_seconds=elapsed,
                files_per_second=files / elapsed,
                folders_per_second=folders / elapsed,
                bytes_per_second=total_size / elapsed,
                engine_name=self.name,
            )
        )
