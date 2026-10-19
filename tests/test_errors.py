"""Tests for the exceptions vizz-geopipe raises."""

from vizz_geopipe.errors import PublishError
from vizz_geopipe.errors import SourceError


def test_source_error_keeps_the_source_and_the_reason():
    error = SourceError("https://example.com/a.zip", "404 Not Found")

    assert error.source == "https://example.com/a.zip"
    assert error.reason == "404 Not Found"
    assert str(error) == "https://example.com/a.zip: 404 Not Found"


def test_publish_error_keeps_the_destination_and_the_reason():
    error = PublishError("mapbox", "upload failed")

    assert error.destination == "mapbox"
    assert error.reason == "upload failed"
    assert str(error) == "mapbox: upload failed"


def test_both_are_runtime_errors():
    assert isinstance(SourceError("a", "b"), RuntimeError)
    assert isinstance(PublishError("a", "b"), RuntimeError)
