"""Rasters split into tiles, with the download URL of each tile listed by an index."""

from abc import ABC
from abc import abstractmethod
from dataclasses import asdict
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
        """Return the URL on each line, by its file name without the suffix.

        Raises:
            SourceError: If the list cannot be read, or two URLs have the same file name.
        """
        urls: dict[str, str] = {}
        for url in self._get(self.url).text.split():
            tile = Path(urlparse(url).path).stem
            if tile in urls:
                raise SourceError(self.url, f"two tiles named {tile}")
            urls[tile] = url
        return urls


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
            SourceError: If the layer cannot be queried, answers with an error, cuts the list
                at its record limit, or leaves out the features or one of the two fields.
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
        if "features" not in result:
            raise SourceError(self.url, "no features in the answer")
        urls: dict[str, str] = {}
        for feature in result["features"]:
            attributes = feature.get("attributes", {})
            for field in (self.name_field, self.url_field):
                if field not in attributes:
                    raise SourceError(self.url, f"no field {field} in the answer")
            urls[attributes[self.name_field]] = attributes[self.url_field]
        return urls


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

    def __post_init__(self) -> None:
        """Reject an empty ``tiles``, which would download nothing."""
        if self.tiles == ():
            raise ValueError("tiles is empty: list tile ids, or None for every tile")

    def identity(self) -> dict[str, str]:
        """Return the index, every field of it, and the selected tiles, without reading it."""
        index = {f"index.{name}": str(value) for name, value in asdict(self.index).items()}
        tiles = ",".join(sorted(self.tiles)) if self.tiles is not None else "*"
        return {"index": type(self.index).__name__, **index, "tiles": tiles}

    def _download(self, dest: Path) -> None:
        urls = self.index.tile_urls()
        selected = self.tiles if self.tiles is not None else tuple(urls)
        # Checked before downloading anything, so a typo does not cost a long download.
        if unknown := sorted(set(selected) - set(urls)):
            raise SourceError(self.index.url, f"unknown tiles: {', '.join(unknown)}")
        for tile in selected:
            url = urls[tile]
            download_file(url, dest / f"{tile}{Path(urlparse(url).path).suffix}")
