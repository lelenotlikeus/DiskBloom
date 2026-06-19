from __future__ import annotations

from dataclasses import dataclass
from time import time

from .models import DiskItem


@dataclass(slots=True)
class FilterCriteria:
    search: str = ""
    extension: str = ""
    min_size: int = 0
    only_folders: bool = False
    only_files: bool = False
    older_than_days: int = 0


def item_matches(item: DiskItem, criteria: FilterCriteria) -> bool:
    if criteria.search and criteria.search.lower() not in item.name.lower():
        return False
    if criteria.extension:
        wanted = criteria.extension.lower()
        if not wanted.startswith("."):
            wanted = f".{wanted}"
        if item.extension.lower() != wanted:
            return False
    if criteria.min_size and item.size < criteria.min_size:
        return False
    if criteria.only_folders and not item.is_folder:
        return False
    if criteria.only_files and item.is_folder:
        return False
    if criteria.older_than_days and item.modified:
        cutoff = time() - (criteria.older_than_days * 24 * 60 * 60)
        if item.modified > cutoff:
            return False
    return True


def filter_items(root: DiskItem, criteria: FilterCriteria) -> list[DiskItem]:
    return [item for item in root.iter_items() if item is not root and item_matches(item, criteria)]


def parse_size(text: str) -> int:
    cleaned = text.strip().lower()
    if not cleaned:
        return 0
    units = {"b": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3, "tb": 1024**4}
    parts = cleaned.replace(" ", "")
    number = ""
    suffix = ""
    for char in parts:
        if char.isdigit() or char == ".":
            number += char
        else:
            suffix += char
    if not number:
        return 0
    suffix = suffix or "b"
    return int(float(number) * units.get(suffix, 1))
