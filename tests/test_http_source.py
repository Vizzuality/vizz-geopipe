"""Tests for downloading sources over HTTP, and the download cache."""

import io
import logging
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


def test_corrupt_record_downloads_again(tmp_path, places):
    source = HttpSource(url=URL, files=("*.shp",))
    source.fetch(tmp_path)
    (tmp_path / ".source.json").write_text('{"ident')

    assert source.fetch(tmp_path) == [tmp_path / "places.shp"]
    assert places.requested == [URL, URL]


def test_a_download_that_is_not_a_zip_needs_a_file_name(tmp_path, fake_web):
    fake_web.pages[URL] = b"x,y"

    with pytest.raises(SourceError, match="file name"):
        HttpSource(url=URL, files=("*.csv",)).fetch(tmp_path)


def test_a_download_that_is_not_a_zip_can_go_in_a_folder(tmp_path, fake_web):
    fake_web.pages[URL] = b"x,y"

    paths = HttpSource(url=URL, files=("data/a.csv",)).fetch(tmp_path)

    assert paths == [tmp_path / "data" / "a.csv"]


def test_a_broken_nested_zip_raises_source_error(tmp_path, fake_web):
    fake_web.pages[URL] = zip_bytes({"inner.zip": b"PK not really a zip"})

    with pytest.raises(SourceError, match="inner.zip"):
        HttpSource(url=URL, files=("*",)).fetch(tmp_path)


def test_fetch_logs_a_download_and_then_the_cache(tmp_path, places, caplog):
    caplog.set_level(logging.DEBUG, logger="vizz_geopipe")
    source = HttpSource(url=URL, files=("*.shp",))

    source.fetch(tmp_path)
    downloading = [record.levelname for record in caplog.records]
    caplog.clear()
    source.fetch(tmp_path)

    assert downloading == ["INFO"]
    assert [record.levelname for record in caplog.records] == ["DEBUG"]


def test_fetch_logs_never_show_the_url(tmp_path, places, caplog):
    caplog.set_level(logging.DEBUG, logger="vizz_geopipe")

    HttpSource(url=URL, files=("*.shp",)).fetch(tmp_path)

    assert "example.com" not in caplog.text
