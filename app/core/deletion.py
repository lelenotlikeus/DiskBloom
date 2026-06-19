from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from send2trash import send2trash

from .models import DiskItem


@dataclass(slots=True)
class DeletionResult:
    reclaimed_size: int
    processed_files: int
    elapsed_seconds: float

    @property
    def bytes_per_second(self) -> float:
        if self.elapsed_seconds <= 0:
            return float(self.reclaimed_size)
        return self.reclaimed_size / self.elapsed_seconds


class DeletionSafetyError(ValueError):
    """Raised when a deletion target is too broad or system-sensitive."""


def _normalized(path: Path) -> Path:
    return path.expanduser().resolve()


def _known_dangerous_paths() -> set[Path]:
    home = Path.home().resolve()
    paths = {
        home,
        home / "Desktop",
        home / "Documents",
        home / "Downloads",
    }
    if os.name == "nt":
        system_drive = Path(os.environ.get("SystemDrive", "C:") + "\\")
        windir = Path(os.environ.get("WINDIR", "C:\\Windows"))
        paths.update(
            {
                system_drive,
                windir,
                Path(os.environ.get("ProgramFiles", "C:\\Program Files")),
                Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")),
            }
        )
    else:
        paths.add(Path("/"))
    return {_normalized(path) for path in paths}


def _dangerous_descendant_roots() -> set[Path]:
    if os.name != "nt":
        return {Path("/").resolve()}
    return {
        _normalized(Path(os.environ.get("WINDIR", "C:\\Windows"))),
        _normalized(Path(os.environ.get("ProgramFiles", "C:\\Program Files"))),
        _normalized(Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"))),
    }


def validate_deletion_target(item: DiskItem, permanent: bool = False) -> Path:
    path = _normalized(item.path)
    if not path.exists():
        raise DeletionSafetyError(f"Deletion target does not exist: {path}")
    if path.anchor and path == Path(path.anchor):
        raise DeletionSafetyError(f"Refusing to delete a drive or filesystem root: {path}")
    if len(str(path)) < 8:
        raise DeletionSafetyError(f"Refusing to delete suspiciously short path: {path}")
    dangerous = _known_dangerous_paths()
    if path in dangerous:
        raise DeletionSafetyError(f"Refusing to delete protected location: {path}")
    if permanent and any(root in path.parents for root in _dangerous_descendant_roots()):
        # Permanent deletion inside sensitive top-level folders is too easy to misuse.
        raise DeletionSafetyError(f"Refusing permanent deletion inside protected location: {path}")
    return path


def count_files(item: DiskItem) -> int:
    if not item.is_folder:
        return 1
    return sum(count_files(child) for child in item.children)


def move_to_trash(item: DiskItem) -> DeletionResult:
    started = perf_counter()
    path = validate_deletion_target(item, permanent=False)
    send2trash(str(path))
    return DeletionResult(
        reclaimed_size=item.size,
        processed_files=count_files(item),
        elapsed_seconds=max(perf_counter() - started, 0.001),
    )


def delete_permanently(item: DiskItem) -> DeletionResult:
    started = perf_counter()
    path = validate_deletion_target(item, permanent=True)
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return DeletionResult(
        reclaimed_size=item.size,
        processed_files=count_files(item),
        elapsed_seconds=max(perf_counter() - started, 0.001),
    )
