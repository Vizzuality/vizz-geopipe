"""Tests for sources that are files on this computer."""

import pytest

from vizz_geopipe.errors import SourceError
from vizz_geopipe.sources import LocalSource


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "a.gpkg").write_bytes(b"a")
    return tmp_path


def test_files_are_returned_where_they_are(project):
    paths = LocalSource(files=("data/*.gpkg",)).fetch(project / "raw")

    assert paths == [project / "data" / "a.gpkg"]
    assert not (project / "raw").exists()


def test_pattern_matching_nothing_raises_source_error(project):
    with pytest.raises(SourceError, match=r"\*\.tif"):
        LocalSource(files=("data/*.tif",)).fetch(project / "raw")


def test_identity_is_each_file_with_its_size_and_time(project):
    path = project / "data" / "a.gpkg"
    stat = path.stat()

    identity = LocalSource(files=("data/a.gpkg",)).identity()

    assert identity == {str(path): f"{stat.st_size}:{stat.st_mtime_ns}"}


def test_absolute_patterns_are_read(project):
    pattern = str(project / "data" / "*.gpkg")

    paths = LocalSource(files=(pattern,)).fetch(project / "raw")

    assert paths == [project / "data" / "a.gpkg"]
