"""Tests for turning Python keyword arguments into GDAL flags."""

from vizz_geopipe.gdal._flags import to_flags


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
