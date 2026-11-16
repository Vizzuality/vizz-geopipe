"""Tests for build and publish fingerprints, and their records."""

from pathlib import Path

import pytest

from vizz_geopipe.fingerprint import BUILD_RECORD
from vizz_geopipe.fingerprint import PUBLISH_RECORD
from vizz_geopipe.fingerprint import build_fingerprint
from vizz_geopipe.fingerprint import read_build
from vizz_geopipe.fingerprint import read_published
from vizz_geopipe.fingerprint import write_build
from vizz_geopipe.fingerprint import write_published

SOURCES = [{"url": "https://example.com/a.zip"}]


def test_key_order_does_not_change_the_fingerprint():
    assert build_fingerprint({"a": 1, "b": 2}, SOURCES) == build_fingerprint(
        {"b": 2, "a": 1}, SOURCES
    )


def test_a_changed_value_changes_the_fingerprint():
    assert build_fingerprint({"max_zoom": 10}, SOURCES) != build_fingerprint(
        {"max_zoom": 11}, SOURCES
    )


def test_a_changed_source_changes_the_fingerprint():
    other = [{"url": "https://example.com/b.zip"}]

    assert build_fingerprint({}, SOURCES) != build_fingerprint({}, other)


def test_other_types_are_written_as_text():
    assert build_fingerprint({"p": Path("a")}, []) == build_fingerprint({"p": "a"}, [])


def test_build_record_is_read_back(tmp_path):
    write_build(tmp_path, "abc")

    assert read_build(tmp_path) == "abc"


def test_missing_build_record_reads_as_none(tmp_path):
    assert read_build(tmp_path) is None


# Half written, JSON but not an object, not text at all.
@pytest.mark.parametrize("content", [b'{"finger', b"[]", b'"abc"', b"\xff\xfe"])
def test_corrupt_build_record_reads_as_none(tmp_path, content):
    (tmp_path / BUILD_RECORD).write_bytes(content)

    assert read_build(tmp_path) is None


@pytest.mark.parametrize("content", [b"[]", b'{"mapbox": "abc"}', b"\xff\xfe"])
def test_corrupt_publish_record_reads_as_none(tmp_path, content):
    (tmp_path / PUBLISH_RECORD).write_bytes(content)

    assert read_published(tmp_path, "mapbox") is None


def test_publishing_over_a_corrupt_record_starts_a_new_one(tmp_path):
    (tmp_path / PUBLISH_RECORD).write_bytes(b"[]")

    write_published(tmp_path, "mapbox", "abc", "user.mangroves")

    assert read_published(tmp_path, "mapbox") == "abc"


def test_published_fingerprint_is_read_back(tmp_path):
    write_published(tmp_path, "mapbox", "abc", "user.mangroves")

    assert read_published(tmp_path, "mapbox") == "abc"


def test_publishing_elsewhere_keeps_the_other_destinations(tmp_path):
    write_published(tmp_path, "mapbox", "abc", "user.mangroves")

    write_published(tmp_path, "bucket", "def", "s3://layers/mangroves.mbtiles")

    assert read_published(tmp_path, "mapbox") == "abc"


def test_never_published_reads_as_none(tmp_path):
    write_published(tmp_path, "mapbox", "abc", "user.mangroves")

    assert read_published(tmp_path, "bucket") is None
