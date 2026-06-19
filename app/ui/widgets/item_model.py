from __future__ import annotations

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt
from PySide6.QtGui import QColor
from PySide6.QtGui import QIcon

from ..theme import ThemeManager

from ...core.models import DiskItem


COLUMNS = ["Name", "Size", "% of parent", "Type", "Modified", "Full path"]


class DiskTreeModel(QAbstractItemModel):
    def __init__(self) -> None:
        super().__init__()
        self.root: DiskItem | None = None
        self._folder_icon = QIcon(ThemeManager.icon_path("folder"))
        self._file_icon = QIcon(ThemeManager.icon_path("file"))

    def set_root(self, root: DiskItem | None) -> None:
        self.beginResetModel()
        self.root = root
        self.endResetModel()

    def item_from_index(self, index: QModelIndex) -> DiskItem | None:
        if index.isValid():
            return index.internalPointer()
        return None

    def index_for_item(self, target: DiskItem) -> QModelIndex:
        if not self.root:
            return QModelIndex()
        if target is self.root:
            return self.index(0, 0, QModelIndex())
        parent = target.parent
        if not parent:
            return QModelIndex()
        row = parent.children.index(target)
        parent_index = self.index_for_item(parent)
        return self.index(row, 0, parent_index)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        if not parent.isValid():
            return 1 if self.root else 0
        item = self.item_from_index(parent)
        if item is None:
            return 0
        return len(item.children)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return len(COLUMNS)

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:  # type: ignore[override]
        if not parent.isValid():
            if self.root and row == 0:
                return self.createIndex(row, column, self.root)
            return QModelIndex()
        parent_item = self.item_from_index(parent)
        if parent_item and 0 <= row < len(parent_item.children):
            return self.createIndex(row, column, parent_item.children[row])
        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:  # type: ignore[override]
        if not index.isValid():
            return QModelIndex()
        item: DiskItem = index.internalPointer()
        if item is self.root:
            return QModelIndex()
        parent_item = item.parent
        if not parent_item:
            return QModelIndex()
        if parent_item is self.root:
            return self.index(0, 0, QModelIndex())
        grand = parent_item.parent
        if not grand:
            return QModelIndex()
        return self.createIndex(grand.children.index(parent_item), 0, parent_item)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None
        item: DiskItem = index.internalPointer()
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return [
                item.name,
                item.formatted_size,
                item.formatted_percent,
                item.display_type,
                item.formatted_modified,
                item.absolute_path,
            ][col]
        if role == Qt.ItemDataRole.UserRole:
            return item
        if role == Qt.ItemDataRole.UserRole + 1:
            return item.size
        if role == Qt.ItemDataRole.UserRole + 2:
            return item.modified or 0
        if role == Qt.ItemDataRole.DecorationRole and col == 0:
            return self._folder_icon if item.is_folder else self._file_icon
        if role == Qt.ItemDataRole.ForegroundRole and item.error:
            return QColor("#ff9a9a")
        if role == Qt.ItemDataRole.ToolTipRole:
            return item.absolute_path if not item.error else f"{item.absolute_path}\n{item.error}"
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):  # type: ignore[override]
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section]
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:  # type: ignore[override]
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
