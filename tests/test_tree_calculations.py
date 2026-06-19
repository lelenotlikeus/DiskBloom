from pathlib import Path

from app.core.models import DiskItem


def test_recalculate_folder_size_and_percent() -> None:
    root = DiskItem("root", Path("root"), "folder")
    a = DiskItem("a.bin", Path("root/a.bin"), "file", size=100)
    b = DiskItem("b.bin", Path("root/b.bin"), "file", size=300)
    root.add_child(a)
    root.add_child(b)
    assert root.recalculate_size() == 400
    assert a.percentage_of_parent == 25
    assert b.percentage_of_parent == 75
