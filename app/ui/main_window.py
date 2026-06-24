from __future__ import annotations

import os
import platform
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from time import time

from PySide6.QtCore import QObject, QSortFilterProxyModel, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from ..core.deletion import DeletionResult, delete_permanently, move_to_trash
from ..core.file_types import TYPE_EXTENSIONS, classify_extension
from ..core.filters import FilterCriteria, item_matches, parse_size
from ..core.formatting import format_size
from ..core.models import DiskItem, ScanResult
from ..core.scanner import DiskScanner, ScanProgress
from ..services.recent_paths import (
    add_recent_path,
    get_everything_cli_path,
    get_language,
    get_parallel_workers,
    get_prefer_indexed_scan,
    get_recent_paths,
    get_scan_engine,
    get_theme,
    has_seen_onboarding,
    set_everything_cli_path,
    set_language,
    set_onboarding_seen,
    set_parallel_workers,
    set_prefer_indexed_scan,
    set_scan_engine,
    set_theme,
)
from ..services.privileges import is_admin, relaunch_as_admin
from .dialogs.confirm_delete import ConfirmDeleteDialog
from .dialogs.onboarding import OnboardingDialog
from .dialogs.settings import SettingsDialog, SettingsValues
from .widgets.item_model import DiskTreeModel
from .widgets.polished import AnalysisList, EmptyState, FileTypeBreakdown, MetricCard
from .widgets.reclaim_meter import ReclaimMeter
from .widgets.scan_overlay import ScanOverlay
from .widgets.size_delegate import SizeBarDelegate
from .widgets.treemap import TreemapWidget
from .theme import ThemeManager


TRANSLATIONS = {
    "en": {
        "choose_folder": "Choose Folder",
        "rescan": "Rescan",
        "settings": "Settings",
        "admin": "Admin",
        "admin_on": "Admin: on",
        "light": "Light",
        "dark": "Dark",
        "ready": "Ready. Choose or drop a folder to scan.",
        "choose_dialog": "Choose folder to scan",
        "settings_saved": "Settings saved.",
    },
    "it": {
        "choose_folder": "Scegli cartella",
        "rescan": "Riscansiona",
        "settings": "Impostazioni",
        "admin": "Admin",
        "admin_on": "Admin: attivo",
        "light": "Chiaro",
        "dark": "Scuro",
        "ready": "Pronto. Scegli o trascina una cartella da scansionare.",
        "choose_dialog": "Scegli cartella da scansionare",
        "settings_saved": "Impostazioni salvate.",
    },
}



class ScanWorker(QObject):
    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        path: Path,
        engine: str = "auto",
        everything_cli_path: str = "",
        parallel_workers: int = 0,
        prefer_indexed: bool = True,
    ) -> None:
        super().__init__()
        self.path = path
        self.engine = engine
        self.everything_cli_path = everything_cli_path
        self.parallel_workers = parallel_workers
        self.prefer_indexed = prefer_indexed
        self._cancelled = False

    @Slot()
    def run(self) -> None:
        try:
            scanner = DiskScanner(
                progress_callback=self.progress.emit,
                cancel_callback=lambda: self._cancelled,
                progress_interval=50,
                engine=self.engine,
                everything_cli_path=self.everything_cli_path,
                parallel_workers=self.parallel_workers,
                prefer_indexed=self.prefer_indexed,
            )
            result = scanner.scan(self.path)
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))

    def cancel(self) -> None:
        self._cancelled = True


class DeleteWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, item: DiskItem, permanent: bool = False) -> None:
        super().__init__()
        self.item = item
        self.permanent = permanent

    @Slot()
    def run(self) -> None:
        try:
            action = delete_permanently if self.permanent else move_to_trash
            self.finished.emit(action(self.item))
        except Exception as exc:
            self.failed.emit(str(exc))


