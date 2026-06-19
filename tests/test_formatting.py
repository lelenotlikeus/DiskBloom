from app.core.formatting import format_size


def test_format_size_bytes() -> None:
    assert format_size(0) == "0 B"
    assert format_size(512) == "512 B"


def test_format_size_large_units() -> None:
    assert format_size(1024) == "1.0 KB"
    assert format_size(1024**2 * 2.5) == "2.5 MB"
