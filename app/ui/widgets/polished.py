from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...core.formatting import format_size
from ...core.models import DiskItem


class MetricCard(QFrame):
    def __init__(self, label: str, icon: str = "") -> None:
        super().__init__()
        self.setObjectName("metricCard")
        self.setMinimumHeight(68)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        self.icon_label = QLabel()
        self.icon_label.setObjectName("metricIcon")
        self.icon_label.setFixedSize(26, 26)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if icon.endswith(".svg"):
            self.icon_label.setPixmap(QIcon(icon).pixmap(18, 18))
        else:
            self.icon_label.setText(icon)
        layout.addWidget(self.icon_label)

        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        self.value_label = QLabel("-")
        self.value_label.setObjectName("metricValue")
        self.value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.label_label = QLabel(label)
        self.label_label.setObjectName("metricLabel")
        text_box.addWidget(self.value_label)
        text_box.addWidget(self.label_label)
        layout.addLayout(text_box, 1)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)
        self.value_label.setToolTip(value)


class EmptyState(QWidget):
    def __init__(self, title: str, body: str, action_text: str = "") -> None:
        super().__init__()
        self.setObjectName("emptyState")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(8)

        mark = QLabel("DiskBloom")
        mark.setObjectName("emptyMark")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label = QLabel(title)
        title_label.setObjectName("emptyTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body_label = QLabel(body)
        body_label.setObjectName("emptyBody")
        body_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body_label.setWordWrap(True)
        body_label.setMaximumWidth(520)
        self.action_button = QPushButton(action_text)
        self.action_button.setObjectName("primary")
        self.action_button.setVisible(bool(action_text))
        layout.addStretch()
        layout.addWidget(mark)
        layout.addWidget(title_label)
        layout.addWidget(body_label)
        layout.addWidget(self.action_button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()


class FileTypeBreakdown(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("breakdownPanel")
        self._rows: dict[str, tuple[QLabel, QProgressBar, QLabel]] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(7)
        for category in (
            "videos",
            "images",
            "archives",
            "documents",
            "code",
            "executables/apps",
            "audio",
            "other",
        ):
            row = QWidget()
            row_layout = QGridLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setHorizontalSpacing(8)
            row_layout.setVerticalSpacing(2)
            label = QLabel(category)
            label.setObjectName("breakdownLabel")
            value = QLabel("-")
            value.setObjectName("breakdownValue")
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setFixedHeight(7)
            row_layout.addWidget(label, 0, 0)
            row_layout.addWidget(value, 0, 1)
            row_layout.addWidget(bar, 1, 0, 1, 2)
            layout.addWidget(row)
            self._rows[category] = (label, bar, value)

    def set_totals(self, totals: dict[str, int]) -> None:
        total = max(sum(totals.values()), 1)
        for category, (_, bar, value) in self._rows.items():
            size = totals.get(category, 0)
            percent = size / total
            bar.setValue(int(percent * 1000))
            value.setText(f"{format_size(size)}  {percent * 100:.1f}%")


class AnalysisList(QListWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("analysisList")
        self.setSpacing(6)
        self.setUniformItemSizes(False)

    def set_items(self, items: Iterable[DiskItem], show_modified: bool = False) -> None:
        self.clear()
        for item in items:
            subtitle = item.absolute_path
            if show_modified:
                subtitle = f"{item.formatted_modified}  |  {item.absolute_path}"
            row = QListWidgetItem(f"{item.name}\n{item.formatted_size}  |  {subtitle}")
            row.setToolTip(item.absolute_path)
            row.setData(Qt.ItemDataRole.UserRole, item)
            row.setSizeHint(row.sizeHint().expandedTo(QSize(260, 52)))
            self.addItem(row)
