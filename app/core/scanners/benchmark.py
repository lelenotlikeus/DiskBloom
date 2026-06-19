from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tracemalloc
from pathlib import Path
from time import perf_counter

try:
    import resource
except ImportError:  # pragma: no cover - Windows
    resource = None

from ..formatting import format_size
from ..models import DiskItem, ScanResult, ScanStats
from .base import ScanOptions, ScannerUnavailable
from .everything_scanner import EverythingScanner, is_available as everything_available
from .parallel_scanner import ParallelScanner
from .standard_scanner import StandardScanner


class LegacyRecursiveScanner:
    name = "Legacy recursive baseline"

    def __init__(self) -> None:
        self.stats = ScanStats(engine_name=self.name, source="filesystem")

    def scan(self, path: str | Path) -> ScanResult:
        root = Path(path).expanduser().resolve()
        started = perf_counter()
        item = self._scan_dir(root, None)
        item.sort_children()
        self.stats.elapsed_seconds = max(perf_counter() - started, 0.000001)
        return ScanResult(item, self.stats)

    def _scan_dir(self, path: Path, parent: DiskItem | None) -> DiskItem:
        item = DiskItem(path.name or str(path), path, "folder", parent=parent)
        self.stats.folders_scanned += 1
        try:
            stat = path.stat()
            item.modified = stat.st_mtime
            with os.scandir(path) as entries:
                for entry in entries:
                    child_path = Path(entry.path)
                    if entry.is_symlink():
                        self.stats.skipped_symlinks += 1
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        child = self._scan_dir(child_path, item)
                    elif entry.is_file(follow_symlinks=False):
                        child = self._scan_file(child_path, entry, item)
                    else:
                        continue
                    item.add_child(child)
                    item.size += child.size
        except OSError as exc:
            self.stats.permission_errors += 1
            if len(self.stats.errors) < 500:
                self.stats.errors.append(f"{path}: {exc}")
            item.error = str(exc)
        return item

    def _scan_file(self, path: Path, entry: os.DirEntry[str], parent: DiskItem) -> DiskItem:
        stat = entry.stat(follow_symlinks=False)
        item = DiskItem(entry.name, path, "file", stat.st_size, stat.st_mtime, path.suffix.lower(), parent=parent)
        self.stats.files_scanned += 1
        self.stats.total_size += item.size
        if self.stats.largest_file is None or item.size > self.stats.largest_file.size:
            self.stats.largest_file = item
        return item


def _memory_mb() -> float | None:
    if resource is None:
        return None
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform == "darwin":
            return usage / (1024 * 1024)
        return usage / 1024
    except Exception:
        return None


def _scanner_for(engine: str, options: ScanOptions):
    if engine == "standard":
        return StandardScanner(options=options)
    if engine == "parallel":
        return ParallelScanner(options=options)
    if engine == "everything":
        ok, reason, _ = everything_available(options.everything_cli_path)
        if not ok:
            raise ScannerUnavailable(reason)
        return EverythingScanner(options=options)
    if engine == "legacy":
        return LegacyRecursiveScanner()
    raise ScannerUnavailable(f"Unknown engine: {engine}")


def _run_once(path: Path, engine: str, options: ScanOptions, trace_memory: bool = False) -> dict[str, object]:
    scanner = _scanner_for(engine, options)
    if trace_memory:
        tracemalloc.start()
    result = scanner.scan(path)
    peak = None
    if trace_memory:
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    stats = result.stats
    memory = _memory_mb()
    return {
        "engine": stats.engine_name,
        "requested_engine": engine,
        "available": True,
        "source": stats.source,
        "time": stats.elapsed_seconds,
        "files": stats.files_scanned,
        "folders": stats.folders_scanned,
        "total_size": stats.total_size,
        "files_per_sec": stats.files_per_second,
        "folders_per_sec": stats.folders_per_second,
        "gb_per_sec": stats.bytes_per_second / (1024**3),
        "permission_errors": stats.permission_errors,
        "skipped_symlinks": stats.skipped_symlinks,
        "peak_python_mb": None if peak is None else peak / (1024 * 1024),
        "process_memory_mb": memory,
    }


def _summarize(runs: list[dict[str, object]]) -> dict[str, object]:
    if not runs:
        return {}
    times = [float(run["time"]) for run in runs]
    best = min(runs, key=lambda run: float(run["time"]))
    summary = dict(best)
    summary["runs"] = len(runs)
    summary["time_avg"] = statistics.mean(times)
    summary["time_min"] = min(times)
    summary["time_max"] = max(times)
    return summary


def print_result(result: dict[str, object]) -> None:
    if not result.get("available", True):
        print(f"Engine: {result['engine']}")
        print("Available: no")
        print(f"Reason: {result['reason']}")
        return
    print(f"Engine: {result['engine']}")
    print("Available: yes")
    print(f"Source: {result['source']}")
    print(f"Runs: {result.get('runs', 1)}")
    print(f"Total scan time: {float(result['time_min']):.3f}s best / {float(result['time_avg']):.3f}s avg")
    print(f"Files scanned: {result['files']}")
    print(f"Folders scanned: {result['folders']}")
    print(f"Total bytes found: {result['total_size']} ({format_size(int(result['total_size']))})")
    print(f"Files/sec: {float(result['files_per_sec']):.1f}")
    print(f"Folders/sec: {float(result['folders_per_sec']):.1f}")
    print(f"GB/sec discovered: {float(result['gb_per_sec']):.3f}")
    print(f"Permission errors: {result['permission_errors']}")
    print(f"Skipped symlinks: {result['skipped_symlinks']}")
    if result.get("peak_python_mb") is not None:
        print(f"Peak Python memory: {float(result['peak_python_mb']):.1f} MB")
    if result.get("process_memory_mb") is not None:
        print(f"Process memory high-water mark: {float(result['process_memory_mb']):.1f} MB")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark DiskBloom scan engines.")
    parser.add_argument("path", type=Path, help="Folder to scan.")
    parser.add_argument("--engines", nargs="+", choices=["standard", "parallel", "everything", "legacy"], default=["standard"])
    parser.add_argument("--engine", choices=["standard", "parallel", "everything", "legacy"], help="Single-engine shorthand.")
    parser.add_argument("--warmups", type=int, default=0)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--json", action="store_true", help="Print JSON instead of human-readable output.")
    parser.add_argument("--everything-cli", default="", help="Optional path to es.exe.")
    parser.add_argument("--workers", type=int, default=0, help="Parallel worker count. 0 means auto.")
    parser.add_argument("--compare-legacy", action="store_true", help="Include legacy baseline.")
    parser.add_argument("--trace-memory", action="store_true", help="Measure Python allocation peak with tracemalloc. This can slow large scans.")
    args = parser.parse_args(argv)

    path = args.path.expanduser().resolve()
    engines = [args.engine] if args.engine else list(args.engines)
    if args.compare_legacy and "legacy" not in engines:
        engines.insert(0, "legacy")

    results: list[dict[str, object]] = []
    for engine in engines:
        options = ScanOptions(
            engine=engine,
            progress_interval=1_000_000,
            everything_cli_path=args.everything_cli,
            workers=args.workers,
        )
        try:
            for _ in range(max(0, args.warmups)):
                _run_once(path, engine, options, args.trace_memory)
            runs = [_run_once(path, engine, options, args.trace_memory) for _ in range(max(1, args.runs))]
            results.append(_summarize(runs))
        except ScannerUnavailable as exc:
            results.append({"engine": engine, "requested_engine": engine, "available": False, "reason": str(exc)})

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for index, result in enumerate(results):
            if index:
                print("")
            print_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
