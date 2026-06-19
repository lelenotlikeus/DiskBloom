from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from app.core.scanner import DiskScanner
from app.ui.main_window import MainWindow
from app.ui.theme import ThemeManager

ThemeManager.prepare_font_environment()


OFFSCREEN_NOTE = (
    "Note: QT_QPA_PLATFORM=offscreen can use a reduced font backend and may not match normal "
    "Windows rendering. For release screenshots on Windows, run this script from a normal desktop "
    "session without forcing offscreen mode."
)


def render(theme: str, scan_path: Path, output: Path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    chosen_font = ThemeManager.configure_application_font(app)
    result = DiskScanner().scan(scan_path)
    window = MainWindow()
    window.theme = theme
    window._apply_theme()
    window.resize(1440, 860)
    window.current_path = scan_path
    window._set_path_label(str(scan_path))
    window.on_scan_finished(result)
    window.select_item(result.root)
    window.show()
    app.processEvents()
    pixmap = QPixmap(window.size())
    window.render(pixmap)
    output.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(output))
    window.close()
    print(f"Rendered {output} using font: {chosen_font}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render DiskBloom screenshots from a real local scan.")
    parser.add_argument("--scan-path", type=Path, default=Path("tests"), help="Folder to scan for screenshot data.")
    parser.add_argument("--output-dir", type=Path, default=Path("screenshots"), help="Output screenshot directory.")
    args = parser.parse_args()

    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        print(OFFSCREEN_NOTE)

    scan_path = args.scan_path.resolve()
    for theme in ("dark", "light"):
        render(theme, scan_path, args.output_dir / f"diskbloom-{theme}.png")


if __name__ == "__main__":
    main()