class DiskFilterProxy(QSortFilterProxyModel):
    def __init__(self) -> None:
        super().__init__()
        self.criteria = FilterCriteria()
        self.setRecursiveFilteringEnabled(True)
        self.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def set_criteria(self, criteria: FilterCriteria) -> None:
        self.criteria = criteria
        self.invalidateFilter()

    def lessThan(self, left, right) -> bool:  # type: ignore[override]
        if left.column() == 1:
            return left.data(Qt.ItemDataRole.UserRole + 1) < right.data(Qt.ItemDataRole.UserRole + 1)
        if left.column() == 4:
            return left.data(Qt.ItemDataRole.UserRole + 2) < right.data(Qt.ItemDataRole.UserRole + 2)
        return str(left.data() or "").lower() < str(right.data() or "").lower()

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:  # type: ignore[override]
        model = self.sourceModel()
        index = model.index(source_row, 0, source_parent)
        item = index.data(Qt.ItemDataRole.UserRole)
        if item is None:
            return True
        if item_matches(item, self.criteria):
            return True
        for row in range(model.rowCount(index)):
            if self.filterAcceptsRow(row, index):
                return True
        return False


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        ThemeManager.configure_application_font(QApplication.instance())
        self.setWindowTitle("DiskBloom")
        self.resize(1450, 860)
        self.setMinimumSize(980, 640)
        self.root_item: DiskItem | None = None
        self.current_path: Path | None = None
        self._scan_thread: QThread | None = None
        self._scan_worker: ScanWorker | None = None
        self._delete_thread: QThread | None = None
        self._delete_worker: DeleteWorker | None = None
        self._selected_item: DiskItem | None = None
        self.theme = get_theme()
        self.language = get_language()
        self.scan_engine = get_scan_engine()
        self.everything_cli_path = get_everything_cli_path()
        self.parallel_workers = get_parallel_workers()
        self.prefer_indexed_scan = get_prefer_indexed_scan()
        self._build_ui()
        self._apply_theme()
        self._load_recent()
        self.setAcceptDrops(True)
        if not has_seen_onboarding():
            QTimer.singleShot(350, self.show_onboarding)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(14, 12, 14, 8)
        root_layout.setSpacing(10)
        root_layout.addWidget(self._toolbar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter, 1)
        splitter.addWidget(self._sidebar())
        splitter.addWidget(self._center())
        splitter.addWidget(self._inspector())
        splitter.setSizes([250, 860, 370])

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage(self._t("ready"))

    def _toolbar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("toolbarPanel")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(12, 8, 10, 8)
        layout.setSpacing(9)
        brand_icon = QLabel()
        brand_icon.setObjectName("brandIcon")
        brand_icon.setFixedSize(34, 34)
        brand_icon.setPixmap(QIcon(ThemeManager.asset_path("logo.svg")).pixmap(34, 34))
        brand_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(brand_icon)
        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title = QLabel("DiskBloom")
        title.setObjectName("appTitle")
        tagline = QLabel("See what is growing on your disk.")
        tagline.setObjectName("tagline")
        title_box.addWidget(title)
        title_box.addWidget(tagline)
        layout.addLayout(title_box)
        self.path_label = QLabel("No folder selected")
        self.path_label.setObjectName("pathPill")
        self.path_label.setMinimumWidth(220)
        self.path_label.setMaximumWidth(380)
        layout.addWidget(self.path_label, 1)
        self.choose_button = QPushButton(self._t("choose_folder"))
        self.choose_button.setObjectName("primary")
        self.choose_button.setIcon(self._icon("folder"))
        self.choose_button.clicked.connect(self.choose_folder)
        layout.addWidget(self.choose_button)
        self.rescan_button = QPushButton(self._t("rescan"))
        self.rescan_button.setIcon(self._icon("refresh"))
        self.rescan_button.clicked.connect(self.rescan)
        layout.addWidget(self.rescan_button)
        self.theme_button = QPushButton(self._theme_button_text())
        self.theme_button.setIcon(self._icon("moon"))
        self.theme_button.clicked.connect(lambda: self.toggle_theme(self.theme_button))
        layout.addWidget(self.theme_button)
        self.settings_button = QPushButton(self._t("settings"))
        self.settings_button.setIcon(self._icon("settings"))
        self.settings_button.clicked.connect(self.open_settings)
        layout.addWidget(self.settings_button)
        self.admin_button = QPushButton(self._t("admin") if not is_admin() else self._t("admin_on"))
        self.admin_button.setIcon(self._icon("shield"))
        self.admin_button.setToolTip("Restart DiskBloom with administrator privileges for fuller system scans and permanent deletion.")
        self.admin_button.clicked.connect(self.request_admin)
        self.admin_button.setEnabled(not is_admin())
        layout.addWidget(self.admin_button)
        return panel

    def _sidebar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(7)
        layout.addWidget(self._section_label("Quick locations"))
        for name, path, icon in self._quick_locations():
            button = QPushButton(name)
            button.setObjectName("navButton")
            button.setIcon(self._icon(icon))
            button.setToolTip(str(path))
            button.clicked.connect(lambda checked=False, p=path: self.start_scan(p))
            layout.addWidget(button)
        layout.addSpacing(8)
        layout.addWidget(self._section_label("Recent scans"))
        self.recent_list = QListWidget()
        self.recent_list.setMinimumHeight(70)
        self.recent_list.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        self.recent_list.itemActivated.connect(lambda item: self.start_scan(Path(item.data(Qt.ItemDataRole.UserRole))))
        self.recent_list.itemClicked.connect(lambda item: self.start_scan(Path(item.data(Qt.ItemDataRole.UserRole))))
        layout.addWidget(self.recent_list, 1)
        layout.addWidget(self._section_label("Filters"))
        filter_panel = QFrame()
        filter_panel.setObjectName("filterPanel")
        filter_layout = QVBoxLayout(filter_panel)
        filter_layout.setContentsMargins(10, 10, 10, 10)
        filter_layout.setSpacing(7)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filename search")
        self.ext_input = QLineEdit()
        self.ext_input.setPlaceholderText("Extension, e.g. .zip")
        self.min_size = QComboBox()
        self.min_size.setEditable(True)
        self.min_size.addItems(["", "100 MB", "1 GB", "10 GB"])
        self.age_filter = QComboBox()
        self.age_filter.addItems(["Any age", "Older than 6 months", "Older than 1 year"])
        self.only_files = QCheckBox("Only files")
        self.only_folders = QCheckBox("Only folders")
        for widget in (self.search_input, self.ext_input):
            widget.textChanged.connect(self.apply_filters)
            filter_layout.addWidget(widget)
        self.min_size.currentTextChanged.connect(self.apply_filters)
        self.age_filter.currentIndexChanged.connect(self.apply_filters)
        self.only_files.toggled.connect(self.apply_filters)
        self.only_folders.toggled.connect(self.apply_filters)
        filter_layout.addWidget(self.min_size)
        filter_layout.addWidget(self.age_filter)
        filter_layout.addWidget(self.only_files)
        filter_layout.addWidget(self.only_folders)
        layout.addWidget(filter_panel)
        return panel

    def _center(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        tree_title = QLabel("Disk usage tree")
        tree_title.setObjectName("panelTitle")
        layout.addWidget(tree_title)
        self.center_stack = QStackedWidget()
        self.center_stack.setMinimumHeight(0)
        self.center_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.model = DiskTreeModel()
        self.proxy = DiskFilterProxy()
        self.proxy.setSourceModel(self.model)
        self.tree = QTreeView()
        self.tree.setMinimumHeight(0)
        self.tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.tree.setModel(self.proxy)
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setItemsExpandable(True)
        self.tree.setExpandsOnDoubleClick(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(22)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(1, Qt.SortOrder.DescendingOrder)
        self.tree.setItemDelegateForColumn(1, SizeBarDelegate())
        self.tree.selectionModel().selectionChanged.connect(self.on_selection_changed)
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.tree.setColumnWidth(0, 320)
        self.tree.setColumnWidth(1, 112)
        self.tree.setColumnWidth(2, 82)
        self.tree.setColumnWidth(3, 82)
        self.tree.setColumnWidth(4, 130)
        self.scan_overlay = ScanOverlay()
        self.tree_empty = EmptyState(
            "Choose a folder to scan",
            "Use the primary action, a quick location, or drag a folder here. Results will appear as an expandable disk usage tree.",
            "Choose Folder",
        )
        self.tree_empty.action_button.clicked.connect(self.choose_folder)
        self.center_stack.addWidget(self.tree_empty)
        self.center_stack.addWidget(self.tree)
        self.center_stack.addWidget(self.scan_overlay)
        self.center_stack.setCurrentWidget(self.tree_empty)
        vertical = QSplitter(Qt.Orientation.Vertical)
        vertical.addWidget(self.center_stack)
        vertical.addWidget(self._treemap_panel())
        vertical.setSizes([620, 240])
        layout.addWidget(vertical)
        return panel

    def _treemap_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("treemapPanel")
        panel.setMinimumHeight(180)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(7)

        header = QHBoxLayout()
        title = QLabel("Treemap")
        title.setObjectName("panelTitle")
        header.addWidget(title)
        self.treemap_path = QLabel("No scan loaded")
        self.treemap_path.setObjectName("muted")
        self.treemap_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        header.addWidget(self.treemap_path, 1)
        self.treemap_back = QPushButton("Back")
        self.treemap_back.setEnabled(False)
        self.treemap_back.clicked.connect(self._treemap_back)
        header.addWidget(self.treemap_back)
        layout.addLayout(header)

        self.treemap = TreemapWidget()
        self.treemap.itemClicked.connect(self.select_item)
        self.treemap.zoomChanged.connect(self._on_treemap_zoom_changed)
        layout.addWidget(self.treemap, 1)
        return panel

    def _inspector(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setMinimumWidth(330)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        self._build_stat_cards(layout)
        self.tabs = QTabWidget()
        self.tabs.setMinimumHeight(0)
        self.tabs.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        details = QWidget()
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(8, 8, 8, 8)
        details_layout.setSpacing(6)
        self.inspector_empty = EmptyState("No item selected", "Select a folder or file in the tree to inspect size, path, modified date, and cleanup actions.")
        details_layout.addWidget(self.inspector_empty, 1)
        self.item_details = QWidget()
        item_layout = QVBoxLayout(self.item_details)
        item_layout.setContentsMargins(0, 0, 0, 0)
        item_layout.setSpacing(8)
        header = QFrame()
        header.setObjectName("pathBox")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 10, 10, 10)
        self.item_icon = QLabel()
        self.item_icon.setFixedSize(34, 34)
        self.item_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.item_icon)
        header_text = QVBoxLayout()
        header_text.setSpacing(1)
        self.item_name = QLabel("-")
        self.item_name.setObjectName("inspectorName")
        self.item_name.setWordWrap(True)
        self.item_meta = QLabel("-")
        self.item_meta.setObjectName("muted")
        header_text.addWidget(self.item_name)
        header_text.addWidget(self.item_meta)
        header_layout.addLayout(header_text, 1)
        item_layout.addWidget(header)
        self.item_size = QLabel("-")
        self.item_size.setObjectName("inspectorSize")
        item_layout.addWidget(self.item_size)
        self.path_box = QLabel("-")
        self.path_box.setObjectName("pathText")
        self.path_box.setWordWrap(True)
        self.path_box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        item_layout.addWidget(self.path_box)
        open_button = QPushButton("Open in Explorer")
        open_button.setIcon(self._icon("open"))
        open_button.clicked.connect(self.open_selected)
        copy_button = QPushButton("Copy path")
        copy_button.setIcon(self._icon("copy"))
        copy_button.clicked.connect(self.copy_selected_path)
        trash_button = QPushButton("Move to Trash")
        trash_button.setObjectName("primary")
        trash_button.setIcon(self._icon("trash"))
        trash_button.clicked.connect(self.confirm_delete)
        item_layout.addWidget(open_button)
        item_layout.addWidget(copy_button)
        item_layout.addWidget(trash_button)
        self.advanced_toggle = QToolButton()
        self.advanced_toggle.setText("Advanced")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        permanent_button = QPushButton("Delete permanently")
        permanent_button.setObjectName("danger")
        permanent_button.clicked.connect(self.confirm_permanent_delete)
        permanent_button.setVisible(False)
        self.advanced_toggle.toggled.connect(permanent_button.setVisible)
        item_layout.addWidget(self.advanced_toggle)
        item_layout.addWidget(permanent_button)
        self.item_details.setVisible(False)
        details_layout.addWidget(self.item_details, 1)
        self.tabs.addTab(details, "Inspector")

        analysis = QWidget()
        analysis_layout = QVBoxLayout(analysis)
        analysis_layout.setContentsMargins(8, 8, 8, 8)
        analysis_layout.setSpacing(6)
        analysis_layout.addWidget(self._section_label("File type breakdown"))
        self.breakdown = FileTypeBreakdown()
        analysis_layout.addWidget(self.breakdown)
        analysis_layout.addWidget(self._section_label("Largest files"))
        self.largest_files = AnalysisList()
        self.largest_files.setMinimumHeight(55)
        self.largest_files.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        self.largest_files.itemActivated.connect(self._list_item_activated)
        analysis_layout.addWidget(self.largest_files)
        analysis_layout.addWidget(self._section_label("Old large files"))
        self.old_files = AnalysisList()
        self.old_files.setMinimumHeight(55)
        self.old_files.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        self.old_files.itemActivated.connect(self._list_item_activated)
        analysis_layout.addWidget(self.old_files)
        self.tabs.addTab(analysis, "Analysis")
        layout.addWidget(self.tabs, 1)
        self.reclaim_meter = ReclaimMeter()
        layout.addWidget(self.reclaim_meter)
        return panel

    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("panelTitle")
        return label

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionLabel")
        return label

    def _build_stat_cards(self, layout: QVBoxLayout) -> None:
        grid = QGridLayout()
        grid.setHorizontalSpacing(7)
        grid.setVerticalSpacing(7)
        self.stat_total = self._stat_card("Total scanned", "drive")
        self.stat_files = self._stat_card("Files", "file")
        self.stat_folders = self._stat_card("Folders", "folder")
        self.stat_largest = self._stat_card("Largest item", "file")
        self.stat_reclaim = self._stat_card("Reclaimable", "trash")
        for index, card in enumerate([self.stat_total, self.stat_files, self.stat_folders, self.stat_largest, self.stat_reclaim]):
            grid.addWidget(card, index // 2, index % 2)
        layout.addLayout(grid)

    def _stat_card(self, label_text: str, icon: str) -> MetricCard:
        card = MetricCard(label_text, ThemeManager.icon_path(icon))
        return card

    def _quick_locations(self) -> list[tuple[str, Path, str]]:
        home = Path.home()
        locations: list[tuple[str, Path, str]] = [("Home", home, "home")]
        icon_map = {
            "Desktop": "desktop",
            "Downloads": "download",
            "Documents": "document",
        }
        for name in ("Desktop", "Downloads", "Documents"):
            path = home / name
            if path.exists():
                locations.append((name, path, icon_map[name]))
        if platform.system() == "Windows" and Path("C:/").exists():
            locations.append(("C:\\  Full disk", Path("C:/"), "drive"))
        else:
            locations.append(("/", Path("/"), "drive"))
        return locations

    def _icon(self, name: str) -> QIcon:
        return QIcon(ThemeManager.icon_path(name))

    def _load_recent(self) -> None:
        self.recent_list.clear()
        for path in get_recent_paths():
            item = QListWidgetItem(self._short_path(path, 34))
            item.setToolTip(path)
            item.setData(Qt.ItemDataRole.UserRole, path)
            self.recent_list.addItem(item)

    def _short_path(self, path: str, max_chars: int = 64) -> str:
        if len(path) <= max_chars:
            return path
        return "..." + path[-(max_chars - 3):]

    def _set_path_label(self, path: str) -> None:
        self.path_label.setText(self._short_path(path, 78))
        self.path_label.setToolTip(path)

    def _t(self, key: str) -> str:
        return TRANSLATIONS.get(self.language, TRANSLATIONS["en"]).get(key, key)

    def _theme_button_text(self) -> str:
        return self._t("light") if self.theme == "dark" else self._t("dark")

    def _refresh_text(self) -> None:
        if hasattr(self, "choose_button"):
            self.choose_button.setText(self._t("choose_folder"))
            self.rescan_button.setText(self._t("rescan"))
            self.settings_button.setText(self._t("settings"))
            self.theme_button.setText(self._theme_button_text())
            self.admin_button.setText(self._t("admin") if not is_admin() else self._t("admin_on"))

    def choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, self._t("choose_dialog"), str(Path.home()))
        if folder:
            self.start_scan(Path(folder))

    def rescan(self) -> None:
        if self.current_path:
            self.start_scan(self.current_path)

    def open_settings(self) -> None:
        dialog = SettingsDialog(
            SettingsValues(
                language=self.language,
                theme=self.theme,
                scan_engine=self.scan_engine,
                everything_cli_path=self.everything_cli_path,
                parallel_workers=self.parallel_workers,
                prefer_indexed_scan=self.prefer_indexed_scan,
                show_onboarding_next_start=False,
            ),
            self,
        )
        if dialog.exec():
            values = dialog.current_values()
            self.language = values.language
            self.theme = values.theme
            self.scan_engine = values.scan_engine
            self.everything_cli_path = values.everything_cli_path
            self.parallel_workers = values.parallel_workers
            self.prefer_indexed_scan = values.prefer_indexed_scan
            set_language(self.language)
            set_theme(self.theme)
            set_scan_engine(self.scan_engine)
            set_everything_cli_path(self.everything_cli_path)
            set_parallel_workers(self.parallel_workers)
            set_prefer_indexed_scan(self.prefer_indexed_scan)
            set_onboarding_seen(not values.show_onboarding_next_start)
            self._apply_theme()
            self._refresh_text()
            self.status.showMessage(f"{self._t('settings_saved')} Engine: {self._engine_label(self.scan_engine)}.")

    def show_onboarding(self) -> None:
        dialog = OnboardingDialog(self.language, self)
        dialog.choose_folder_requested.connect(self.choose_folder)
        dialog.exec()
        set_onboarding_seen(True)

    def start_scan(self, path: Path) -> None:
        if self._is_thread_running(self._scan_thread):
            QMessageBox.information(self, "Scan running", "Wait for the current scan to finish before starting another.")
            return
        self.current_path = Path(path).expanduser()
        if platform.system() == "Windows" and str(self.current_path).upper().startswith("C:") and not is_admin():
            self.status.showMessage("Scanning without administrator privileges. Some protected folders may be skipped.")
        self._set_path_label(str(self.current_path))
        self.status.showMessage(f"Scanning {self.current_path}... Engine: {self._engine_label(self.scan_engine)}")
        self.model.set_root(None)
        self.root_item = None
        self.treemap.set_root(None)
        self._on_treemap_zoom_changed(None)
        self.scan_overlay.start(self.current_path)
        self.center_stack.setCurrentWidget(self.scan_overlay)
        thread = QThread(self)
        worker = ScanWorker(
            self.current_path,
            self.scan_engine,
            self.everything_cli_path,
            self.parallel_workers,
            self.prefer_indexed_scan,
        )
        self._scan_thread = thread
        self._scan_worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self.on_scan_progress)
        worker.finished.connect(self.on_scan_finished)
        worker.failed.connect(self.on_scan_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(lambda t=thread: self._cleanup_scan_thread(t))
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def _is_thread_running(self, thread: QThread | None) -> bool:
        if thread is None:
            return False
        try:
            return thread.isRunning()
        except RuntimeError:
            return False

    def _cleanup_scan_thread(self, thread: QThread) -> None:
        if self._scan_thread is thread:
            self._scan_thread = None
            self._scan_worker = None

    def _cleanup_delete_thread(self, thread: QThread) -> None:
        if self._delete_thread is thread:
            self._delete_thread = None
            self._delete_worker = None

    @Slot(object)
    def on_scan_progress(self, progress: ScanProgress) -> None:
        self.scan_overlay.set_progress(
            progress.current_path,
            progress.files_scanned,
            progress.folders_scanned,
            progress.total_size,
        )
        self.status.showMessage(
            f"Engine: {progress.engine_name} | {progress.files_per_second:.0f} files/s | "
            f"{progress.folders_per_second:.0f} folders/s | {format_size(progress.bytes_per_second)}/s | "
            f"Files {progress.files_scanned} | Folders {progress.folders_scanned}"
        )

    @Slot(object)
    def on_scan_finished(self, result: ScanResult) -> None:
        self.root_item = result.root
        self.scan_overlay.finish()
        self.model.set_root(result.root)
        self.center_stack.setCurrentWidget(self.tree)
        self.tree.expandToDepth(1)
        self.tree.sortByColumn(1, Qt.SortOrder.DescendingOrder)
        self.treemap.set_root(result.root)
        if self.current_path:
            add_recent_path(self.current_path)
        self._load_recent()
        largest = result.stats.largest_file.formatted_size + " " + result.stats.largest_file.name if result.stats.largest_file else "-"
        reclaimable = self._estimate_reclaimable(result.root)
        self.stat_total.set_value(format_size(result.root.size))
        self.stat_files.set_value(str(result.stats.files_scanned))
        self.stat_folders.set_value(str(result.stats.folders_scanned))
        self.stat_largest.set_value(largest[:28])
        self.stat_reclaim.set_value(format_size(reclaimable))
        self._refresh_analysis()
        errors = f" | {result.stats.permission_errors} access errors" if result.stats.permission_errors else ""
        symlinks = f" | {result.stats.skipped_symlinks} symlinks skipped" if result.stats.skipped_symlinks else ""
        self.status.showMessage(
            f"Scan complete with {result.stats.engine_name}: {format_size(result.root.size)} found in "
            f"{result.stats.elapsed_seconds:.2f}s{errors}{symlinks}"
        )

    def _engine_label(self, engine: str) -> str:
        return {
            "auto": "Auto",
            "standard": "Standard",
            "parallel": "Parallel",
            "everything": "Everything",
            "windows_fast": "Windows Fast / Experimental",
        }.get(engine, "Auto")

    @Slot(str)
    def on_scan_failed(self, message: str) -> None:
        self.scan_overlay.fail(message)
        self.center_stack.setCurrentWidget(self.scan_overlay)
        self.status.showMessage("Scan failed")
        QMessageBox.critical(self, "Scan failed", message)

    def apply_filters(self) -> None:
        days = 0
        if self.age_filter.currentIndex() == 1:
            days = 183
        elif self.age_filter.currentIndex() == 2:
            days = 365
        if self.only_files.isChecked() and self.only_folders.isChecked():
            self.only_folders.setChecked(False)
        criteria = FilterCriteria(
            search=self.search_input.text(),
            extension=self.ext_input.text(),
            min_size=parse_size(self.min_size.currentText()),
            only_files=self.only_files.isChecked(),
            only_folders=self.only_folders.isChecked(),
            older_than_days=days,
        )
        self.proxy.set_criteria(criteria)

    def on_selection_changed(self) -> None:
        indexes = self.tree.selectionModel().selectedRows()
        if not indexes:
            self._selected_item = None
            self.treemap.set_selected_item(None)
            return
        source = self.proxy.mapToSource(indexes[0])
        self._selected_item = source.data(Qt.ItemDataRole.UserRole)
        self.treemap.set_selected_item(self._selected_item)
        self._update_details()

    def _treemap_back(self) -> None:
        self.treemap.go_back()

    @Slot(object)
    def _on_treemap_zoom_changed(self, item: DiskItem | None) -> None:
        if item:
            self.treemap_path.setText(item.absolute_path)
            self.treemap_path.setToolTip(item.absolute_path)
        else:
            self.treemap_path.setText("No scan loaded")
            self.treemap_path.setToolTip("")
        self.treemap_back.setEnabled(self.treemap.can_go_back())

    def _update_details(self) -> None:
        item = self._selected_item
        if not item:
            self.item_details.setVisible(False)
            self.inspector_empty.setVisible(True)
            return
        self.inspector_empty.setVisible(False)
        self.item_details.setVisible(True)
        self.item_icon.setPixmap(self._icon("folder" if item.is_folder else "file").pixmap(28, 28))
        self.item_name.setText(item.name)
        self.item_name.setToolTip(item.name)
        self.item_meta.setText(f"{item.display_type}  |  Modified {item.formatted_modified}  |  {len(item.children)} children")
        self.item_size.setText(item.formatted_size)
        self.path_box.setText(item.absolute_path)
        self.path_box.setToolTip(item.absolute_path)

    def open_selected(self) -> None:
        if not self._selected_item:
            return
        path = self._selected_item.path
        try:
            if platform.system() == "Windows":
                os.startfile(path if path.is_dir() else path.parent)  # type: ignore[attr-defined]
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", str(path if path.is_dir() else path.parent)])
            else:
                subprocess.Popen(["xdg-open", str(path if path.is_dir() else path.parent)])
        except Exception as exc:
            QMessageBox.warning(self, "Open failed", str(exc))

    def copy_selected_path(self) -> None:
        if self._selected_item:
            QApplication.clipboard().setText(self._selected_item.absolute_path)
            self.status.showMessage("Path copied to clipboard")

    def confirm_delete(self) -> None:
        if not self._selected_item:
            return
        if self._is_selected_scan_root():
            answer = QMessageBox.warning(
                self,
                "Move scanned root to Trash?",
                "The selected item is the root folder of the current scan. Moving it to Trash affects the whole scanned folder.",
                QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Ok:
                return
        dialog = ConfirmDeleteDialog(self._selected_item, permanent=False, parent=self)
        if dialog.exec():
            self._delete_selected(self._selected_item, permanent=False)

    def confirm_permanent_delete(self) -> None:
        if not self._selected_item:
            return
        if self._is_selected_scan_root():
            answer = QMessageBox.warning(
                self,
                "Permanently delete scanned root?",
                "The selected item is the root folder of the current scan. Permanent deletion would remove the whole scanned folder and cannot be restored from Trash.",
                QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Ok:
                return
        if not is_admin():
            answer = QMessageBox.question(
                self,
                "Administrator required",
                "Permanent deletion requires administrator privileges. Restart DiskBloom as administrator now?",
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.request_admin()
            return
        dialog = ConfirmDeleteDialog(self._selected_item, permanent=True, parent=self)
        if dialog.exec():
            self._delete_selected(self._selected_item, permanent=True)

    def _is_selected_scan_root(self) -> bool:
        return bool(self._selected_item and self.root_item and self._selected_item.path == self.root_item.path)

    def _delete_selected(self, item: DiskItem, permanent: bool = False) -> None:
        if self._is_thread_running(self._delete_thread):
            QMessageBox.information(self, "Deletion running", "Wait for the current Trash operation to finish.")
            return
        self.reclaim_meter.start()
        action_text = "Permanently deleting" if permanent else "Moving"
        self.status.showMessage(f"{action_text} {item.name}...")
        thread = QThread(self)
        worker = DeleteWorker(item, permanent=permanent)
        self._delete_thread = thread
        self._delete_worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(lambda result, i=item, p=permanent: self.on_delete_finished(i, result, p))
        worker.failed.connect(self.on_delete_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(lambda t=thread: self._cleanup_delete_thread(t))
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def on_delete_finished(self, item: DiskItem, result: DeletionResult, permanent: bool = False) -> None:
        self.reclaim_meter.finish(result.reclaimed_size, result.bytes_per_second, result.processed_files, permanent=permanent)
        if item.parent:
            item.parent.children.remove(item)
            node = item.parent
            while node:
                node.size = max(0, node.size - item.size)
                node = node.parent
        self.model.set_root(self.root_item)
        self.treemap.set_root(self.root_item)
        self._refresh_analysis()
        if permanent:
            self.status.showMessage(f"Permanently deleted: {item.name}.")
        else:
            self.status.showMessage(f"Moved to Trash: {item.name}. You can restore it from the system Trash/Recycle Bin.")

    @Slot(str)
    def on_delete_failed(self, message: str) -> None:
        self.reclaim_meter.fail("Deletion failed")
        QMessageBox.critical(self, "Move to Trash failed", message)

    def _refresh_analysis(self) -> None:
        self.largest_files.clear()
        self.old_files.clear()
        if not self.root_item:
            self.breakdown.set_totals({})
            return
        totals: dict[str, int] = defaultdict(int)
        files = [item for item in self.root_item.iter_items() if not item.is_folder]
        for item in files:
            totals[classify_extension(item.extension)] += item.size
        self.breakdown.set_totals(totals)
        self.largest_files.set_items(sorted(files, key=lambda i: i.size, reverse=True)[:25])
        cutoff = time() - 365 * 24 * 60 * 60
        old_large = [item for item in files if item.modified and item.modified < cutoff and item.size >= 100 * 1024 * 1024]
        self.old_files.set_items(sorted(old_large, key=lambda i: i.size, reverse=True)[:25], show_modified=True)

    def _list_item_activated(self, row: QListWidgetItem) -> None:
        item = row.data(Qt.ItemDataRole.UserRole)
        if item:
            self.select_item(item)

    def select_item(self, item: DiskItem) -> None:
        source = self.model.index_for_item(item)
        if not source.isValid():
            return
        proxy_index = self.proxy.mapFromSource(source)
        self.tree.setCurrentIndex(proxy_index)
        self.tree.scrollTo(proxy_index)
        self._selected_item = item
        self.treemap.set_selected_item(item)
        self._update_details()

    def _estimate_reclaimable(self, root: DiskItem) -> int:
        cutoff = time() - 365 * 24 * 60 * 60
        temp_exts = {".tmp", ".log", ".bak", ".old", ".dmp"}
        total = 0
        for item in root.iter_items():
            if item.is_folder:
                continue
            if item.extension.lower() in temp_exts or (item.modified and item.modified < cutoff and item.size > 100 * 1024 * 1024):
                total += item.size
        return total

    def toggle_theme(self, button: QPushButton) -> None:
        self.theme = "light" if self.theme == "dark" else "dark"
        set_theme(self.theme)
        self._apply_theme()
        self._refresh_text()

    def _apply_theme(self) -> None:
        QApplication.instance().setStyleSheet(ThemeManager.stylesheet(self.theme))
        for widget in (getattr(self, "reclaim_meter", None), getattr(self, "scan_overlay", None), getattr(self, "treemap", None)):
            if widget:
                widget.update()

    def request_admin(self) -> None:
        if is_admin():
            QMessageBox.information(self, "Administrator", "DiskBloom is already running as administrator.")
            return
        if relaunch_as_admin():
            QApplication.quit()
        else:
            QMessageBox.warning(self, "Administrator", "Could not start the elevated DiskBloom process.")

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if Path(url.toLocalFile()).is_dir():
                    event.acceptProposedAction()
                    return

    def dropEvent(self, event) -> None:  # type: ignore[override]
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.is_dir():
                self.start_scan(path)
                event.acceptProposedAction()
                return

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._scan_worker:
            self._scan_worker.cancel()
        for thread in (self._scan_thread, self._delete_thread):
            if self._is_thread_running(thread):
                thread.quit()
                thread.wait(1500)
        event.accept()


def run() -> None:
    ThemeManager.prepare_font_environment()
    app = QApplication(sys.argv)
    app.setApplicationName("DiskBloom")
    ThemeManager.configure_application_font(app)
    icon_path = Path(__file__).resolve().parents[2] / "assets" / "icon.svg"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
