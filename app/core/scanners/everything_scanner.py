from __future__ import annotations

import csv
import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from ..models import DiskItem, ScanResult, ScanStats
from .base import CancelCallback, ProgressCallback, ScanOptions, ScanProgress, ScannerUnavailable


COMMON_ES_PATHS = (
    r"C:\Program Files\Everything\es.exe",
    r"C:\Program Files\Everything 1.5a\es.exe",
    r"C:\Program Files (x86)\Everything\es.exe",
)


@dataclass(slots=True)
class EverythingRecord:
    path: str
    size: int
    modified: float | None
    is_folder: bool


def find_es_executable(configured_path: str = "") -> Path | None:
    candidates: list[str] = []
    if configured_path:
        path = Path(configured_path).expanduser()
        return path if path.exists() and path.is_file() else None
    found = shutil.which("es.exe") or shutil.which("es")
    if found:
        candidates.append(found)
    candidates.extend(COMMON_ES_PATHS)
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.exists() and path.is_file():
            return path
    return None


def is_available(configured_path: str = "") -> tuple[bool, str, Path | None]:
    if platform.system() != "Windows":
        return False, "Everything Scanner is Windows-only.", None
    exe = find_es_executable(configured_path)
    if not exe:
        return False, "Everything CLI es.exe was not found. Install Everything/ES or configure its path.", None
    return True, f"Using {exe}", exe


def _filetime_to_unix(value: str) -> float | None:
    text = value.strip()
    if not text:
        return None
    try:
        number = int(text)
    except ValueError:
        return None
    if number <= 0:
        return None
    return (number / 10_000_000) - 11644473600


def _parse_size(value: str) -> int:
    text = value.strip().replace(",", "")
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def parse_everything_csv(csv_text: str) -> list[EverythingRecord]:
    rows = csv.DictReader(csv_text.splitlines())
    records: list[EverythingRecord] = []
    for row in rows:
        normalized = {str(key).strip().lower(): (value or "") for key, value in row.items() if key is not None}
        path = (
            normalized.get("filename")
            or normalized.get("full path and name")
            or normalized.get("path")
            or normalized.get("name")
            or ""
        ).strip()
        if not path:
            continue
        attributes = normalized.get("attributes", "")
        is_folder = "D" in attributes.upper()
        records.append(
            EverythingRecord(
                path=path,
                size=0 if is_folder else _parse_size(normalized.get("size", "")),
                modified=_filetime_to_unix(normalized.get("date modified", "") or normalized.get("dm", "")),
                is_folder=is_folder,
            )
        )
    return records


def build_tree_from_records(root_path: str | Path, records: list[EverythingRecord], engine_name: str = "Everything") -> ScanResult:
    root = Path(root_path).expanduser().resolve()
    root_item = DiskItem(root.name or str(root), root, "folder")
    root_str = str(root)
    root_key = os.path.normcase(root_str)
    root_prefix = root_key if root_key.endswith(os.sep) else root_key + os.sep
    by_path: dict[str, DiskItem] = {root_key: root_item}
    stats = ScanStats(engine_name=engine_name, source="everything-index")
    stats.folders_scanned = 1

    def ensure_folder(folder_text: str) -> DiskItem:
        key = os.path.normcase(folder_text)
        existing = by_path.get(key)
        if existing:
            return existing
        parent_text = os.path.dirname(folder_text.rstrip("\\/"))
        parent = ensure_folder(parent_text) if parent_text and key != root_key else root_item
        folder_path = Path(folder_text)
        item = DiskItem(os.path.basename(folder_text.rstrip("\\/")) or folder_text, folder_path, "folder", parent=parent)
        parent.children.append(item)
        by_path[key] = item
        stats.folders_scanned += 1
        return item

    for record in records:
        path_text = record.path
        path_key = os.path.normcase(path_text)
        if path_key != root_key and not path_key.startswith(root_prefix):
            continue
        if path_key == root_key:
            root_item.modified = record.modified
            continue
        if record.is_folder:
            folder = ensure_folder(path_text)
            folder.modified = record.modified
            continue
        parent = ensure_folder(os.path.dirname(path_text))
        record_path = Path(path_text)
        item = DiskItem(
            os.path.basename(path_text),
            record_path,
            "file",
            size=record.size,
            modified=record.modified,
            extension=record_path.suffix.lower(),
            parent=parent,
        )
        parent.children.append(item)
        stats.files_scanned += 1
        stats.total_size += record.size
        if stats.largest_file is None or record.size > stats.largest_file.size:
            stats.largest_file = item

    root_item.recalculate_size()
    root_item.sort_children()
    return ScanResult(root_item, stats)


class EverythingScanner:
    """Read-only scanner backed by the local Voidtools Everything index."""

    name = "Everything"

    def __init__(
        self,
        progress_callback: ProgressCallback | None = None,
        cancel_callback: CancelCallback | None = None,
        options: ScanOptions | None = None,
    ) -> None:
        self.progress_callback = progress_callback
        self.cancel_callback = cancel_callback or (lambda: False)
        self.options = options or ScanOptions(engine="everything")

    def scan(self, path: str | Path) -> ScanResult:
        root = Path(path).expanduser().resolve()
        available, reason, exe = is_available(self.options.everything_cli_path)
        if not available or exe is None:
            raise ScannerUnavailable(reason)
        started = perf_counter()
        self._emit(root, 0, 0, 0, started)
        records = self._query(exe, root)
        if self.cancel_callback():
            result = build_tree_from_records(root, [], self.name)
            result.stats.cancelled = True
        else:
            result = build_tree_from_records(root, records, self.name)
        result.stats.elapsed_seconds = max(perf_counter() - started, 0.000001)
        result.stats.source = "everything-index"
        self._emit(root, result.stats.files_scanned, result.stats.folders_scanned, result.stats.total_size, started)
        return result

    def _query(self, exe: Path, root: Path) -> list[EverythingRecord]:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            output_path = Path(tmp.name)
        try:
            root_text = str(root)
            if not root_text.endswith("\\"):
                root_text += "\\"
            command = [
                str(exe),
                f"path:{root_text}",
                "-export-csv",
                str(output_path),
                "-full-path-and-name",
                "-size",
                "-date-modified",
                "-attributes",
                "-size-format",
                "1",
                "-date-format",
                "2",
                "-timeout",
                "15000",
            ]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace")
            if completed.returncode != 0:
                message = (completed.stderr or completed.stdout or f"es.exe exited with code {completed.returncode}").strip()
                raise ScannerUnavailable(message)
            csv_text = output_path.read_text(encoding="utf-8-sig", errors="replace") if output_path.exists() else ""
            return parse_everything_csv(csv_text)
        finally:
            try:
                output_path.unlink(missing_ok=True)
            except OSError:
                pass

    def _emit(self, path: Path, files: int, folders: int, total_size: int, started: float) -> None:
        if not self.progress_callback:
            return
        elapsed = max(perf_counter() - started, 0.000001)
        self.progress_callback(
            ScanProgress(
                current_path=path,
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
