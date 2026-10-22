"""Rasters split into tiles, with the download URL of each tile listed by an index."""

from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

from vizz_geopipe.errors import SourceError
from vizz_geopipe.sources._base import CachedSource
from vizz_geopipe.sources._files import download_file

TIMEOUT = 60


@dataclass(frozen=True, kw_only=True)
class TileIndex(ABC):
    """A list of the tiles of a raster and where to download each one.

    Attributes:
        url: Where the list is.
    """

    url: str

    @abstractmethod
    def tile_urls(self) -> dict[str, str]:
        """Return the download URL of each tile, by tile id.

        Raises:
            SourceError: If the list cannot be read.
        """

    def _get(self, url: str, **params: str) -> requests.Response:
        try:
            response = requests.get(url, params=params or None, timeout=TIMEOUT)
            response.raise_for_status()
        except requests.RequestException as error:
            raise SourceError(self.url, str(error)) from error
        return response


@dataclass(frozen=True, kw_only=True)
class TextTileIndex(TileIndex):
    """A text file with one tile URL per line. Each tile is named after its file name."""

    def tile_urls(self) -> dict[str, str]:
        """Return the URL on each line, by its file name without the suffix."""
        return {Path(urlparse(url).path).stem: url for url in self._get(self.url).text.split()}


@dataclass(frozen=True, kw_only=True)
class ArcGISTileIndex(TileIndex):
    """An ArcGIS feature layer with one feature per tile.

    Attributes:
        name_field: Field with the tile id.
        url_field: Field with the tile's download URL.
    """

    name_field: str
    url_field: str

    def tile_urls(self) -> dict[str, str]:
        """Return the ``url_field`` of every feature, by its ``name_field``.

        Raises:
            SourceError: If the layer cannot be queried, answers with an error, or cuts the
                list at its record limit.
        """
        response = self._get(
            f"{self.url}/query",
            where="1=1",
            outFields=f"{self.name_field},{self.url_field}",
            returnGeometry="false",
            f="json",
        )
        try:
            result = response.json()
        except requests.JSONDecodeError as error:
            raise SourceError(self.url, f"not JSON: {error}") from error
        # ArcGIS reports errors, and results cut at the server's record limit, with a 200.
        if "error" in result:
            raise SourceError(self.url, f"ArcGIS error: {result['error']}")
        if result.get("exceededTransferLimit"):
            raise SourceError(self.url, "the tile list was cut at the server's record limit")
        return {
            feature["attributes"][self.name_field]: feature["attributes"][self.url_field]
            for feature in result["features"]
        }


@dataclass(frozen=True, kw_only=True)
class TileIndexSource(CachedSource):
    """The tiles of a raster, downloaded from the URLs a tile index lists.

    Each tile is saved as ``<tile id><suffix of its URL>``, e.g. ``10N_000E.tif``.

    Attributes:
        index: Where the list of tiles is.
        tiles: The ids of the tiles to download, or ``None`` for every tile in the index.
        files: Glob patterns of the files to read; every downloaded tile by default.
    """

    index: TileIndex
    tiles: tuple[str, ...] | None = None
    files: tuple[str, ...] = ("*",)

    def identity(self) -> dict[str, str]:
        """Return the index URL and the selected tiles, without reading the index."""
        return {"index": self.index.url, "tiles": ",".join(sorted(self.tiles or ("*",)))}

    def _download(self, dest: Path) -> None:
        urls = self.index.tile_urls()
        selected = self.tiles if self.tiles is not None else tuple(urls)
        # Checked before downloading anything, so a typo does not cost a long download.
        if unknown := sorted(set(selected) - set(urls)):
            raise SourceError(self.index.url, f"unknown tiles: {', '.join(unknown)}")
        for tile in selected:
            url = urls[tile]
            download_file(url, dest / f"{tile}{Path(urlparse(url).path).suffix}")
