"""vizz-geopipe: download, transform and publish map-ready geospatial data with GDAL."""

from importlib.metadata import version

__version__ = version("vizz-geopipe")

from vizz_geopipe.destinations import Destination
from vizz_geopipe.destinations import GCSDestination
from vizz_geopipe.destinations import MapboxDestination
from vizz_geopipe.destinations import S3Destination
from vizz_geopipe.errors import GdalError
from vizz_geopipe.errors import PublishError
from vizz_geopipe.errors import SourceError
from vizz_geopipe.gdal import RasterPipeline
from vizz_geopipe.gdal import VectorPipeline
from vizz_geopipe.gdal import to_cog
from vizz_geopipe.gdal import to_mbtiles
from vizz_geopipe.gdal import to_pmtiles
from vizz_geopipe.layers import CogLayer
from vizz_geopipe.layers import Layer
from vizz_geopipe.layers import VectorLayer
from vizz_geopipe.project import LayerStatus
from vizz_geopipe.project import Project
from vizz_geopipe.project import StepResult
from vizz_geopipe.sources import ArcGISTileIndex
from vizz_geopipe.sources import BucketSource
from vizz_geopipe.sources import HttpSource
from vizz_geopipe.sources import LocalSource
from vizz_geopipe.sources import Source
from vizz_geopipe.sources import TextTileIndex
from vizz_geopipe.sources import TileIndex
from vizz_geopipe.sources import TileIndexSource

__all__ = [
    "ArcGISTileIndex",
    "BucketSource",
    "CogLayer",
    "Destination",
    "GCSDestination",
    "GdalError",
    "HttpSource",
    "Layer",
    "LayerStatus",
    "LocalSource",
    "MapboxDestination",
    "Project",
    "PublishError",
    "RasterPipeline",
    "S3Destination",
    "Source",
    "SourceError",
    "StepResult",
    "TextTileIndex",
    "TileIndex",
    "TileIndexSource",
    "VectorLayer",
    "VectorPipeline",
    "__version__",
    "to_cog",
    "to_mbtiles",
    "to_pmtiles",
]
