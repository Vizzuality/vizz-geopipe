"""Tests for converting rasters to Cloud Optimized GeoTIFFs."""

import json
import subprocess
from pathlib import Path

import pytest

from vizz_geopipe.gdal.raster import to_cog


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


def test_one_raster_is_read_and_written(gdal_calls):
    to_cog([Path("in.tif")], Path("out.tif"), dst_crs=None)

    assert step_names(gdal_calls) == ["read", "write"]


def test_several_rasters_are_mosaicked(gdal_calls):
    to_cog([Path("a.tif"), Path("b.tif")], Path("out.tif"))

    assert "! mosaic a.tif b.tif" in command(gdal_calls)


def test_steps_run_in_order_nodata_clip_reproject(gdal_calls):
    to_cog([Path("in.tif")], Path("out.tif"), nodata=0, dst_crs="EPSG:3857", bbox=(0, 0, 1, 1))

    assert step_names(gdal_calls) == ["read", "edit", "clip", "reproject", "write"]


def raster_info(path):
    """Return what ``gdal raster info`` says about a raster, as a dictionary."""
    info = subprocess.run(
        ["gdal", "raster", "info", "--format", "json", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(info.stdout)


@pytest.mark.gdal
def test_output_is_a_zstd_cog(geotiff_file, tmp_path):
    output = to_cog([geotiff_file], tmp_path / "grid_cog.tif")

    structure = raster_info(output)["metadata"]["IMAGE_STRUCTURE"]
    assert structure["LAYOUT"] == "COG"
    assert structure["COMPRESSION"] == "ZSTD"


@pytest.mark.gdal
def test_the_output_is_web_mercator_by_default(geotiff_file, tmp_path):
    output = to_cog([geotiff_file], tmp_path / "grid_cog.tif")

    assert raster_info(output)["stac"]["proj:epsg"] == 3857


@pytest.mark.gdal
def test_dst_crs_none_keeps_the_source_crs(geotiff_file, tmp_path):
    output = to_cog([geotiff_file], tmp_path / "grid_cog.tif", dst_crs=None)

    assert raster_info(output)["stac"]["proj:epsg"] == 4326


@pytest.mark.gdal
def test_nodata_is_set_on_the_output(geotiff_file, tmp_path):
    output = to_cog([geotiff_file], tmp_path / "grid_cog.tif", nodata=0)

    band = raster_info(output)["bands"][0]
    assert band["noDataValue"] == 0
