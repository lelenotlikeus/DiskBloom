from app.core.file_types import classify_extension


def test_classify_known_extensions() -> None:
    assert classify_extension(".mp4") == "videos"
    assert classify_extension("photo.PNG") == "images"
    assert classify_extension("archive.zip") == "archives"
    assert classify_extension("script.py") == "code"


def test_classify_unknown_extension() -> None:
    assert classify_extension(".mystery") == "other"
