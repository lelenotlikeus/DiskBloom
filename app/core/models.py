from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .formatting import format_modified, format_percent, format_size


@dataclass(slots=True)
class DiskItem:
    name: str
    path: Path
    item_type: str
    size: int = 0
    modified: float | None = None
    extension: str = ""
    children: list["DiskItem"] = field(default_factory=list)
    parent: "DiskItem | None" = field(default=None, repr=False, compare=False)
    error: str | None = None

    @property
    def is_folder(self) -> bool:
        return self.item_type == "folder"

    @property
    def formatted_size(self) -> str:
        return format_size(self.size)

    @property
    def percentage_of_parent(self) -> float:
        if not self.parent or self.parent.size <= 0:
            return 100.0 if self.size else 0.0
        return (self.size / self.parent.size) * 100

    @property
    def formatted_percent(self) -> str:
        return format_percent(self.percentage_of_parent)

    @property
    def formatted_modified(self) -> str:
        return format_modified(self.modified)

    @property
    def display_type(self) -> str:
        if self.is_folder:
            return "Folder"
        return self.extension.lower().lstrip(".").upper() or "File"

    @property
    def absolute_path(self) -> str:
        return str(self.path)

    def add_child(self, child: "DiskItem") -> None:
        child.parent = self
        self.children.append(child)

    def sort_children(self) -> None:
        self.children.sort(key=lambda item: (not item.is_folder, -item.size, item.name.lower()))
        for child in self.children:
            child.sort_children()

    def iter_items(self) -> Iterable["DiskItem"]:
        yield self
        for child in self.children:
            yield from child.iter_items()

    def recalculate_size(self) -> int:
        if self.is_folder:
            self.size = sum(child.recalculate_size() for child in self.children)
        return self.size


@dataclass(slots=True)
class ScanStats:
    files_scanned: int = 0
    folders_scanned: int = 0
    total_size: int = 0
    errors: list[str] = field(default_factory=list)
    largest_file: DiskItem | None = None
    permission_errors: int = 0
    skipped_symlinks: int = 0
    engine_name: str = "Standard"
    elapsed_seconds: float = 0.0
    cancelled: bool = False
    source: str = "filesystem"

    @property
    def reclaimable_estimate(self) -> int:
        # Conservative approximation: old/temp-like files are calculated in UI filters.
        return 0

    @property
    def files_per_second(self) -> float:
        return self.files_scanned / self.elapsed_seconds if self.elapsed_seconds > 0 else 0.0

    @property
    def folders_per_second(self) -> float:
        return self.folders_scanned / self.elapsed_seconds if self.elapsed_seconds > 0 else 0.0

    @property
    def bytes_per_second(self) -> float:
        return self.total_size / self.elapsed_seconds if self.elapsed_seconds > 0 else 0.0


@dataclass(slots=True)
class ScanResult:
    root: DiskItem
    stats: ScanStats
