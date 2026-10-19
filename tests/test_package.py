"""Tests for the package itself: that it installs and knows its version."""

from importlib.metadata import version

import vizz_geopipe


def test_version_matches_the_installed_metadata():
    assert vizz_geopipe.__version__ == version("vizz-geopipe")
