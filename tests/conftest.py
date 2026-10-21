"""Fixtures shared by all tests."""

import json
from pathlib import Path

import pytest

from vizz_geopipe.errors import GdalError
from vizz_geopipe.gdal import _pipeline
from vizz_geopipe.gdal._runner import MIN_VERSION
from vizz_geopipe.gdal._runner import gdal_version
from vizz_geopipe.gdal._runner import run_gdal


def gdal_is_installed() -> bool:
    """Return whether GDAL 3.13 or newer is on PATH."""
    try:
        return gdal_version()[:2] >= MIN_VERSION
    except GdalError:
        return False


def pytest_collection_modifyitems(items):
    """Skip the tests marked ``gdal`` when GDAL 3.13 or newer is not installed."""
    if gdal_is_installed():
        return
    for item in items:
        if "gdal" in item.keywords:
            item.add_marker(pytest.mark.skip(reason="needs GDAL 3.13 or newer on PATH"))


@pytest.fixture
def gdal_calls(monkeypatch) -> list[list[str]]:
    """Record pipeline runs instead of running gdal, and return the recorded arguments."""
    calls: list[list[str]] = []

    def record(args, config=None):
        calls.append(list(args))

    monkeypatch.setattr(_pipeline, "run_gdal", record)
    return calls


@pytest.fixture
def geojson_file(tmp_path) -> Path:
    """A GeoJSON file with one point, whose attributes are "name" and "kind"."""
    point = {
        "type": "Feature",
        "properties": {"name": "a", "kind": "x"},
        "geometry": {"type": "Point", "coordinates": [0, 0]},
    }
    path = tmp_path / "places.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [point]}))
    return path


@pytest.fixture
def geotiff_file(tmp_path) -> Path:
    """A 64x64 GeoTIFF over (0, 0, 1, 1) in EPSG:4326, with every pixel set to 7."""
    path = tmp_path / "grid.tif"
    options = "--size 64,64 --datatype Byte --crs EPSG:4326 --bbox 0,0,1,1 --burn 7"
    run_gdal(["raster", "create", *options.split(), str(path)])
    return path
