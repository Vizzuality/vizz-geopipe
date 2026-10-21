"""Fixtures shared by all tests."""

import json
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

import pytest
import requests

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


@dataclass
class FakeWeb:
    """What ``requests.get`` answers in tests, and the URLs it was asked for.

    Attributes:
        pages: The body of each URL. Any other URL answers 404.
        requested: Every URL asked for, in order.
    """

    pages: dict[str, bytes] = field(default_factory=dict)
    requested: list[str] = field(default_factory=list)


class FakeResponse:
    """The parts of ``requests.Response`` the sources use."""

    def __init__(self, url: str, body: bytes | None) -> None:
        self.url = url
        self.body = body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *exc_info) -> None:
        return None

    def raise_for_status(self) -> None:
        if self.body is None:
            raise requests.HTTPError(f"404 Not Found: {self.url}")

    def iter_content(self, chunk_size: int):
        yield self.body

    @property
    def text(self) -> str:
        return self.body.decode()

    def json(self):
        return json.loads(self.body)


@pytest.fixture
def fake_web(monkeypatch) -> FakeWeb:
    """Answer ``requests.get`` from ``FakeWeb.pages`` instead of the internet."""
    web = FakeWeb()

    def get(url, **kwargs):
        web.requested.append(url)
        return FakeResponse(url, web.pages.get(url))

    monkeypatch.setattr(requests, "get", get)
    return web
