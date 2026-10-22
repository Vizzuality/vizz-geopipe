"""Tests for downloading sources over HTTP, and the download cache."""

import io
import zipfile

import pytest

from vizz_geopipe.errors import SourceError
from vizz_geopipe.sources import HttpSource

URL = "https://example.com/places.zip"


def zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


@pytest.fixture
def places(fake_web):
    fake_web.pages[URL] = zip_bytes({"places.shp": b"shp", "places.dbf": b"dbf"})
    return fake_web


def test_files_matching_the_patterns_are_returned(tmp_path, places):
    paths = HttpSource(url=URL, files=("*.shp",)).fetch(tmp_path / "src")

    assert paths == [tmp_path / "src" / "places.shp"]


def test_second_fetch_uses_the_cache(tmp_path, places):
    source = HttpSource(url=URL, files=("*.shp",))

    source.fetch(tmp_path)
    source.fetch(tmp_path)

    assert places.requested == [URL]


def test_refresh_downloads_again(tmp_path, places):
    source = HttpSource(url=URL, files=("*.shp",))

    source.fetch(tmp_path)
    source.fetch(tmp_path, refresh=True)

    assert places.requested == [URL, URL]


def test_changed_url_downloads_again_without_old_files(tmp_path, places):
    other = "https://example.com/other.zip"
    places.pages[other] = zip_bytes({"other.shp": b"shp"})
    HttpSource(url=URL, files=("*.shp",)).fetch(tmp_path)

    paths = HttpSource(url=other, files=("*.shp",)).fetch(tmp_path)

    assert paths == [tmp_path / "other.shp"]


def test_failed_fetch_is_not_cached(tmp_path, fake_web):
    source = HttpSource(url=URL, files=("*.shp",))
    with pytest.raises(SourceError):
        source.fetch(tmp_path)
    fake_web.pages[URL] = zip_bytes({"places.shp": b"shp"})

    assert source.fetch(tmp_path) == [tmp_path / "places.shp"]


def test_pattern_matching_nothing_raises_source_error(tmp_path, places):
    with pytest.raises(SourceError, match=r"\*\.tif"):
        HttpSource(url=URL, files=("*.tif",)).fetch(tmp_path)


def test_a_download_that_is_not_a_zip_is_saved_as_the_first_file(tmp_path, fake_web):
    url = "https://example.com/data?format=csv"
    fake_web.pages[url] = b"x,y"

    paths = HttpSource(url=url, files=("data.csv",)).fetch(tmp_path)

    assert paths == [tmp_path / "data.csv"]
    assert paths[0].read_bytes() == b"x,y"
