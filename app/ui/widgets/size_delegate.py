from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem

from ..theme import ThemeManager


class SizeBarDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:  # type: ignore[override]
        item = index.data(Qt.ItemDataRole.UserRole)
        if item is not None and index.column() == 1:
            painter.save()
            super().paint(painter, option, index)
            percent = max(0.0, min(1.0, item.percentage_of_parent / 100.0))
            rect = option.rect.adjusted(10, option.rect.height() - 8, -10, -4)
            fill = rect
            fill.setWidth(max(2, int(rect.width() * percent)))
            tokens = ThemeManager.tokens()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(tokens.border))
            painter.drawRoundedRect(rect, 3, 3)
            gradient = QLinearGradient(fill.left(), fill.center().y(), fill.right(), fill.center().y())
            gradient.setColorAt(0.0, QColor(tokens.accent))
            gradient.setColorAt(1.0, QColor(tokens.accent_2))
            painter.setBrush(gradient)
            painter.drawRoundedRect(fill, 3, 3)
            painter.restore()
            return
        super().paint(painter, option, index)
