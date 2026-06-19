from __future__ import annotations

from datetime import datetime


def format_size(size: int | float) -> str:
    """Return a human readable binary size string."""
    value = float(max(size, 0))
    units = ("B", "KB", "MB", "GB", "TB", "PB")
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"


def format_percent(value: float) -> str:
    if value <= 0:
        return "0%"
    if value < 0.1:
        return "<0.1%"
    return f"{value:.1f}%"


def format_modified(timestamp: float | None) -> str:
    if not timestamp:
        return "-"
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
