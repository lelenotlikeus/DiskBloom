from time import time

from app.core.filters import FilterCriteria, item_matches, parse_size
from app.core.models import DiskItem


def test_parse_size() -> None:
    assert parse_size("100 MB") == 100 * 1024**2
    assert parse_size("1.5GB") == int(1.5 * 1024**3)


def test_item_matches_filters() -> None:
    item = DiskItem("movie.mkv", path=__import__("pathlib").Path("movie.mkv"), item_type="file", size=200 * 1024**2, extension=".mkv", modified=time() - 400 * 86400)
    assert item_matches(item, FilterCriteria(search="movie", extension=".mkv", min_size=100 * 1024**2, only_files=True))
    assert not item_matches(item, FilterCriteria(extension=".zip"))
    assert item_matches(item, FilterCriteria(older_than_days=365))
