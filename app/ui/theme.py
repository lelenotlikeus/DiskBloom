from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication


ASSET_DIR = Path(__file__).resolve().parents[2] / "assets"
ICON_DIR = ASSET_DIR / "icons"


@dataclass(frozen=True)
class ThemeTokens:
    name: str
    bg: str
    surface: str
    surface_2: str
    elevated: str
    input_bg: str
    text: str
    muted: str
    subtle: str
    border: str
    border_strong: str
    accent: str
    accent_2: str
    accent_soft: str
    danger: str
    danger_soft: str
    selected: str
    selected_text: str
    shadow: str
    scrollbar: str
    scrollbar_hover: str


DARK = ThemeTokens(
    name="dark",
    bg="#070d13",
    surface="#0d1620",
    surface_2="#0a121a",
    elevated="#111d28",
    input_bg="#0a121a",
    text="#f2f7fb",
    muted="#91a4b7",
    subtle="#66798a",
    border="#1b2a38",
    border_strong="#2c4354",
    accent="#55f0c2",
    accent_2="#5aa9ff",
    accent_soft="#12332f",
    danger="#c98797",
    danger_soft="#231019",
    selected="#173346",
    selected_text="#f4fbff",
    shadow="rgba(0, 0, 0, 0.32)",
    scrollbar="#263848",
    scrollbar_hover="#3a5063",
)

LIGHT = ThemeTokens(
    name="light",
    bg="#f3f6fa",
    surface="#ffffff",
    surface_2="#f8fafc",
    elevated="#ffffff",
    input_bg="#ffffff",
    text="#14212d",
    muted="#5d6e7e",
    subtle="#81909f",
    border="#d6e0ea",
    border_strong="#bfccd8",
    accent="#168f7d",
    accent_2="#2f82d6",
    accent_soft="#e7f6f2",
    danger="#9d3148",
    danger_soft="#fff0f3",
    selected="#dcefe9",
    selected_text="#10241f",
    shadow="rgba(18, 33, 45, 0.10)",
    scrollbar="#c3cfdb",
    scrollbar_hover="#9fb0bf",
)


SPACING = {
    "page": 14,
    "panel": 12,
    "card": 12,
    "tight": 6,
    "gap": 10,
}

RADIUS = {
    "sm": 6,
    "md": 8,
    "lg": 10,
    "pill": 16,
}

FONT_FAMILIES = (
    "Segoe UI",
    "Inter",
    "SF Pro Text",
    "Helvetica Neue",
    "Arial",
    "Noto Sans",
    "DejaVu Sans",
    "Liberation Sans",
    "Sans Serif",
)

