"""Sources downloaded over HTTP."""

import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from vizz_geopipe.sources._base import CachedSource
from vizz_geopipe.sources._files import download_file
from vizz_geopipe.sources._files import extract_zips


@dataclass(frozen=True, kw_only=True)
class HttpSource(CachedSource):
    """A file downloaded from a URL.

    Zip archives, and zips nested one level inside them, are extracted. Any other download
    is saved as ``files[0]``, so ``files[0]`` must then be a file name, not a pattern.

    Attributes:
        url: Where to download the data.
    """

    url: str

    def identity(self) -> dict[str, str]:
        """Return the URL: a new URL is new data."""
        return {"url": self.url}

    def _download(self, dest: Path) -> None:
        name = Path(urlparse(self.url).path).name or "download"
        download = download_file(self.url, dest / name)
        if zipfile.is_zipfile(download):
            extract_zips(download, dest)
        else:
            download.replace(dest / self.files[0])
