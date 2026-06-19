# Scan Performance

DiskBloom has multiple scan-engine entry points while keeping the main application Python and PySide6.

Standard recursive traversal cannot reliably match lower-level NTFS metadata tools because it still asks the filesystem for directory entries and metadata folder by folder. DiskBloom's fastest practical Python route is therefore an optional indexed backend.

## Engines

### Standard

The Standard scanner is the default safe backend. It is cross-platform and uses `os.scandir` with `DirEntry` metadata where possible.

Important optimizations:

- no filesystem traversal through Qt objects
- no file opening
- no icon or file-type work in the scan loop
- no symlink following by default
- no repeated absolute path resolving inside child loops
- progress emitted in batches
- child sorting only after scan completion
- direct counters for errors, skipped symlinks, files, folders, and rates

### Windows Fast / Experimental

Some disk utilities can be faster on NTFS because they may read metadata from the Master File Table or USN Journal instead of walking every directory normally.

DiskBloom detects Windows, the target volume, filesystem type, and administrator availability. It does **not** currently implement a safe read-only MFT/USN parser. Windows Fast is hidden from normal settings until a real implementation exists.

This is intentional: a fake "fast" backend would be misleading. Future work can add a real MFT/USN backend behind this interface.

### Parallel

The Parallel scanner uses worker threads over directories. It is a real filesystem traversal backend, not a UI trick. It can help on some SSD/cache-heavy workloads, but it is not always faster. On this machine it was slower than Standard on both `C:\Users\ggisk` and `C:\Windows`, likely because Python object creation, lock coordination, antivirus, and storage behavior outweighed the parallelism benefit.

### Everything

The Everything scanner is an optional Windows indexed backend. It uses Voidtools Everything CLI (`es.exe`) when available:

1. DiskBloom runs `es.exe` with a path-scoped query.
2. Everything exports CSV with full path, size, modified date, and attributes.
3. DiskBloom rebuilds its normal tree model from the flat indexed results.
4. Folder sizes are aggregated from file records.

This is read-only. DiskBloom does not install Everything, does not require it as a dependency, and still works without it.

Privacy/security note: Everything uses a local service/index. DiskBloom only queries the local CLI you configure or install; it does not send file paths over the network.

Install Everything manually from Voidtools, then either place `es.exe` on `PATH` or configure its path in DiskBloom Settings. Common paths checked automatically:

- `C:\Program Files\Everything\es.exe`
- `C:\Program Files\Everything 1.5a\es.exe`
- `C:\Program Files (x86)\Everything\es.exe`

## Benchmark Command

```powershell
python -m app.core.scanners.benchmark "C:\path\to\scan"
python -m app.core.scanners.benchmark "%USERPROFILE%" --engines standard parallel everything
python -m app.core.scanners.benchmark "C:" --engines standard parallel everything --warmups 1 --runs 3
python -m app.core.scanners.benchmark "C:\path\to\scan" --engines standard parallel everything --json
python -m app.core.scanners.benchmark "C:\path\to\scan" --engine standard
```

Output includes:

- scan engine used
- total scan time
- files and folders scanned
- total bytes found
- files/sec
- folders/sec
- MB/sec discovered
- GB/sec discovered
- permission errors
- skipped symlinks
- memory high-water mark when the platform exposes it
- whether data came from live filesystem traversal or the Everything index

## Sample Output

```text
Engine: Standard
Available: yes
Source: filesystem
Runs: 1
Total scan time: 8.294s best / 8.294s avg
Files scanned: 204706
Folders scanned: 27861
Total bytes found: 51682862205 (48.1 GB)
Files/sec: 24681.2
Folders/sec: 3359.2
GB/sec discovered: 5.803
Permission errors: 20
Skipped symlinks: 23
```

## Local Before/After Sample

| Path | Engine | Files | Folders | Time | Files/sec |
| --- | --- | ---: | ---: | ---: | ---: |
| `%USERPROFILE%` | Standard | 204,755 | 27,867 | 17.394s | 11,771 |
| `%USERPROFILE%` | Parallel | 204,706 | 27,861 | 8.294s | 24,681 |
| `C:\Windows` | Standard | 813,393 | 258,564 | 63.848s | 12,740 |
| `C:\Windows` | Parallel | 813,393 | 258,532 | 66.432s | 12,244 |

These measurements were taken on the local project folder and are strongly affected by OS cache, disk type, antivirus, and current load.

## Parallel Scanning

Directory-level parallel scanning is available. Auto uses Parallel on Windows and Standard elsewhere. Everything is intentionally opt-in because its CSV export and tree rebuild cost can be slower than filesystem traversal on some systems.

## Remaining Limitations

- No real MFT/USN scanner yet.
- Windows Fast is hidden/unavailable until implemented.
- Everything requires Everything/ES installed and indexed locally.
- Parallel is not consistently faster than Standard.
- Network drives and protected system folders depend on OS permissions.
- Benchmark results are not comparable across machines unless the same path and cache conditions are used.
