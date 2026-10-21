"""Tests for building gdal raster pipeline commands."""

from pathlib import Path

from vizz_geopipe.gdal.raster import RasterPipeline


def test_edit_keeps_zero_nodata():
    pipe = RasterPipeline.read(Path("in.tif")).edit(nodata=0)

    assert pipe.args()[-4:] == ["!", "edit", "--nodata", "0"]


def test_optional_arguments_left_out_add_no_flags():
    pipe = RasterPipeline.read(Path("in.tif")).reproject("EPSG:3857")

    assert pipe.args()[-4:] == ["!", "reproject", "--dst-crs", "EPSG:3857"]
