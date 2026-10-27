"""The interface every source follows, and the download cache shared by most of them."""

import json
import shutil
from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path

from vizz_geopipe.errors import SourceError
from vizz_geopipe.sources._files import atomic_write

RECORD_NAME = ".source.json"


@dataclass(frozen=True, kw_only=True)
class Source(ABC):
    """Where a layer gets its data.

    Attributes:
        label: Value that identifies this source's features when a layer merges sources.
    """

    label: str | None = None

    @abstractmethod
    def fetch(self, dest: Path, refresh: bool = False) -> list[Path]:
        """Get the data, and return the paths of the files to read.

        Args:
            dest: The folder this source may write into. It belongs to this source alone.
            refresh: Get the data again even if a previous fetch is still valid.

        Raises:
            SourceError: If the data cannot be fetched, or a pattern matches no file.
        """

    @abstractmethod
    def identity(self) -> dict[str, str]:
        """Return what makes this source "the same data": if it changes, fetch again."""


@dataclass(frozen=True, kw_only=True)
class CachedSource(Source):
    """A source that downloads into ``dest``, and reuses the download while it is valid.

    After a download, ``dest/.source.json`` records the source's ``identity()``. A later
    ``fetch`` reuses the files only if that record exists, its identity equals the current
    one, and every pattern in ``files`` still matches. Anything else downloads again, after
    deleting everything in ``dest``: give each source a folder of its own.

    A pattern also matches folders, on purpose: a File Geodatabase (``x.gdb``) is a folder
    that GDAL reads.

    Attributes:
        files: Glob patterns of the files to read, relative to ``dest``.
    """

    files: tuple[str, ...]

    def fetch(self, dest: Path, refresh: bool = False) -> list[Path]:
        """Download into ``dest`` unless the last download is still valid.

        Returns:
            The files matching each pattern in ``files``, pattern by pattern, each sorted.

        Raises:
            SourceError: If the download fails, or a pattern matches no file.
        """
        # Asked once: the record must describe the data the cache was checked against, even if
        # the source changes while it downloads.
        identity = self.identity()
        if refresh or not self._is_cached(dest, identity):
            # Files of an older download (an edited URL) would still match the patterns.
            if dest.exists():
                shutil.rmtree(dest)
            dest.mkdir(parents=True)
            self._download(dest)
            # Written last, so an interrupted download is never taken for a finished one.
            record = {"identity": identity, "fetched_at": datetime.now(UTC).isoformat()}
            with atomic_write(dest / RECORD_NAME) as file:
                file.write(json.dumps(record, indent=2).encode())
        return self._match(dest)

    @abstractmethod
    def _download(self, dest: Path) -> None:
        """Put the source's files in ``dest``, an empty folder that exists."""

    def _is_cached(self, dest: Path, identity: dict[str, str]) -> bool:
        try:
            recorded = json.loads((dest / RECORD_NAME).read_text()).get("identity")
        # A missing or half-written record is no record: download again.
        except (FileNotFoundError, json.JSONDecodeError):
            return False
        if recorded != identity:
            return False
        return all(self._glob(dest, pattern) for pattern in self.files)

    def _match(self, dest: Path) -> list[Path]:
        paths = []
        for pattern in self.files:
            if not (matches := self._glob(dest, pattern)):
                raise SourceError(pattern, f"no file matches in {dest}")
            paths += matches
        return paths

    @staticmethod
    def _glob(dest: Path, pattern: str) -> list[Path]:
        # The record is bookkeeping, never data, even for the pattern "*".
        return sorted(path for path in dest.glob(pattern) if path.name != RECORD_NAME)
