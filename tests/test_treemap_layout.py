from dataclasses import dataclass

from app.core.treemap_layout import squarify


@dataclass(slots=True)
class Item:
    name: str
    size: int


def test_squarify_keeps_rectangles_inside_bounds() -> None:
    rects = squarify([Item("a", 60), Item("b", 30), Item("c", 10)], 0, 0, 100, 80)
    assert len(rects) == 3
    for rect in rects:
        assert rect.x >= 0
        assert rect.y >= 0
        assert rect.x + rect.width <= 100.0001
        assert rect.y + rect.height <= 80.0001


def test_squarify_area_is_proportional() -> None:
    rects = squarify([Item("large", 75), Item("small", 25)], 0, 0, 100, 100)
    areas = {rect.item.name: rect.area for rect in rects}
    assert areas["large"] > areas["small"]
    assert round(areas["large"] / areas["small"]) == 3


def test_squarify_creates_mosaic_not_full_width_bars() -> None:
    items = [Item(f"item-{index}", 10) for index in range(12)]
    rects = squarify(items, 0, 0, 400, 220)

    assert len(rects) == len(items)
    full_width_bars = [rect for rect in rects if rect.width > 390]
    assert len(full_width_bars) < 3
    assert len({round(rect.x, 1) for rect in rects}) > 1
    assert len({round(rect.y, 1) for rect in rects}) > 1


def test_squarify_avoids_extreme_strips_for_even_items() -> None:
    items = [Item(f"item-{index}", 1) for index in range(16)]
    rects = squarify(items, 0, 0, 320, 320)

    worst_ratio = max(max(rect.width / rect.height, rect.height / rect.width) for rect in rects)
    assert worst_ratio <= 2.5
