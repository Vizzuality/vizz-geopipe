"""Tests for converting vector data to MBTiles and PMTiles."""

import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

from vizz_geopipe.gdal.vector import to_mbtiles
from vizz_geopipe.gdal.vector import to_pmtiles


def command(gdal_calls):
    """Return the recorded gdal command as one string, to search with ``in``."""
    return " ".join(gdal_calls[0])


def step_names(gdal_calls):
    """Return the names of the pipeline steps in the recorded command, in order."""
    args = gdal_calls[0]
    names = []
    for i, arg in enumerate(args):
        if arg == "!":
            names.append(args[i + 1])
    return names


# Without GDAL: check the command that would run.


def test_one_input_is_read_clipped_repaired_and_written(gdal_calls):
    to_mbtiles([Path("in.geojson")], Path("out.mbtiles"))

    assert step_names(gdal_calls) == ["read", "clip", "make-valid", "write"]


def test_features_are_clipped_to_web_mercator(gdal_calls):
    to_mbtiles([Path("in.geojson")], Path("out.mbtiles"))

    bbox = "-180.0,-85.0511287798066,180.0,85.0511287798066"
    assert f"clip --bbox {bbox} --bbox-crs EPSG:4326" in command(gdal_calls)


def test_zoom_levels_are_passed_to_gdal(gdal_calls):
    to_mbtiles([Path("in.geojson")], Path("out.mbtiles"), min_zoom=2, max_zoom=8)

    assert "--co MINZOOM=2 --co MAXZOOM=8" in command(gdal_calls)


def test_fields_keep_the_geometry(gdal_calls):
    to_mbtiles([Path("in.geojson")], Path("out.mbtiles"), fields=["name"])

    assert "select --fields name,_ogr_geometry_" in command(gdal_calls)


def test_labels_merge_inputs_into_one_layer(gdal_calls):
    to_mbtiles([Path("a.shp"), Path("b.shp")], Path("out.mbtiles"), labels=["A", "B"])

    assert step_names(gdal_calls) == ["concat", "sql", "clip", "make-valid", "write"]


def test_labels_become_a_type_attribute(gdal_calls):
    to_mbtiles([Path("a.shp"), Path("b.shp")], Path("out.mbtiles"), labels=["A", "B"])

    assert "WHEN '0' THEN 'A' WHEN '1' THEN 'B' END AS type" in command(gdal_calls)


def test_labels_with_quotes_are_escaped(gdal_calls):
    to_mbtiles([Path("a.shp"), Path("b.shp")], Path("out.mbtiles"), labels=["Côte d'Ivoire", "B"])

    assert "THEN 'Côte d''Ivoire'" in command(gdal_calls)


def test_to_pmtiles_writes_pmtiles(gdal_calls):
    to_pmtiles([Path("in.geojson")], Path("out.pmtiles"))

    assert "--output-format PMTiles" in command(gdal_calls)


def test_no_inputs_are_rejected(gdal_calls):
    with pytest.raises(ValueError, match="at least one input"):
        to_mbtiles([], Path("out.mbtiles"))


def test_labels_need_one_value_per_input(gdal_calls):
    with pytest.raises(ValueError, match="one value per input"):
        to_mbtiles([Path("a.shp"), Path("b.shp")], Path("out.mbtiles"), labels=["A"])


def test_open_options_need_a_single_input(gdal_calls):
    with pytest.raises(ValueError, match="single input"):
        to_mbtiles(
            [Path("a.shp"), Path("b.shp")], Path("out.mbtiles"), open_options={"ENCODING": "UTF-8"}
        )


def test_min_zoom_cannot_be_above_max_zoom(gdal_calls):
    with pytest.raises(ValueError, match="greater than max_zoom"):
        to_mbtiles([Path("in.geojson")], Path("out.mbtiles"), min_zoom=8, max_zoom=4)


# With GDAL: run it and inspect the output.


def write_points(path, properties):
    """Write a GeoJSON file with one point that has ``properties``, and return its path."""
    point = {
        "type": "Feature",
        "properties": properties,
        "geometry": {"type": "Point", "coordinates": [0, 0]},
    }
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [point]}))
    return path


def mbtiles_zoom_levels(path):
    """Return the lowest and highest zoom level stored in an MBTiles file."""
    with sqlite3.connect(path) as db:
        return db.execute("SELECT MIN(zoom_level), MAX(zoom_level) FROM tiles").fetchone()


def mbtiles_fields(path):
    """Return the attributes stored in an MBTiles file, as ``{name: type}``."""
    with sqlite3.connect(path) as db:
        (metadata,) = db.execute("SELECT value FROM metadata WHERE name = 'json'").fetchone()
    return json.loads(metadata)["vector_layers"][0]["fields"]


def layer_names(path):
    """Return the names of the layers in a vector file, as GDAL reads them."""
    info = subprocess.run(
        ["gdal", "vector", "info", "--format", "json", str(path)],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    return [layer["name"] for layer in json.loads(info.stdout)["layers"]]


@pytest.mark.gdal
def test_mbtiles_has_the_requested_zoom_levels(geojson_file, tmp_path):
    output = to_mbtiles([geojson_file], tmp_path / "places.mbtiles", min_zoom=1, max_zoom=3)

    assert mbtiles_zoom_levels(output) == (1, 3)


@pytest.mark.gdal
def test_mbtiles_keeps_only_the_selected_fields(geojson_file, tmp_path):
    output = to_mbtiles([geojson_file], tmp_path / "places.mbtiles", max_zoom=2, fields=["name"])

    assert mbtiles_fields(output) == {"name": "String"}


@pytest.mark.gdal
def test_labelled_inputs_keep_number_fields(tmp_path):
    # GDAL 3.13 turned a number into text when another field followed it, hence "name".
    a = write_points(tmp_path / "a.geojson", {"pop": 5, "name": "a"})
    b = write_points(tmp_path / "b.geojson", {"pop": 0, "name": "b"})

    output = to_mbtiles([a, b], tmp_path / "out.mbtiles", max_zoom=2, labels=["A", "B"])

    assert mbtiles_fields(output)["pop"] == "Number"


@pytest.mark.gdal
def test_pmtiles_layer_is_named_after_the_file(geojson_file, tmp_path):
    output = to_pmtiles([geojson_file], tmp_path / "places.pmtiles", max_zoom=2)

    assert layer_names(output) == ["places"]
