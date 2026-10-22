"""Where layers get their data: downloads, local files, bucket objects and tile indexes."""

from vizz_geopipe.sources._base import Source
from vizz_geopipe.sources.http import HttpSource
from vizz_geopipe.sources.local import LocalSource
from vizz_geopipe.sources.tile_index import ArcGISTileIndex
from vizz_geopipe.sources.tile_index import TextTileIndex
from vizz_geopipe.sources.tile_index import TileIndex
from vizz_geopipe.sources.tile_index import TileIndexSource

__all__ = [
    "ArcGISTileIndex",
    "HttpSource",
    "LocalSource",
    "Source",
    "TextTileIndex",
    "TileIndex",
    "TileIndexSource",
]
