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
    one, and every pattern in ``files`` still matches. Anything else downloads again.

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
        if refresh or not self._is_cached(dest):
            # Files of an older download (an edited URL) would still match the patterns.
            if dest.exists():
                shutil.rmtree(dest)
            dest.mkdir(parents=True)
            self._download(dest)
            # Written last, so an interrupted download is never taken for a finished one.
            record = {"identity": self.identity(), "fetched_at": datetime.now(UTC).isoformat()}
            (dest / RECORD_NAME).write_text(json.dumps(record, indent=2))
        return self._match(dest)

    @abstractmethod
    def _download(self, dest: Path) -> None:
        """Put the source's files in ``dest``, an empty folder that exists."""

    def _is_cached(self, dest: Path) -> bool:
        record = dest / RECORD_NAME
        if not record.is_file():
            return False
        if json.loads(record.read_text()).get("identity") != self.identity():
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
