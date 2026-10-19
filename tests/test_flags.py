"""Tests for turning Python keyword arguments into GDAL flags."""

from pathlib import Path

import pytest

from vizz_geopipe.gdal._flags import to_flags


def test_snake_case_becomes_a_kebab_case_flag():
    assert to_flags(bbox_crs="EPSG:4326") == ["--bbox-crs", "EPSG:4326"]


def test_true_becomes_a_bare_flag():
    assert to_flags(overwrite=True) == ["--overwrite"]


def test_false_and_none_are_omitted():
    assert to_flags(overwrite=False, where=None) == []


def test_zero_is_kept():
    assert to_flags(nodata=0) == ["--nodata", "0"]


def test_sequences_are_comma_joined():
    assert to_flags(bbox=(-180.0, -85.0, 180.0, 85.0)) == ["--bbox", "-180.0,-85.0,180.0,85.0"]


def test_mappings_repeat_their_flag_for_each_item():
    flags = to_flags(creation_options={"MINZOOM": 0, "MAXZOOM": 12})

    assert flags == ["--co", "MINZOOM=0", "--co", "MAXZOOM=12"]


def test_paths_become_strings():
    assert to_flags(like=Path("data/a.tif")) == ["--like", "data/a.tif"]


def test_a_mapping_for_an_unknown_option_is_rejected():
    with pytest.raises(TypeError, match="bad_option"):
        to_flags(bad_option={"A": 1})
