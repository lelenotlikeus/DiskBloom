from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ...core.formatting import format_size
from ..theme import ThemeManager


class ReclaimMeter(QWidget):
    """A compact, stable speedometer-style reclaim animation."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(205)
        self.setMaximumHeight(230)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._mode = "idle"
        self._frame = 0
        self._needle = 0.08
        self._target_needle = 0.08
        self._speed = 0.0
        self._target_speed = 0.0
        self._reclaimed = 0
        self._files = 0
        self._note = "Ready to reclaim space"
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._mode = "running"
        self._frame = 0
        self._needle = 0.08
        self._target_needle = 0.72
        self._speed = 0
        self._target_speed = 420 * 1024 * 1024
        self._reclaimed = 0
        self._files = 0
        self._note = "Reclaiming"
        self._timer.start(16)
        self.update()

    def finish(self, reclaimed: int, speed: float, files: int, permanent: bool = False) -> None:
        self._mode = "settling"
        self._frame = 0
        self._reclaimed = reclaimed
        self._files = files
        self._target_speed = max(speed, 1)
        self._target_needle = self._needle_for_speed(self._target_speed)
        self._note = "Permanently deleted" if permanent else "Moved to Trash"
        if not self._timer.isActive():
            self._timer.start(16)
        self.update()

    def fail(self, message: str) -> None:
        self._mode = "failed"
        self._timer.stop()
        self._note = message
        self.update()

    def _tick(self) -> None:
        self._frame += 1
        if self._mode == "running":
            progress = self._ease_out_cubic(min(1.0, self._frame / 95))
            drift = math.sin(self._frame * 0.055) * 0.018
            desired = 0.12 + progress * 0.68 + drift
            self._needle += (desired - self._needle) * 0.08
            self._speed += (self._target_speed * (0.22 + progress * 0.78) - self._speed) * 0.06
        elif self._mode == "settling":
            progress = min(1.0, self._frame / 120)
            desired = self._target_needle
            if self._frame < 42:
                desired += math.sin((self._frame / 42) * math.pi) * 0.045
            self._needle += (desired - self._needle) * 0.075
            self._speed += (self._target_speed - self._speed) * 0.065
            if progress >= 1:
                self._mode = "complete"
                self._needle = self._target_needle
                self._speed = self._target_speed
                self._frame = 0
        elif self._mode == "complete":
            self._frame += 1
            if self._frame > 130:
                self._timer.stop()
        self.update()

    def _needle_for_speed(self, speed: float) -> float:
        mbps = max(speed / (1024 * 1024), 1)
        return min(0.92, max(0.14, math.log10(mbps + 1) / math.log10(2400)))

    def _ease_out_cubic(self, value: float) -> float:
        return 1 - pow(1 - value, 3)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = ThemeManager.tokens()

        bounds = QRectF(self.rect()).adjusted(12, 10, -12, -10)
        painter.setPen(QColor(c.text))
        title_font = QFont(ThemeManager.font_family())
        title_font.setPointSize(10)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(bounds.adjusted(2, 0, -2, 0), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, "Reclaim Meter")

        gauge_side = min(bounds.width() - 20, 142)
        gauge = QRectF(0, 0, gauge_side, gauge_side)
        gauge.moveCenter(QPointF(bounds.center().x(), bounds.top() + 84))
        self._draw_gauge(painter, gauge)
        self._draw_readout(painter, bounds, gauge)

    def _draw_gauge(self, painter: QPainter, gauge: QRectF) -> None:
        start_angle = 220
        span_angle = -260
        center = gauge.center()
        radius = gauge.width() / 2 - 11
        progress = max(0.04, min(1.0, self._needle))

        shadow_pen = QPen(QColor(0, 0, 0, 85), 18)
        shadow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(shadow_pen)
        painter.drawArc(gauge.adjusted(1, 3, 1, 3), start_angle * 16, span_angle * 16)

        c = ThemeManager.tokens()
        base_pen = QPen(QColor(c.border_strong), 13)
        base_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(base_pen)
        painter.drawArc(gauge, start_angle * 16, span_angle * 16)

        gradient = QLinearGradient(gauge.left(), gauge.center().y(), gauge.right(), gauge.center().y())
        gradient.setColorAt(0.0, QColor(c.accent))
        gradient.setColorAt(0.62, QColor(c.accent_2))
        gradient.setColorAt(1.0, QColor("#ffcf5a" if c.name == "dark" else c.accent))
        glow_alpha = (28 if self._mode != "complete" else 64) if c.name == "dark" else 16
        glow_pen = QPen(QColor(85, 240, 194, glow_alpha), 19)
        glow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(glow_pen)
        painter.drawArc(gauge, start_angle * 16, int(span_angle * progress * 16))

        arc_pen = QPen(gradient, 11)
        arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(arc_pen)
        painter.drawArc(gauge, start_angle * 16, int(span_angle * progress * 16))

        for i in range(13):
            fraction = i / 12
            angle = math.radians(start_angle + span_angle * fraction)
            tick_outer = QPointF(center.x() + math.cos(angle) * radius, center.y() - math.sin(angle) * radius)
            tick_len = 11 if i % 3 == 0 else 7
            tick_inner = QPointF(center.x() + math.cos(angle) * (radius - tick_len), center.y() - math.sin(angle) * (radius - tick_len))
            painter.setPen(QPen(QColor(c.subtle), 1.8 if i % 3 == 0 else 1.1))
            painter.drawLine(tick_inner, tick_outer)

        needle_angle = math.radians(start_angle + span_angle * progress)
        needle_end = QPointF(center.x() + math.cos(needle_angle) * (radius - 19), center.y() - math.sin(needle_angle) * (radius - 19))
        painter.setPen(QPen(QColor(c.text), 3.5))
        painter.drawLine(center, needle_end)
        painter.setBrush(QColor(c.accent) if self._mode != "complete" else QColor("#ffcf5a" if c.name == "dark" else c.accent))
        painter.setPen(QPen(QColor(c.bg), 2.5))
        painter.drawEllipse(center, 7, 7)

    def _draw_readout(self, painter: QPainter, bounds: QRectF, gauge: QRectF) -> None:
        speed_rect = QRectF(bounds.left(), gauge.bottom() - 3, bounds.width(), 40)
        c = ThemeManager.tokens()
        painter.setPen(QColor(c.text))
        speed_font = QFont(ThemeManager.font_family())
        speed_font.setPointSize(15)
        speed_font.setBold(True)
        painter.setFont(speed_font)
        painter.drawText(speed_rect, Qt.AlignmentFlag.AlignCenter, f"{format_size(self._speed)}/s")

        painter.setPen(QColor(c.muted))
        note_font = QFont(ThemeManager.font_family())
        note_font.setPointSize(8)
        painter.setFont(note_font)
        painter.drawText(QRectF(bounds.left(), speed_rect.bottom() - 2, bounds.width(), 22), Qt.AlignmentFlag.AlignCenter, self._note)

        metric_top = speed_rect.bottom() + 24
        left_metric = QRectF(bounds.left(), metric_top, bounds.width() / 2 - 5, 42)
        right_metric = QRectF(bounds.center().x() + 5, metric_top, bounds.width() / 2 - 5, 42)
        self._metric(painter, left_metric, format_size(self._reclaimed), "reclaimed")
        self._metric(painter, right_metric, f"{self._files}", "files")

    def _metric(self, painter: QPainter, rect: QRectF, value: str, label: str) -> None:
        c = ThemeManager.tokens()
        painter.setPen(QColor(c.text))
        value_font = QFont(ThemeManager.font_family())
        value_font.setPointSize(10)
        value_font.setBold(True)
        painter.setFont(value_font)
        painter.drawText(rect.adjusted(0, 0, 0, -16), Qt.AlignmentFlag.AlignCenter, value)
        painter.setPen(QColor(c.subtle))
        label_font = QFont(ThemeManager.font_family())
        label_font.setPointSize(8)
        painter.setFont(label_font)
        painter.drawText(rect.adjusted(0, 18, 0, 0), Qt.AlignmentFlag.AlignCenter, label)
