# DiskBloom

**See what is growing on your disk.**

DiskBloom is a modern open-source desktop app for exploring disk usage, finding large files, and cleaning space safely. It scans real folders, shows an expandable disk-usage tree, highlights large and old files, and moves unwanted items to the system Trash or Recycle Bin by default.

DiskBloom is built with Python and PySide6, but end users are meant to run packaged desktop builds, not start the app from source.

## Features

- Real folder scanning with a responsive desktop UI.
- Expandable disk-usage tree with size, percentage, type, modified date, and full path columns.
- Quick locations, recent scans, drag-and-drop folders, and native folder picker.
- Search and filters for name, extension, age, size, files only, and folders only.
- Inspector panel with item details, copy path, open in file explorer, and safe cleanup actions.
- Visual analysis with treemap, file type breakdown, largest files, and old large files.
- Safe deletion through the operating system Trash or Recycle Bin using `send2trash`.
- Advanced permanent deletion is guarded, hidden behind confirmation, and refuses dangerous system paths.
- First-run guided tutorial.
- Settings for language, theme, scan engine, Everything CLI path, and parallel worker count.
- Dark and light themes.

## Download And Run

The recommended way to use DiskBloom is to download a packaged build from the GitHub Releases page.

### Windows

1. Open the latest release.
2. Download the Windows ZIP artifact.
3. Extract the ZIP.
4. Run `DiskBloom.exe`.

If Windows SmartScreen warns you, choose **More info** and then **Run anyway** only if you downloaded the file from this repository. The app is currently unsigned.

### macOS

1. Open the latest release.
2. Download the macOS artifact if available.
3. Extract it and run DiskBloom.

If macOS blocks the app because it is unsigned, open **System Settings > Privacy & Security** and allow it manually.

### Linux

1. Open the latest release.
2. Download the Linux artifact if available.
3. Extract it.
4. Run the DiskBloom executable from the extracted folder.

Linux desktop environments differ, so you may need to mark the file executable.

```bash
chmod +x DiskBloom
```

## Quick Tutorial

1. Launch DiskBloom.
2. Click **Choose Folder**, use a quick location, or drag a folder into the window.
3. Wait for the scan to finish. The status bar shows the active scan engine and real scan speed.
4. Expand folders in the center tree to find what is using space.
5. Select an item to inspect details on the right.
6. Use **Copy path** or **Open in Explorer/Finder/File Manager** to review files.
7. Use **Move to Trash** for safe cleanup.

DiskBloom never permanently deletes by default.

## Safety Model

DiskBloom is designed to be cautious:

- **Move to Trash** is the default cleanup action.
- Files and folders moved to Trash can usually be restored from the system Trash or Recycle Bin.
- Permanent deletion is hidden inside the Advanced section.
- Permanent deletion requires stronger confirmation.
- Dangerous targets such as drive roots, the user home folder, Desktop, Documents, Downloads, Windows, and Program Files are refused.
- Tests use temporary files only.

Always review the confirmation dialog before cleaning a folder.

## Scan Engines

DiskBloom includes multiple scan engines:

| Engine | Purpose |
| --- | --- |
| Auto | Chooses a practical default for the current operating system. |
| Standard | Safe cross-platform filesystem traversal. |
| Parallel | Directory-level threaded traversal, often faster on Windows systems. |
| Everything | Optional Windows indexed backend using Voidtools Everything `es.exe`. |

Everything support is optional. DiskBloom does not install Everything and does not require it. If you want to test it, install Everything manually and set the path to `es.exe` in Settings.

Performance depends on disk type, operating system, antivirus, cache state, permissions, and folder structure. Use the built-in benchmark command from a source checkout if you want exact numbers for your machine.

## Settings And User Data

DiskBloom stores settings per user:

- Windows: `%APPDATA%\DiskBloom\config.json`
- macOS: `~/Library/Application Support/DiskBloom/config.json`
- Linux: `$XDG_CONFIG_HOME/diskbloom/config.json` or `~/.config/diskbloom/config.json`

Settings include:

- theme
- language
- recent scans
- scan engine
- parallel worker count
- optional Everything CLI path
- onboarding state

## Build From Source

Most users should download a packaged release. Developers can build DiskBloom locally.

### Requirements

- Python 3.11+
- Git

### Windows Build

```powershell
git clone https://github.com/lelenotlikeus/DiskBloom.git
cd DiskBloom
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
.\build_windows.bat
```

The build output is written to:

```text
dist\DiskBloom
```

Run:

```text
dist\DiskBloom\DiskBloom.exe
```

### Linux/macOS Build

```bash
git clone https://github.com/lelenotlikeus/DiskBloom.git
cd DiskBloom
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
chmod +x build_linux.sh
./build_linux.sh
```

The build output is written to `dist/DiskBloom`.

## Development

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Run tests:

```bash
pytest
```

Run a benchmark from source:

```bash
python -m app.core.scanners.benchmark "<folder>" --engines standard parallel everything
```

Run from source during development:

```bash
python main.py
```

This source command is for contributors only. Normal users should use packaged builds.

## Project Structure

```text
app/
  core/          filesystem scanning, models, filters, deletion safety
  core/scanners/ scan engines and benchmark tool
  services/      config, recent paths, privileges
  ui/            PySide6 windows, dialogs, widgets, theme
assets/          icons and logo
docs/            architecture, performance, roadmap
tests/           pytest test suite
```

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) and keep changes focused, readable, and tested.

## Security

Please read [SECURITY.md](SECURITY.md) before reporting vulnerabilities or safety issues.

## License

DiskBloom is released under the [MIT License](LICENSE).
