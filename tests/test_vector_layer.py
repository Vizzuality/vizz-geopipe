"""Tests for vector layers, built as MBTiles or PMTiles."""

import pytest

from vizz_geopipe.layers import VectorLayer
from vizz_geopipe.sources import LocalSource


def source(pattern, label=None):
    return LocalSource(files=(pattern,), label=label)


def test_suffix_follows_the_output_format():
    layer = VectorLayer(name="a", title="A", sources=(source("a.gpkg"),), output_format="PMTiles")

    assert layer.suffix == ".pmtiles"


def test_labels_must_be_given_for_every_source():
    with pytest.raises(ValueError, match="label"):
        VectorLayer(name="a", title="A", sources=(source("a.gpkg", "A"), source("b.gpkg")))


def test_min_zoom_above_max_zoom_is_rejected():
    with pytest.raises(ValueError):
        VectorLayer(name="a", title="A", sources=(source("a.gpkg"),), min_zoom=8, max_zoom=4)


def test_each_file_gets_its_source_label(tmp_path, gdal_calls):
    layer = VectorLayer(name="a", title="A", sources=(source("x", "A"), source("y", "B")))

    inputs = [[tmp_path / "1.shp", tmp_path / "2.shp"], [tmp_path / "3.shp"]]

    layer.convert(inputs, tmp_path / "a.mbtiles")

    assert "WHEN '0' THEN 'A' WHEN '1' THEN 'A' WHEN '2' THEN 'B'" in " ".join(gdal_calls[0])


@pytest.mark.gdal
def test_a_vector_layer_builds_mbtiles(workdir, geojson_file):
    layer = VectorLayer(name="places", title="Places", sources=(source(str(geojson_file)),))

    artifact = layer.build(workdir)

    assert artifact.name == "places.mbtiles"
    assert artifact.stat().st_size > 0
