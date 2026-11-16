"""Tests for raster layers, built as Cloud Optimized GeoTIFFs."""

import pytest

from vizz_geopipe.layers import CogLayer
from vizz_geopipe.sources import LocalSource


def test_suffix_is_tif():
    layer = CogLayer(name="dem", title="DEM", sources=(LocalSource(files=("a.tif",)),))

    assert layer.suffix == ".tif"


def test_files_of_every_source_are_mosaicked(tmp_path, gdal_calls):
    sources = (LocalSource(files=("a",)), LocalSource(files=("b",)))
    layer = CogLayer(name="dem", title="DEM", sources=sources, resampling="nearest")

    layer.convert([[tmp_path / "1.tif"], [tmp_path / "2.tif"]], tmp_path / "dem.tif")

    command = " ".join(gdal_calls[0])
    assert "mosaic" in command
    assert "OVERVIEW_RESAMPLING=nearest" in command


@pytest.mark.gdal
def test_a_cog_layer_builds_a_cog(workdir, geotiff_file):
    source = LocalSource(files=(str(geotiff_file),))
    layer = CogLayer(name="grid", title="Grid", sources=(source,))

    artifact = layer.build(workdir)

    assert artifact.name == "grid.tif"
    assert artifact.stat().st_size > 0
