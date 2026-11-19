"""Destinations: where built artifacts are published."""

from vizz_geopipe.destinations._base import Destination
from vizz_geopipe.destinations.mapbox import MapboxDestination

__all__ = ["Destination", "MapboxDestination"]
