"""The names users import from vizz_geopipe.gdal and vizz_geopipe.sources."""

import vizz_geopipe.gdal
import vizz_geopipe.sources


def test_the_gdal_tier_exports_its_public_names():
    assert set(vizz_geopipe.gdal.__all__) == {
        "GdalError", "RasterPipeline", "VectorPipeline", "to_cog", "to_mbtiles", "to_pmtiles",
    }  # fmt: skip
    for name in vizz_geopipe.gdal.__all__:
        assert hasattr(vizz_geopipe.gdal, name)


def test_sources_exports_its_public_names():
    assert set(vizz_geopipe.sources.__all__) == {
        "ArcGISTileIndex",
        "BucketSource",
        "HttpSource",
        "LocalSource",
        "Source",
        "TextTileIndex",
        "TileIndex",
        "TileIndexSource",
    }
    for name in vizz_geopipe.sources.__all__:
        assert hasattr(vizz_geopipe.sources, name)
