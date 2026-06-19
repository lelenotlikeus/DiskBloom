# Architecture

DiskBloom is organized around a small core layer and a PySide6 UI layer.

## Core

- `app/core/models.py` defines `DiskItem`, `ScanStats`, and `ScanResult`.
- `app/core/scanner.py` is a compatibility facade that selects a scanner backend.
- `app/core/scanners/base.py` defines scanner options, progress snapshots, and shared callback types.
- `app/core/scanners/standard_scanner.py` is the optimized cross-platform `os.scandir` scanner. It avoids repeated path resolution in hot loops, skips symlinks, batches progress, tracks rates/errors, and sorts after scanning.
- `app/core/scanners/parallel_scanner.py` scans directories with worker threads and aggregates the tree after traversal.
- `app/core/scanners/everything_scanner.py` optionally uses Voidtools Everything `es.exe` to export indexed path/size/date/attribute data, then rebuilds the normal DiskBloom tree.
- `app/core/scanners/windows_fast_scanner.py` performs Windows/NTFS/admin capability detection. It intentionally refuses to claim MFT/USN support until a safe read-only implementation exists, so Auto falls back to Standard today.
- `app/core/scanners/benchmark.py` provides `python -m app.core.scanners.benchmark <path>` for real scan timing.
- `app/core/filters.py` contains reusable filtering rules and size parsing.
- `app/core/file_types.py` classifies files into analysis categories.
- `app/core/deletion.py` wraps `send2trash` for safe deletion, contains guarded permanent deletion, and refuses dangerous filesystem targets.

## UI

- `app/ui/main_window.py` owns the application shell, scan worker thread, filter controls, inspector, and deletion workflow.
- `app/ui/theme.py` centralizes color, spacing, radius, typography, font fallback, and generated QSS for dark/light theme parity.
- `app/ui/widgets/item_model.py` exposes `DiskItem` trees through `QAbstractItemModel`.
- `app/ui/widgets/size_delegate.py` paints size bars in the size column.
- `app/ui/widgets/treemap.py` draws a real proportional treemap from scanned children.
- `app/ui/widgets/reclaim_meter.py` shows deletion progress feedback.

## Persistence

Recent paths, theme preference, onboarding state, language, and scan engine preference are saved as JSON in the per-user application config directory:

- Windows: `%APPDATA%\DiskBloom\config.json`
- macOS: `~/Library/Application Support/DiskBloom/config.json`
- Linux: `$XDG_CONFIG_HOME/diskbloom/config.json` or `~/.config/diskbloom/config.json`

Older `~/.diskbloom/config.json` files are migrated automatically when possible.
