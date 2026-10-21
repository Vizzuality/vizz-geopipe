"""Tests for the exceptions vizz-geopipe raises."""

from vizz_geopipe.errors import SourceError


def test_source_error_keeps_the_source_and_the_reason():
    error = SourceError("https://example.com/a.zip", "404 Not Found")

    assert error.source == "https://example.com/a.zip"
    assert error.reason == "404 Not Found"
    assert str(error) == "https://example.com/a.zip: 404 Not Found"