SYSTEM_FONT_FILES = (
    Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Fonts" / "segoeui.ttf",
    Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Fonts" / "segoeuib.ttf",
    Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Fonts" / "arial.ttf",
    Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Fonts" / "tahoma.ttf",
    Path("/System/Library/Fonts/SFNS.ttf"),
    Path("/System/Library/Fonts/Helvetica.ttc"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSans-Regular.ttf"),
)

TYPE = {
    "font": ", ".join(f'"{family}"' if " " in family else family for family in FONT_FAMILIES),
    "body": "10pt",
    "small": "8.5pt",
    "title": "16pt",
    "metric": "12.5pt",
}


class ThemeManager:
    _current: ThemeTokens = DARK
    _font_family: str = FONT_FAMILIES[0]
    _font_files_loaded = False

    @classmethod
    def set_theme(cls, name: str) -> None:
        cls._current = LIGHT if name == "light" else DARK

    @classmethod
    def tokens(cls) -> ThemeTokens:
        return cls._current

    @classmethod
    def prepare_font_environment(cls) -> None:
        """Help Qt's offscreen backend find real system fonts before QApplication starts."""
        if sys.platform.startswith("win"):
            windows_fonts = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Fonts"
            if windows_fonts.exists():
                os.environ.setdefault("QT_QPA_FONTDIR", str(windows_fonts))

    @classmethod
    def _load_system_font_files(cls) -> list[str]:
        if cls._font_files_loaded:
            return []
        cls._font_files_loaded = True
        loaded: list[str] = []
        for font_path in SYSTEM_FONT_FILES:
            if not font_path.exists():
                continue
            font_id = QFontDatabase.addApplicationFont(str(font_path))
            if font_id < 0:
                continue
            loaded.extend(QFontDatabase.applicationFontFamilies(font_id))
        return loaded

    @classmethod
    def configure_application_font(cls, app: QApplication | None = None) -> str:
        app = app or QApplication.instance()
        cls.prepare_font_environment()
        loaded = cls._load_system_font_files()
        available = set(QFontDatabase.families()) | set(loaded)
        chosen = next((family for family in FONT_FAMILIES if family in available), FONT_FAMILIES[-1])
        if chosen == FONT_FAMILIES[-1] and loaded:
            chosen = loaded[0]
        cls._font_family = chosen
        if app is not None:
            font = QFont(chosen)
            font.setPointSize(10)
            app.setFont(font)
        return chosen

    @classmethod
    def font_family(cls) -> str:
        return cls._font_family

    @classmethod
    def font_stack(cls) -> str:
        families = (cls._font_family, *[family for family in FONT_FAMILIES if family != cls._font_family])
        return ", ".join(f'"{family}"' if " " in family else family for family in families)

    @classmethod
    def icon_path(cls, name: str) -> str:
        return str((ICON_DIR / f"{name}.svg").resolve()).replace("\\", "/")

    @classmethod
    def asset_path(cls, name: str) -> str:
        return str((ASSET_DIR / name).resolve()).replace("\\", "/")

    @classmethod
    def stylesheet(cls, name: str) -> str:
        cls.set_theme(name)
        c = cls._current
        chevron_right = str((ASSET_DIR / "chevron-right.svg").resolve()).replace("\\", "/")
        chevron_down = str((ASSET_DIR / "chevron-down.svg").resolve()).replace("\\", "/")
        return f"""
QMainWindow, QWidget {{
    background: {c.bg};
    color: {c.text};
    font-family: {cls.font_stack()};
    font-size: {TYPE["body"]};
}}
QFrame#panel, QFrame#toolbarPanel {{
    background: {c.surface};
    border: 1px solid {c.border};
    border-radius: {RADIUS["lg"]}px;
}}
QFrame#filterPanel, QFrame#pathBox, QWidget#breakdownPanel {{
    background: {c.surface_2};
    border: 1px solid {c.border};
    border-radius: {RADIUS["md"]}px;
}}
QFrame#metricCard {{
    background: {c.elevated};
    border: 1px solid {c.border};
    border-left: 2px solid {c.accent};
    border-radius: {RADIUS["md"]}px;
}}
QLabel#brandIcon {{
    background: {c.accent_soft};
    border: 1px solid {c.border_strong};
    border-radius: {RADIUS["md"]}px;
    color: {c.accent};
    font-weight: 800;
}}
QLabel#appTitle {{
    font-size: {TYPE["title"]};
    font-weight: 750;
    color: {c.text};
}}
QLabel#tagline, QLabel#muted, QLabel#emptyBody {{
    color: {c.muted};
}}
QLabel#pathPill {{
    background: {c.input_bg};
    border: 1px solid {c.border_strong};
    border-radius: {RADIUS["pill"]}px;
    padding: 6px 12px;
    color: {c.muted};
}}
QLabel#panelTitle {{
    font-size: 10pt;
    font-weight: 700;
    color: {c.text};
}}
QLabel#sectionLabel {{
    color: {c.muted};
    font-size: {TYPE["small"]};
    font-weight: 700;
    text-transform: uppercase;
}}
QLabel#metricIcon {{
    color: {c.accent};
    font-size: 13pt;
}}
QLabel#metricValue {{
    font-size: {TYPE["metric"]};
    font-weight: 750;
    color: {c.text};
}}
QLabel#metricLabel, QLabel#breakdownLabel, QLabel#breakdownValue {{
    color: {c.muted};
    font-size: {TYPE["small"]};
}}
QLabel#inspectorName {{
    font-size: 13pt;
    font-weight: 750;
    color: {c.text};
}}
QLabel#inspectorSize {{
    font-size: 18pt;
    font-weight: 800;
    color: {c.text};
}}
QLabel#pathText {{
    background: {c.input_bg};
    border: 1px solid {c.border};
    border-radius: {RADIUS["md"]}px;
    padding: 8px;
    color: {c.muted};
}}
QLabel#emptyMark {{
    color: {c.accent};
    font-size: 11pt;
    font-weight: 800;
}}
QLabel#emptyTitle {{
    color: {c.text};
    font-size: 18pt;
    font-weight: 760;
}}
QLabel#scanTitle {{
    color: {c.text};
    font-size: 20pt;
    font-weight: 760;
}}
QPushButton, QToolButton {{
    background: {c.elevated};
    border: 1px solid {c.border_strong};
    border-radius: {RADIUS["md"]}px;
    padding: 7px 11px;
    color: {c.text};
}}
QPushButton:hover, QToolButton:hover {{
    background: {c.surface_2};
    border-color: {c.accent};
}}
QPushButton:pressed, QToolButton:pressed {{
    background: {c.input_bg};
}}
QPushButton#primary {{
    background: {c.accent};
    border-color: {c.accent};
    color: {"#05201a" if c.name == "dark" else "#ffffff"};
    font-weight: 700;
}}
QPushButton#danger {{
    background: transparent;
    border-color: {c.danger_soft};
    color: {c.danger};
    font-weight: 600;
}}
QPushButton#danger:hover {{
    background: {c.danger_soft};
    border-color: {c.danger};
}}
QPushButton#navButton {{
    text-align: left;
    background: transparent;
    border: 1px solid transparent;
    padding: 8px 10px;
    border-radius: {RADIUS["md"]}px;
}}
QPushButton#navButton:hover {{
    background: {c.surface_2};
    border-color: {c.border};
}}
QLineEdit, QComboBox {{
    background: {c.input_bg};
    border: 1px solid {c.border_strong};
    border-radius: {RADIUS["md"]}px;
    padding: 7px;
    color: {c.text};
    selection-background-color: {c.selected};
}}
QComboBox::drop-down {{
    width: 24px;
    border: 0;
}}
QComboBox::down-arrow {{
    image: url("{chevron_down}");
    width: 12px;
    height: 12px;
}}
QComboBox QAbstractItemView {{
    background: {c.surface};
    color: {c.text};
    border: 1px solid {c.border};
    selection-background-color: {c.selected};
}}
QCheckBox {{
    color: {c.muted};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 5px;
    border: 1px solid {c.border_strong};
    background: {c.input_bg};
}}
QCheckBox::indicator:checked {{
    background: {c.accent};
    border-color: {c.accent};
}}
QProgressBar {{
    background: {c.input_bg};
    border: 1px solid {c.border};
    border-radius: 7px;
    min-height: 12px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {c.accent}, stop:1 {c.accent_2});
    border-radius: 7px;
}}
QTreeView, QListWidget {{
    background: {c.input_bg};
    alternate-background-color: {c.surface_2};
    border: 1px solid {c.border};
    border-radius: {RADIUS["lg"]}px;
    outline: none;
}}
QTreeView::item {{
    min-height: 34px;
    padding: 4px 6px;
    border-radius: {RADIUS["sm"]}px;
}}
QTreeView::item:hover, QListWidget::item:hover {{
    background: {c.surface_2};
}}
QTreeView::item:selected, QListWidget::item:selected {{
    background: {c.selected};
    color: {c.selected_text};
}}
QTreeView::branch {{
    background: transparent;
    width: 18px;
}}
QTreeView::branch:has-children:closed {{ image: url("{chevron_right}"); }}
QTreeView::branch:has-children:open {{ image: url("{chevron_down}"); }}
QHeaderView::section {{
    background: {c.elevated};
    color: {c.muted};
    padding: 8px;
    border: 0;
    border-right: 1px solid {c.border};
    font-weight: 700;
}}
QTabWidget::pane {{
    border: 1px solid {c.border};
    border-radius: {RADIUS["lg"]}px;
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {c.muted};
    padding: 8px 12px;
    border: 1px solid transparent;
    border-top-left-radius: {RADIUS["md"]}px;
    border-top-right-radius: {RADIUS["md"]}px;
}}
QTabBar::tab:selected {{
    background: {c.elevated};
    color: {c.text};
    border-color: {c.border_strong};
    border-bottom-color: {c.elevated};
}}
QListWidget::item {{
    padding: 8px;
    border-radius: {RADIUS["md"]}px;
    color: {c.text};
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {c.scrollbar};
    border-radius: 5px;
    min-height: 34px;
}}
QScrollBar::handle:vertical:hover {{ background: {c.scrollbar_hover}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {c.scrollbar};
    border-radius: 5px;
    min-width: 34px;
}}
QScrollBar::handle:horizontal:hover {{ background: {c.scrollbar_hover}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QStatusBar {{
    background: {c.bg};
    color: {c.muted};
}}
"""
