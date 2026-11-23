"""The names users import from vizz_geopipe and its gdal, sources, layers and destinations."""

import vizz_geopipe
import vizz_geopipe.destinations
import vizz_geopipe.gdal
import vizz_geopipe.layers
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


def test_layers_exports_its_public_names():
    assert set(vizz_geopipe.layers.__all__) == {"CogLayer", "Layer", "VectorLayer"}
    for name in vizz_geopipe.layers.__all__:
        assert hasattr(vizz_geopipe.layers, name)


def test_destinations_exports_its_public_names():
    assert set(vizz_geopipe.destinations.__all__) == {
        "Destination",
        "GCSDestination",
        "MapboxDestination",
        "S3Destination",
    }
    for name in vizz_geopipe.destinations.__all__:
        assert hasattr(vizz_geopipe.destinations, name)


def test_the_package_exports_the_public_api():
    expected = {
        "__version__", "Project", "StepResult", "LayerStatus",
        "GdalError", "SourceError", "PublishError",
    }  # fmt: skip
    for sub_package in (
        vizz_geopipe.gdal,
        vizz_geopipe.sources,
        vizz_geopipe.layers,
        vizz_geopipe.destinations,
    ):
        expected |= set(sub_package.__all__)
    assert set(vizz_geopipe.__all__) == expected
    for name in vizz_geopipe.__all__:
        assert hasattr(vizz_geopipe, name)
