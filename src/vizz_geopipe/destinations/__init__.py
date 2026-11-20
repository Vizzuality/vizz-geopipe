"""Destinations: where built artifacts are published."""

from vizz_geopipe.destinations._base import Destination
from vizz_geopipe.destinations.mapbox import MapboxDestination
from vizz_geopipe.destinations.s3 import S3Destination

__all__ = ["Destination", "MapboxDestination", "S3Destination"]
