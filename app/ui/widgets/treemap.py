from __future__ import annotations

import os
import platform
import subprocess
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QRectF, Signal, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from ...core.formatting import format_size
from ...core.models import DiskItem
from ...core.treemap_layout import LayoutRect, squarify
from ..theme import ThemeManager


@dataclass(slots=True)
class PaintedRect:
    rect: QRectF
    item: DiskItem | None
    depth: int
    label: str = ""
    grouped_size: int = 0


class TreemapWidget(QWidget):
    itemClicked = Signal(object)
    itemDoubleClicked = Signal(object)
    zoomChanged = Signal(object)

    MAX_DEPTH = 4
    MAX_CHILDREN_PER_LEVEL = 120
    MIN_VISIBLE_AREA = 26.0
    FOLDER_RECURSE_AREA = 7600.0

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(190)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self._scan_root: DiskItem | None = None
        self._view_root: DiskItem | None = None
        self._selected: DiskItem | None = None
        self._hovered: PaintedRect | None = None
        self._painted: list[PaintedRect] = []

    def set_root(self, root: DiskItem | None) -> None:
        self._scan_root = root
        self._view_root = root
        self._selected = None
        self._hovered = None
        self.zoomChanged.emit(self._view_root)
        self.update()

    def current_root(self) -> DiskItem | None:
        return self._view_root

    def set_selected_item(self, item: DiskItem | None) -> None:
        self._selected = item
        self.update()

    def can_go_back(self) -> bool:
        return bool(self._view_root and self._scan_root and self._view_root is not self._scan_root and self._view_root.parent)

    def go_back(self) -> None:
        if self.can_go_back() and self._view_root:
            self._view_root = self._view_root.parent
            self.zoomChanged.emit(self._view_root)
            self.update()

    def zoom_to(self, item: DiskItem) -> None:
        if item.is_folder and item.children:
            self._view_root = item
            self.zoomChanged.emit(item)
            self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            c = ThemeManager.tokens()
            painter.fillRect(self.rect(), QColor(c.input_bg))
            self._painted.clear()

            if not self._view_root or self._view_root.size <= 0:
                painter.setPen(QColor(c.muted))
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Scan a folder to build the treemap")
                return

            bounds = QRectF(self.rect()).adjusted(8, 8, -8, -8)
            self._draw_items(painter, self._view_root, bounds, 0)
        finally:
            painter.end()

    def _draw_items(self, painter: QPainter, root: DiskItem, bounds: QRectF, depth: int) -> None:
        if bounds.width() <= 3 or bounds.height() <= 3 or depth > self.MAX_DEPTH:
            return
        children, other_size = self._visible_children(root, bounds)
        layout_items: list[DiskItem | _OtherItem] = children[:]
        if other_size > 0:
            layout_items.append(_OtherItem(other_size))
        for layout in squarify(layout_items, bounds.x(), bounds.y(), bounds.width(), bounds.height()):
            gap = 2.0 if depth <= 1 else 1.4
            rect = QRectF(layout.x, layout.y, layout.width, layout.height).adjusted(gap, gap, -gap, -gap)
            if rect.width() < 1 or rect.height() < 1:
                continue
            item = layout.item if isinstance(layout.item, DiskItem) else None
            grouped_size = getattr(layout.item, "size", 0) if item is None else 0
            painted = PaintedRect(rect, item, depth, "Other" if item is None else item.name, grouped_size)
            self._painted.append(painted)
            can_recurse = (
                bool(item and item.is_folder and item.children)
                and rect.width() * rect.height() > self.FOLDER_RECURSE_AREA
                and depth < self.MAX_DEPTH
                and rect.width() > 42
                and rect.height() > 34
            )
            self._draw_rect(painter, painted, as_container=can_recurse)
            if item and can_recurse:
                label_height = 18 if rect.height() > 48 and rect.width() > 80 else 0
                inner = rect.adjusted(4, 4 + label_height, -4, -4)
                self._draw_items(painter, item, inner, depth + 1)

    def _visible_children(self, root: DiskItem, bounds: QRectF) -> tuple[list[DiskItem], int]:
        children = [child for child in root.children if child.size > 0]
        children.sort(key=lambda item: item.size, reverse=True)
        area = max(1.0, bounds.width() * bounds.height())
        visible: list[DiskItem] = []
        other_size = 0
        for child in children:
            child_area = area * (child.size / max(root.size, 1))
            if len(visible) < self.MAX_CHILDREN_PER_LEVEL and child_area >= self.MIN_VISIBLE_AREA:
                visible.append(child)
            else:
                other_size += child.size
        return visible, other_size

    def _draw_rect(self, painter: QPainter, painted: PaintedRect, *, as_container: bool = False) -> None:
        c = ThemeManager.tokens()
        color = self._color_for_item(painted.item)
        rect = painted.rect
        radius = 4 if rect.width() > 8 and rect.height() > 8 else 1

        if as_container:
            surface = QColor(c.surface)
            surface.setAlpha(105 if c.name == "dark" else 185)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(surface)
            painter.drawRoundedRect(rect, radius, radius)
        else:
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            gradient.setColorAt(0.0, color.lighter(116 if c.name == "dark" else 108))
            gradient.setColorAt(1.0, color.darker(118 if c.name == "dark" else 104))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(gradient)
            painter.drawRoundedRect(rect, radius, radius)

        border = QColor(c.accent if painted.item is self._selected else c.border)
        if painted is self._hovered:
            border = QColor(c.accent_2)
        width = 2.0 if painted.item is self._selected else 1.0
        if as_container and painted.item is not self._selected and painted is not self._hovered:
            border = QColor(c.border)
            border.setAlpha(150 if c.name == "dark" else 210)
        painter.setPen(QPen(border, width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)

        if rect.width() >= 76 and rect.height() >= 30:
            if as_container:
                painter.setPen(QColor(c.text))
            else:
                painter.setPen(QColor("#061018") if color.lightness() > 130 else QColor("#eef7fb"))
            font = QFont(ThemeManager.font_family())
            font.setPointSize(8 if rect.height() < 56 else 9)
            font.setBold(True)
            painter.setFont(font)
            size = painted.item.size if painted.item else painted.grouped_size
            if as_container:
                text = f"{painted.label}  {format_size(size)}"
                painter.drawText(
                    rect.adjusted(7, 3, -7, -4),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                    painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, int(rect.width() - 14)),
                )
            else:
                text = f"{painted.label}\n{format_size(size)}" if rect.height() >= 42 else painted.label
                painter.drawText(rect.adjusted(6, 4, -6, -4), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, text)

    def _color_for_item(self, item: DiskItem | None) -> QColor:
        c = ThemeManager.tokens()
        if item is None:
            return QColor(c.subtle)
        if item.is_folder:
            return QColor("#2f4655" if c.name == "dark" else "#d6e0e7")
        ext = item.extension.lower()
        if ext in {
            ".exe",
            ".dll",
            ".msi",
            ".app",
            ".dmg",
            ".pkg",
            ".deb",
            ".rpm",
            ".apk",
            ".bat",
            ".cmd",
            ".pak",
            ".vpk",
            ".wad",
            ".bundle",
        }:
            return QColor("#27b8d8")
        if ext in {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso"}:
            return QColor("#dca84a")
        if ext in {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".m4v"}:
            return QColor("#9377f2")
        if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".heic", ".svg"}:
            return QColor("#4fbd83")
        if ext in {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"}:
            return QColor("#44a7b7")
        if ext in {
            ".py",
            ".js",
            ".ts",
            ".html",
            ".css",
            ".json",
            ".xml",
            ".cpp",
            ".c",
            ".h",
            ".cs",
            ".java",
            ".md",
            ".txt",
            ".log",
            ".ini",
            ".yaml",
            ".yml",
        }:
            return QColor("#7d8792" if c.name == "dark" else "#98a4af")
        return QColor("#5f6f7c" if c.name == "dark" else "#b7c2ca")

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        hovered = self._rect_at(event.pos())
        if hovered is not self._hovered:
            self._hovered = hovered
            self.update()
        if hovered:
            QToolTip.showText(event.globalPosition().toPoint(), self._tooltip_for(hovered), self)
        else:
            QToolTip.hideText()

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self._hovered = None
        QToolTip.hideText()
        self.update()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() != Qt.MouseButton.LeftButton:
            return
        painted = self._rect_at(event.pos())
        if painted and painted.item:
            self._selected = painted.item
            self.itemClicked.emit(painted.item)
            self.update()

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        painted = self._rect_at(event.pos())
        if not painted or not painted.item:
            return
        item = painted.item
        if item.is_folder:
            self.zoom_to(item)
            self.itemDoubleClicked.emit(item)
        else:
            self._open_location(item)

    def _rect_at(self, pos: QPoint) -> PaintedRect | None:
        for painted in reversed(self._painted):
            if painted.rect.contains(pos):
                return painted
        return None

    def _tooltip_for(self, painted: PaintedRect) -> str:
        if not painted.item:
            return f"Other\nGrouped small items\nSize: {format_size(painted.grouped_size)}"
        item = painted.item
        return (
            f"{item.name}\n"
            f"{item.absolute_path}\n"
            f"Size: {item.formatted_size}\n"
            f"Type: {item.display_type}"
        )

    def _open_location(self, item: DiskItem) -> None:
        path = item.path
        target = path if path.is_dir() else path.parent
        try:
            if platform.system() == "Windows":
                os.startfile(target)  # type: ignore[attr-defined]
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", str(target)])
            else:
                subprocess.Popen(["xdg-open", str(target)])
        except Exception:
            pass


@dataclass(slots=True)
class _OtherItem:
    size: int
