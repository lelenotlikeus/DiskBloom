from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(slots=True)
class LayoutRect:
    item: Any
    x: float
    y: float
    width: float
    height: float
    depth: int = 0

    @property
    def area(self) -> float:
        return max(0.0, self.width) * max(0.0, self.height)


def squarify(items: Iterable[Any], x: float, y: float, width: float, height: float) -> list[LayoutRect]:
    weighted = [(item, float(getattr(item, "size", 0))) for item in items if getattr(item, "size", 0) > 0]
    weighted.sort(key=lambda pair: pair[1], reverse=True)
    total = sum(size for _, size in weighted)
    area = max(0.0, width) * max(0.0, height)
    if total <= 0 or area <= 0:
        return []

    normalized = [(item, size * area / total) for item, size in weighted]
    rects: list[LayoutRect] = []
    row: list[tuple[Any, float]] = []
    remaining = normalized[:]
    cur_x, cur_y, cur_w, cur_h = x, y, width, height

    while remaining:
        item = remaining[0]
        side = min(cur_w, cur_h)
        if not row or _worst(row + [item], side) <= _worst(row, side):
            row.append(item)
            remaining.pop(0)
            continue
        cur_x, cur_y, cur_w, cur_h = _layout_row(row, cur_x, cur_y, cur_w, cur_h, rects)
        row = []
    if row:
        _layout_row(row, cur_x, cur_y, cur_w, cur_h, rects)
    return rects


def _worst(row: list[tuple[Any, float]], side: float) -> float:
    if not row or side <= 0:
        return float("inf")
    sizes = [size for _, size in row]
    row_sum = sum(sizes)
    if row_sum <= 0:
        return float("inf")
    max_size = max(sizes)
    min_size = min(sizes)
    side_sq = side * side
    return max((side_sq * max_size) / (row_sum * row_sum), (row_sum * row_sum) / (side_sq * min_size))


def _layout_row(
    row: list[tuple[Any, float]],
    x: float,
    y: float,
    width: float,
    height: float,
    output: list[LayoutRect],
) -> tuple[float, float, float, float]:
    row_sum = sum(size for _, size in row)
    if row_sum <= 0 or width <= 0 or height <= 0:
        return x, y, width, height

    if width >= height:
        row_width = min(width, row_sum / height)
        cur_y = y
        bottom = y + height
        for index, (item, size) in enumerate(row):
            rect_height = bottom - cur_y if index == len(row) - 1 else size / row_width
            output.append(LayoutRect(item, x, cur_y, row_width, rect_height))
            cur_y += rect_height
        return x + row_width, y, max(0.0, width - row_width), height

    row_height = min(height, row_sum / width)
    cur_x = x
    right = x + width
    for index, (item, size) in enumerate(row):
        rect_width = right - cur_x if index == len(row) - 1 else size / row_height
        output.append(LayoutRect(item, cur_x, y, rect_width, row_height))
        cur_x += rect_width
    return x, y + row_height, width, max(0.0, height - row_height)
