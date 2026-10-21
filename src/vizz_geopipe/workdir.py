"""The folders a project keeps its downloads, outputs and temporary files in."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Workdir:
    """The data folder of a project, split into raw, processed and temporary files.

    Attributes:
        root: The project's data folder.
    """

    root: Path

    def _folder_name(self, name: str) -> str:
        """Return ``name`` if it is a single folder name.

        Raises:
            ValueError: If ``name`` is not a single folder name.
        """
        if Path(name).name != name or name in {"", ".", ".."}:
            raise ValueError(f"{name!r} is not a single folder name")
        return name

    def _make(self, path: Path) -> Path:
        """Create the folder ``path`` if it does not exist, and return it."""
        path.mkdir(parents=True, exist_ok=True)
        return path

    def raw_dir(self, name: str) -> Path:
        """Return ``root/raw/<name>``, creating it if needed.

        Raises:
            ValueError: If ``name`` is not a single folder name.
        """
        return self._make(self.root / "raw" / self._folder_name(name))

    def processed_dir(self, name: str) -> Path:
        """Return ``root/processed/<name>``, creating it if needed.

        Raises:
            ValueError: If ``name`` is not a single folder name.
        """
        return self._make(self.root / "processed" / self._folder_name(name))

    def tmp_dir(self) -> Path:
        """Return ``root/tmp``, creating it if needed."""
        return self._make(self.root / "tmp")
