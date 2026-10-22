"""Where layers get their data: downloads, local files, bucket objects and tile indexes."""

from vizz_geopipe.sources._base import Source
from vizz_geopipe.sources.http import HttpSource

__all__ = [
    "HttpSource",
    "Source",
]
