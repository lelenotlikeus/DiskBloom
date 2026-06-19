import os
from pathlib import Path

import pytest

from app.core.deletion import DeletionSafetyError, delete_permanently, move_to_trash, validate_deletion_target
from app.core.models import DiskItem


def _file_item(path: Path) -> DiskItem:
    return DiskItem(path.name, path, "file", size=path.stat().st_size, modified=path.stat().st_mtime, extension=path.suffix)


def _folder_item(path: Path) -> DiskItem:
    item = DiskItem(path.name, path, "folder", size=0, modified=path.stat().st_mtime)
    for child_path in path.iterdir():
        if child_path.is_file():
            child = _file_item(child_path)
            item.add_child(child)
            item.size += child.size
    return item


def test_move_to_trash_uses_send2trash_on_temp_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / "diskbloom_safe_delete_test_file.txt"
    target.write_text("temporary deletion test", encoding="utf-8")
    item = _file_item(target)

    def fake_send2trash(path: str) -> None:
        Path(path).unlink()

    monkeypatch.setattr("app.core.deletion.send2trash", fake_send2trash)
    result = move_to_trash(item)

    assert not target.exists()
    assert result.reclaimed_size == item.size
    assert result.processed_files == 1


def test_permanent_delete_temp_file_only(tmp_path: Path) -> None:
    target = tmp_path / "diskbloom_safe_delete_test_file.txt"
    target.write_text("temporary permanent deletion test", encoding="utf-8")
    item = _file_item(target)

    result = delete_permanently(item)

    assert not target.exists()
    assert result.reclaimed_size == item.size
    assert result.processed_files == 1


def test_permanent_delete_temp_folder_only(tmp_path: Path) -> None:
    target = tmp_path / "diskbloom_safe_delete_test_folder"
    target.mkdir()
    child = target / "diskbloom_safe_delete_test_file.txt"
    child.write_text("temporary permanent folder deletion test", encoding="utf-8")
    item = _folder_item(target)

    result = delete_permanently(item)

    assert not target.exists()
    assert result.reclaimed_size == item.size
    assert result.processed_files == 1


@pytest.mark.parametrize("path", [Path.home(), Path.home() / "Desktop", Path.home() / "Documents", Path.home() / "Downloads"])
def test_deletion_refuses_user_profile_special_folders(path: Path) -> None:
    if not path.exists():
        pytest.skip(f"{path} does not exist on this system")
    item = DiskItem(path.name, path, "folder")

    with pytest.raises(DeletionSafetyError):
        validate_deletion_target(item, permanent=True)


def test_deletion_refuses_filesystem_root() -> None:
    root = Path(Path.cwd().anchor)
    item = DiskItem(str(root), root, "folder")

    with pytest.raises(DeletionSafetyError):
        validate_deletion_target(item, permanent=True)


@pytest.mark.skipif(os.environ.get("DISKBLOOM_RUN_TRASH_INTEGRATION") != "1", reason="real Trash integration is opt-in")
def test_move_to_trash_real_integration_temp_file_only(tmp_path: Path) -> None:
    target = tmp_path / "diskbloom_safe_delete_test_file.txt"
    target.write_text("temporary real trash integration test", encoding="utf-8")
    item = _file_item(target)

    move_to_trash(item)

    assert not target.exists()
