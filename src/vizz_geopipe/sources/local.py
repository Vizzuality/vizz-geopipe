"""Sources that are files already on this computer."""

from dataclasses import dataclass
from pathlib import Path

from vizz_geopipe.errors import SourceError
from vizz_geopipe.sources._base import Source


@dataclass(frozen=True, kw_only=True)
class LocalSource(Source):
    """Files already on this computer, read where they are.

    Nothing is copied or downloaded, so there is nothing to cache: ``fetch`` never writes to
    ``dest``. Relative patterns are read from the current working directory, which the
    ``geopipe`` command sets to the project root.

    Attributes:
        files: Paths or glob patterns of the files to read, e.g. ``("data/*.gpkg",)``.
    """

    files: tuple[str, ...]

    def fetch(self, dest: Path, refresh: bool = False) -> list[Path]:
        """Return the files matching each pattern in ``files``, pattern by pattern, each sorted.

        Args:
            dest: Not used: the files stay where they are.
            refresh: Not used: there is no copy to refresh.

        Raises:
            SourceError: If a pattern matches no file.
        """
        return self._match()

    def identity(self) -> dict[str, str]:
        """Return each matching file's path with its size and modification time.

        Editing, replacing or touching a file changes its identity.
        """
        identity: dict[str, str] = {}
        for path in self._match():
            stat = path.stat()
            identity[str(path)] = f"{stat.st_size}:{stat.st_mtime_ns}"
        return identity

    def _match(self) -> list[Path]:
        """Return the files matching each pattern, pattern by pattern, each sorted."""
        paths: list[Path] = []
        for pattern in self.files:
            # Path.glob only takes relative patterns: glob an absolute one from its anchor ("/").
            anchor = Path(pattern).anchor
            base = Path(anchor) if anchor else Path.cwd()
            matches = sorted(base.glob(pattern.removeprefix(anchor)))
            if not matches:
                raise SourceError(pattern, "no file matches")
            paths += matches
        return paths
