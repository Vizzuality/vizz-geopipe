"""The interface every layer follows, and the build shared by all of them."""

from abc import ABC
from abc import abstractmethod
from collections.abc import Sequence
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path

from vizz_geopipe.fingerprint import build_fingerprint
from vizz_geopipe.fingerprint import read_build
from vizz_geopipe.fingerprint import write_build
from vizz_geopipe.sources import Source
from vizz_geopipe.workdir import Workdir

# Fields that do not change the artifact: editing them must not rebuild the layer.
NOT_FINGERPRINTED = ("title", "publish_to")


@dataclass(frozen=True, kw_only=True)
class Layer(ABC):
    """A dataset to build from one or more sources into one artifact, ready to publish.

    ``build`` is written once, here: fetch the sources, ``convert`` them into a temporary
    file, move it into place and record its fingerprint. A subclass writes ``suffix`` and
    ``convert``.

    Attributes:
        name: The layer's id: names its folders and its artifact.
        title: A human-readable name.
        sources: Where the data comes from. ``convert`` gets their files in this order.
        publish_to: The names of the destinations to publish to.
    """

    name: str
    title: str
    sources: tuple[Source, ...]
    publish_to: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Check the layer when it is created, not when it is built.

        Raises:
            ValueError: If there are no sources.
        """
        if not self.sources:
            raise ValueError(f"layer {self.name!r} has no sources")

    @property
    @abstractmethod
    def suffix(self) -> str:
        """The artifact's file suffix, e.g. ``".mbtiles"``."""

    @abstractmethod
    def convert(self, inputs: Sequence[Sequence[Path]], output: Path) -> Path:
        """Convert the sources' files into ``output``.

        Public, so a script can convert files it already has, without a ``Workdir``.

        Args:
            inputs: The files of each source: ``inputs[i]`` are those of ``sources[i]``.
            output: The file to write.

        Returns:
            ``output``.
        """

    def artifact(self, workdir: Workdir) -> Path:
        """Return where the built artifact goes: ``processed/<name>/<name><suffix>``."""
        return workdir.processed_dir(self.name) / f"{self.name}{self.suffix}"

    def fingerprint(self) -> str:
        """Return the fingerprint of everything that shapes the artifact.

        That is every field except ``title`` and ``publish_to``, the layer's class, and the
        ``identity()`` of each source.
        """
        config = {key: value for key, value in asdict(self).items() if key not in NOT_FINGERPRINTED}
        config["type"] = type(self).__name__
        return build_fingerprint(config, [source.identity() for source in self.sources])

    def is_built(self, workdir: Workdir) -> bool:
        """Return whether the artifact exists and was built from what the layer is now."""
        artifact = self.artifact(workdir)
        return artifact.is_file() and read_build(artifact.parent) == self.fingerprint()

    def build(self, workdir: Workdir, refresh: bool = False) -> Path:
        """Fetch the sources, convert them, and put the artifact in place.

        It always builds; ``is_built`` is the check for whether it needs to.

        Args:
            workdir: The project's data folder.
            refresh: Download the sources again instead of using their cache.

        Returns:
            The artifact.
        """
        # Before fetching: the record must describe the data that was asked for, even if a
        # source changes while the layer builds.
        fingerprint = self.fingerprint()
        inputs = [
            source.fetch(workdir.raw_dir(self.name) / str(index), refresh=refresh)
            for index, source in enumerate(self.sources)
        ]
        # In tmp/, on the same file system as processed/, so the move below is atomic: a
        # failed build leaves the previous artifact as it was.
        temporary = workdir.tmp_dir() / f"{self.name}{self.suffix}"
        try:
            self.convert(inputs, temporary)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        artifact = self.artifact(workdir)
        temporary.replace(artifact)
        # Written last, so an interrupted build is never taken for a finished one.
        write_build(artifact.parent, fingerprint)
        return artifact
