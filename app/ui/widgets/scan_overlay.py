from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from ...core.formatting import format_size
from ..theme import ThemeManager


class ScanOverlay(QWidget):
    """Stable center-state shown while the filesystem scanner is running."""

    def __init__(self) -> None:
        super().__init__()
        self._phase = 0.0
        self._display_progress = 0.02
        self._target_progress = 0.02
        self._files = 0
        self._folders = 0
        self._size = 0
        self._current_path = ""
        self._state = "idle"
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def start(self, path: Path) -> None:
        self._phase = 0.0
        self._display_progress = 0.02
        self._target_progress = 0.06
        self._files = 0
        self._folders = 0
        self._size = 0
        self._current_path = str(path)
        self._state = "running"
        self._timer.start(16)
        self.update()

    def set_progress(self, current_path: Path, files: int, folders: int, size: int) -> None:
        self._current_path = str(current_path)
        self._files = files
        self._folders = folders
        self._size = size
        discovered = max(files + folders, 1)
        estimated = min(0.94, 0.08 + math.log10(discovered + 1) * 0.22)
        self._target_progress = max(self._target_progress, estimated)
        self.update()

    def finish(self) -> None:
        self._state = "complete"
        self._target_progress = 1.0
        self.update()

    def fail(self, message: str) -> None:
        self._state = "failed"
        self._current_path = message
        self._timer.stop()
        self.update()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.0065) % 1.0
        if self._state == "running" and self._target_progress < 0.90:
            self._target_progress += 0.0008
        self._display_progress += (self._target_progress - self._display_progress) * 0.055
        if self._state == "complete" and self._display_progress > 0.995:
            self._display_progress = 1.0
            self._timer.stop()
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            bounds = QRectF(self.rect()).adjusted(34, 30, -34, -30)
            content_width = min(bounds.width(), 560)
            panel = QRectF(0, 0, content_width, min(bounds.height(), 360))
            panel.moveCenter(bounds.center())

            self._draw_panel(painter, panel)
            self._draw_orbit(painter, QRectF(panel.center().x() - 58, panel.top() + 34, 116, 116))
            self._draw_text(painter, panel)
            self._draw_progress(painter, QRectF(panel.left() + 56, panel.top() + 202, panel.width() - 112, 12))
            self._draw_metrics(painter, QRectF(panel.left() + 34, panel.top() + 236, panel.width() - 68, 76))
        finally:
            painter.end()

    def _draw_panel(self, painter: QPainter, panel: QRectF) -> None:
        path = QPainterPath()
        path.addRoundedRect(panel, 10, 10)
        c = ThemeManager.tokens()
        panel_color = QColor(c.surface)
        panel_color.setAlpha(238 if c.name == "dark" else 248)
        painter.fillPath(path, panel_color)
        painter.setPen(QPen(QColor(c.border), 1))
        painter.drawPath(path)

    def _draw_orbit(self, painter: QPainter, ring: QRectF) -> None:
        start_angle = 90 - self._phase * 360
        c = ThemeManager.tokens()
        base_pen = QPen(QColor(c.border_strong), 7)
        base_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(base_pen)
        painter.drawArc(ring, 0, 360 * 16)

        glow_alpha = (52 if self._state == "complete" else 32) if c.name == "dark" else 14
        glow_pen = QPen(QColor(85, 240, 194, glow_alpha), 12)
        glow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(glow_pen)
        painter.drawArc(ring.adjusted(1, 1, -1, -1), int(start_angle * 16), -118 * 16)

        gradient = QLinearGradient(ring.left(), ring.top(), ring.right(), ring.bottom())
        gradient.setColorAt(0.0, QColor(c.accent))
        gradient.setColorAt(1.0, QColor(c.accent_2))
        arc_pen = QPen(gradient, 6)
        arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(arc_pen)
        painter.drawArc(ring, int(start_angle * 16), -118 * 16)

        inner = ring.adjusted(27, 27, -27, -27)
        painter.setPen(QPen(QColor(c.border_strong), 2))
        painter.drawEllipse(inner)
        painter.setPen(QPen(QColor(c.muted), 1))
        center = ring.center()
        for i in range(8):
            angle = math.radians(i * 45 + self._phase * 18)
            x = center.x() + math.cos(angle) * 25
            y = center.y() + math.sin(angle) * 25
            painter.drawPoint(int(x), int(y))

    def _draw_text(self, painter: QPainter, panel: QRectF) -> None:
        title = "Scan complete" if self._state == "complete" else "Scanning disk"
        if self._state == "failed":
            title = "Scan failed"

        c = ThemeManager.tokens()
        painter.setPen(QColor(c.text))
        title_font = QFont(ThemeManager.font_family())
        title_font.setPointSize(20)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(QRectF(panel.left(), panel.top() + 154, panel.width(), 34), Qt.AlignmentFlag.AlignCenter, title)

        painter.setPen(QColor(c.muted))
        path_font = QFont(ThemeManager.font_family())
        path_font.setPointSize(9)
        painter.setFont(path_font)
        painter.drawText(
            QRectF(panel.left() + 40, panel.top() + 184, panel.width() - 80, 22),
            Qt.AlignmentFlag.AlignCenter,
            self._short_path(self._current_path),
        )

    def _draw_progress(self, painter: QPainter, rect: QRectF) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        c = ThemeManager.tokens()
        painter.setBrush(QColor(c.border))
        painter.drawRoundedRect(rect, 6, 6)

        fill = QRectF(rect)
        fill.setWidth(max(8, rect.width() * self._display_progress))
        gradient = QLinearGradient(fill.left(), fill.center().y(), fill.right(), fill.center().y())
        gradient.setColorAt(0.0, QColor(c.accent))
        gradient.setColorAt(1.0, QColor(c.accent_2))
        painter.setBrush(gradient)
        painter.drawRoundedRect(fill, 6, 6)

        if self._state == "running":
            shimmer_x = rect.left() + ((self._phase * 1.4) % 1.0) * rect.width()
            shimmer = QRectF(shimmer_x - 42, rect.top(), 42, rect.height())
            painter.setBrush(QColor(255, 255, 255, 42 if c.name == "dark" else 80))
            painter.drawRoundedRect(shimmer.intersected(rect), 6, 6)

    def _draw_metrics(self, painter: QPainter, rect: QRectF) -> None:
        gap = 10
        card_width = (rect.width() - gap * 2) / 3
        cards = [
            (QRectF(rect.left(), rect.top(), card_width, rect.height()), f"{self._files:,}", "files"),
            (QRectF(rect.left() + card_width + gap, rect.top(), card_width, rect.height()), f"{self._folders:,}", "folders"),
            (QRectF(rect.left() + (card_width + gap) * 2, rect.top(), card_width, rect.height()), format_size(self._size), "found"),
        ]
        for card, value, label in cards:
            c = ThemeManager.tokens()
            painter.setPen(QPen(QColor(c.border), 1))
            painter.setBrush(QColor(c.elevated))
            painter.drawRoundedRect(card, 8, 8)
            painter.setPen(QColor(c.text))
            value_font = QFont(ThemeManager.font_family())
            value_font.setPointSize(12)
            value_font.setBold(True)
            painter.setFont(value_font)
            painter.drawText(card.adjusted(6, 8, -6, -28), Qt.AlignmentFlag.AlignCenter, value)
            painter.setPen(QColor(c.muted))
            label_font = QFont(ThemeManager.font_family())
            label_font.setPointSize(8)
            painter.setFont(label_font)
            painter.drawText(card.adjusted(6, 42, -6, -8), Qt.AlignmentFlag.AlignCenter, label)

    def _short_path(self, path: str) -> str:
        if not path:
            return "Preparing folder scan..."
        if len(path) <= 72:
            return path
        return "..." + path[-69:]
