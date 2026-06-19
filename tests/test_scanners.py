from __future__ import annotations

from pathlib import Path

import pytest

from app.core.scanners.base import ScanOptions
from app.core.scanners.capabilities import choose_scanner
from app.core.scanners.everything_scanner import EverythingRecord, build_tree_from_records, parse_everything_csv
from app.core.scanners.parallel_scanner import ParallelScanner
from app.core.scanners.standard_scanner import StandardScanner
from app.core.scanners.windows_fast_scanner import detect_capability
from app.core.scanners.benchmark import main as benchmark_main
import app.core.scanners.capabilities as capabilities


def test_standard_scanner_size_aggregation(tmp_path: Path) -> None:
    folder = tmp_path / "scan"
    nested = folder / "nested"
    nested.mkdir(parents=True)
    (folder / "a.bin").write_bytes(b"a" * 10)
    (nested / "b.bin").write_bytes(b"b" * 25)

    result = StandardScanner(options=ScanOptions(progress_interval=1)).scan(folder)

    assert result.root.size == 35
    assert result.stats.files_scanned == 2
    assert result.stats.folders_scanned == 2
    assert result.stats.largest_file is not None
    assert result.stats.largest_file.name == "b.bin"
    assert result.stats.engine_name == "Standard"


def test_standard_scanner_skips_symlinks(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "real.txt").write_text("real", encoding="utf-8")
    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation is unavailable in this environment.")

    result = StandardScanner().scan(tmp_path)

    assert result.stats.files_scanned == 1
    assert result.stats.skipped_symlinks >= 1


def test_standard_scanner_cancellation(tmp_path: Path) -> None:
    folder = tmp_path / "scan"
    folder.mkdir()
    for index in range(20):
        (folder / f"{index}.txt").write_text("x", encoding="utf-8")

    calls = 0

    def cancel() -> bool:
        nonlocal calls
        calls += 1
        return calls > 3

    result = StandardScanner(cancel_callback=cancel).scan(folder)

    assert result.stats.cancelled is True
    assert result.stats.files_scanned < 20


def test_engine_selection_falls_back_to_standard_for_unavailable_fast(tmp_path: Path) -> None:
    scanner = choose_scanner(tmp_path, ScanOptions(engine="windows_fast"))
    assert scanner.name == "Standard"


def test_everything_unavailable_falls_back_to_standard(tmp_path: Path) -> None:
    scanner = choose_scanner(tmp_path, ScanOptions(engine="everything", everything_cli_path=str(tmp_path / "missing-es.exe")))
    assert scanner.name == "Standard"


def test_auto_prefers_everything_when_available(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(capabilities, "everything_available", lambda configured_path="": (True, "ok", tmp_path / "es.exe"))
    scanner = capabilities.choose_scanner(tmp_path, ScanOptions(engine="auto", prefer_indexed=True))
    assert scanner.name == "Everything"


def test_windows_fast_capability_detection_is_safe(tmp_path: Path) -> None:
    capability = detect_capability(tmp_path)
    assert capability.available is False
    assert capability.reason


def test_parse_everything_csv_output() -> None:
    csv_text = (
        "Filename,Size,Date Modified,Attributes\n"
        "C:\\\\Data\\\\file.txt,42,132537600000000000,A\n"
        "C:\\\\Data\\\\Folder,,132537600000000000,D\n"
    )
    records = parse_everything_csv(csv_text)
    assert len(records) == 2
    assert records[0].path.endswith("file.txt")
    assert records[0].size == 42
    assert records[0].is_folder is False
    assert records[1].is_folder is True


def test_build_tree_from_everything_records(tmp_path: Path) -> None:
    root = tmp_path / "root"
    records = [
        EverythingRecord(str(root / "a.bin"), 10, 1000.0, False),
        EverythingRecord(str(root / "nested"), 0, 1001.0, True),
        EverythingRecord(str(root / "nested" / "b.bin"), 25, 1002.0, False),
    ]
    result = build_tree_from_records(root, records)
    assert result.root.size == 35
    assert result.stats.files_scanned == 2
    assert result.stats.folders_scanned == 2
    assert result.stats.largest_file is not None
    assert result.stats.largest_file.name == "b.bin"


def test_parallel_scanner_matches_standard_totals(tmp_path: Path) -> None:
    folder = tmp_path / "scan"
    (folder / "a" / "b").mkdir(parents=True)
    (folder / "one.txt").write_bytes(b"1" * 7)
    (folder / "a" / "two.txt").write_bytes(b"2" * 11)
    (folder / "a" / "b" / "three.txt").write_bytes(b"3" * 13)

    standard = StandardScanner().scan(folder)
    parallel = ParallelScanner(options=ScanOptions(workers=2)).scan(folder)

    assert parallel.root.size == standard.root.size == 31
    assert parallel.stats.files_scanned == standard.stats.files_scanned == 3
    assert parallel.stats.folders_scanned == standard.stats.folders_scanned == 3


def test_benchmark_command_does_not_crash(tmp_path: Path) -> None:
    folder = tmp_path / "bench"
    folder.mkdir()
    (folder / "file.txt").write_text("hello", encoding="utf-8")
    assert benchmark_main([str(folder), "--engines", "standard", "parallel", "--runs", "1"]) == 0
