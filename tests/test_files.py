"""Tests for writing, downloading and extracting files."""

import zipfile

import pytest

from vizz_geopipe.errors import SourceError
from vizz_geopipe.sources._files import atomic_write
from vizz_geopipe.sources._files import download_file
from vizz_geopipe.sources._files import extract_zips


def test_atomic_write_creates_the_file(tmp_path):
    with atomic_write(tmp_path / "a" / "out.txt") as file:
        file.write(b"done")

    assert (tmp_path / "a" / "out.txt").read_bytes() == b"done"


def test_atomic_write_leaves_nothing_when_writing_fails(tmp_path):
    with pytest.raises(OSError), atomic_write(tmp_path / "out.txt") as file:
        file.write(b"half")
        raise OSError("disk full")

    assert list(tmp_path.iterdir()) == []


def test_download_file_writes_the_body(tmp_path, fake_web):
    fake_web.pages["https://example.com/a.csv"] = b"x,y"

    path = download_file("https://example.com/a.csv", tmp_path / "a.csv")

    assert path.read_bytes() == b"x,y"


def test_http_error_raises_source_error(tmp_path, fake_web):
    with pytest.raises(SourceError) as caught:
        download_file("https://example.com/missing.zip", tmp_path / "a.zip")

    assert caught.value.source == "https://example.com/missing.zip"
    assert not (tmp_path / "a.zip").exists()


def test_zips_nested_one_level_are_extracted(tmp_path):
    inner = tmp_path / "inner.zip"
    with zipfile.ZipFile(inner, "w") as archive:
        archive.writestr("b.txt", "b")
    outer = tmp_path / "outer.zip"
    with zipfile.ZipFile(outer, "w") as archive:
        archive.writestr("a.txt", "a")
        archive.write(inner, "inner.zip")
    inner.unlink()
    dest = tmp_path / "out"

    extract_zips(outer, dest)

    found = sorted(path.relative_to(dest).as_posix() for path in dest.rglob("*"))
    assert found == ["a.txt", "inner", "inner/b.txt"]
    assert not outer.exists()
