"""A project: the layers of a repository and the destinations they publish to."""

from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

from vizz_geopipe.destinations import Destination
from vizz_geopipe.layers import Layer
from vizz_geopipe.workdir import Workdir
from vizz_geopipe.workdir import check_folder_name


@dataclass(frozen=True, kw_only=True)
class Project:
    """The layers of a repository, the destinations they publish to, and where data lives.

    The configuration is checked when the project is created, so a mistake fails before
    anything is downloaded or built.

    Attributes:
        data_dir: The project's data folder.
        layers: The layers, in the order they are built and published.
        destinations: The destinations by name, as ``Layer.publish_to`` refers to them.
    """

    data_dir: Path
    layers: Sequence[Layer]
    destinations: Mapping[str, Destination] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Check the layers against each other and against the destinations.

        Raises:
            ValueError: If two layers share a name, a name is not a single folder name, a
                layer publishes to an unknown destination, or a destination cannot publish
                a layer's file or name.
        """
        seen = set()
        for layer in self.layers:
            if layer.name in seen:
                raise ValueError(f"two layers are named {layer.name!r}")
            seen.add(layer.name)
            try:
                check_folder_name(layer.name)
            except ValueError as error:
                raise ValueError(f"layer {layer.name!r}: {error}") from None
            for key in layer.publish_to:
                if key not in self.destinations:
                    raise ValueError(
                        f"layer {layer.name!r} publishes to {key!r}, which is not in destinations"
                    )
                try:
                    self._check_destination(layer, self.destinations[key])
                except ValueError as error:
                    raise ValueError(f"layer {layer.name!r}: {error}") from None

    def _check_destination(self, layer: Layer, destination: Destination) -> None:
        """Raise ``ValueError`` if ``destination`` cannot publish ``layer``."""
        if not destination.accepts(Path(f"{layer.name}{layer.suffix}")):
            raise ValueError(f"{type(destination).__name__} cannot publish {layer.suffix} files")
        destination.validate(layer.name)

    @property
    def workdir(self) -> Workdir:
        """The project's data folders."""
        return Workdir(self.data_dir)

    def _select(
        self, names: Sequence[str] | None, *, to: str | None = None, publishing: bool = False
    ) -> list[Layer]:
        """Return the layers a call works on, in declaration order.

        Args:
            names: The layers asked for, or ``None`` for all of them.
            to: Only the layers that publish to this destination. Layers named in ``names``
                are never filtered by it; with ``publishing`` they must publish to it, or
                the call raises.
            publishing: The call publishes, so every layer must have something to publish.

        Raises:
            ValueError: If a name or ``to`` is unknown, or a layer asked for by name has
                nothing to publish.
        """
        known = {layer.name for layer in self.layers}
        unknown = sorted(set(names or ()) - known)
        if unknown:
            raise ValueError(f"unknown layers: {', '.join(unknown)}")
        if to is not None and to not in self.destinations:
            raise ValueError(f"unknown destination: {to!r}")

        def publishes(layer: Layer) -> bool:
            return to in layer.publish_to if to is not None else bool(layer.publish_to)

        if names is None:
            filtered = publishing or to is not None
            return [layer for layer in self.layers if not filtered or publishes(layer)]
        chosen = [layer for layer in self.layers if layer.name in names]
        if publishing:
            for layer in chosen:
                if not publishes(layer):
                    raise ValueError(f"layer {layer.name!r} has nothing to publish")
        return chosen
