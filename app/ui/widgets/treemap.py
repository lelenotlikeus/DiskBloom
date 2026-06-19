from __future__ import annotations

from PySide6.QtCore import QRect, Signal, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from ...core.formatting import format_size
from ...core.models import DiskItem
from ..theme import ThemeManager


class TreemapWidget(QWidget):
    itemClicked = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(110)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        self._root: DiskItem | None = None
        self._rects: list[tuple[object, DiskItem]] = []
        self.setMouseTracking(True)

    def set_root(self, root: DiskItem | None) -> None:
        self._root = root
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = ThemeManager.tokens()
        painter.fillRect(self.rect(), QColor(c.input_bg))
        self._rects.clear()
        if not self._root or self._root.size <= 0:
            painter.setPen(QColor(c.muted))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Scan a folder to build treemap")
            return
        children = [child for child in self._root.children if child.size > 0][:28]
        total = sum(child.size for child in children) or 1
        x = 8
        y = 8
        w = self.width() - 16
        h = self.height() - 16
        horizontal = w >= h
        palette = [c.accent, c.accent_2, "#f4c95d", "#8fb3ff", "#d98293", "#7ecf91", "#a8b4ff"]
        for index, child in enumerate(children):
            fraction = child.size / total
            if horizontal:
                rect_w = max(8, int(w * fraction))
                rect = QRect(x, y, rect_w - 4, h)
                x += rect_w
            else:
                rect_h = max(8, int(h * fraction))
                rect = QRect(x, y, w, rect_h - 4)
                y += rect_h
            color = QColor(palette[index % len(palette)])
            color.setAlpha(200)
            painter.fillRect(rect, color)
            painter.setPen(QColor(c.bg))
            painter.drawRect(rect)
            if rect.width() > 76 and rect.height() > 34:
                painter.setPen(QColor(c.bg))
                painter.drawText(rect.adjusted(6, 4, -6, -4), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, f"{child.name}\n{format_size(child.size)}")
            self._rects.append((rect, child))

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        for rect, item in self._rects:
            if rect.contains(event.pos()):
                self.itemClicked.emit(item)
                return
