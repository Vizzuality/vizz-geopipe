"""The names users import from vizz_geopipe.gdal."""

import vizz_geopipe.gdal


def test_the_gdal_tier_exports_its_public_names():
    assert set(vizz_geopipe.gdal.__all__) == {
        "GdalError", "RasterPipeline", "VectorPipeline", "to_cog", "to_mbtiles", "to_pmtiles",
    }  # fmt: skip
    for name in vizz_geopipe.gdal.__all__:
        assert hasattr(vizz_geopipe.gdal, name)
