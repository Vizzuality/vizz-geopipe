"""Layers of vector data, built as vector tiles."""

from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from vizz_geopipe.gdal import to_mbtiles
from vizz_geopipe.gdal import to_pmtiles
from vizz_geopipe.layers._base import Layer

SUFFIXES = {"MBTiles": ".mbtiles", "PMTiles": ".pmtiles"}


@dataclass(frozen=True, kw_only=True)
class VectorLayer(Layer):
    """Vector files from every source, merged into one MBTiles or PMTiles tile layer.

    When the sources have labels, each feature gets its source's label in a ``type``
    attribute (see ``to_mbtiles``).

    Attributes:
        min_zoom: Lowest zoom level to generate.
        max_zoom: Highest zoom level to generate.
        fields: Attributes to keep. ``None`` keeps all of them.
        where: Attribute filter, e.g. ``"STATUS = 'Designated'"``.
        open_options: GDAL open options. Only with a single input file.
        output_format: ``"MBTiles"`` or ``"PMTiles"``.
    """

    min_zoom: int = 0
    max_zoom: int = 12
    fields: tuple[str, ...] | None = None
    where: str | None = None
    open_options: Mapping[str, str] | None = None
    output_format: Literal["MBTiles", "PMTiles"] = "MBTiles"

    def __post_init__(self) -> None:
        """Check the options when the layer is created, not when it is built.

        Raises:
            ValueError: If there are no sources, ``min_zoom > max_zoom``, ``output_format``
                is unknown, or only some sources have a label.
        """
        super().__post_init__()
        if self.min_zoom > self.max_zoom:
            raise ValueError(
                f"min_zoom ({self.min_zoom}) is greater than max_zoom ({self.max_zoom})"
            )
        if self.output_format not in SUFFIXES:
            raise ValueError(f"output_format must be one of {', '.join(SUFFIXES)}")
        labelled = [source.label is not None for source in self.sources]
        if any(labelled) and not all(labelled):
            raise ValueError(f"layer {self.name!r}: give a label to every source, or to none")

    @property
    def suffix(self) -> str:
        """``".mbtiles"`` or ``".pmtiles"``, following ``output_format``."""
        return SUFFIXES[self.output_format]

    def convert(self, inputs: Sequence[Sequence[Path]], output: Path) -> Path:
        """Merge every source's files into one tile layer in ``output``.

        Args:
            inputs: The files of each source: ``inputs[i]`` are those of ``sources[i]``.
            output: The ``.mbtiles`` or ``.pmtiles`` file to write.

        Returns:
            ``output``.
        """
        files = [path for paths in inputs for path in paths]
        labels = None
        if self.sources[0].label is not None:
            # A source can return several files: each one gets its source's label.
            labels = [
                source.label
                for source, paths in zip(self.sources, inputs, strict=True)
                for _ in paths
            ]
        to_tiles = to_mbtiles if self.output_format == "MBTiles" else to_pmtiles
        return to_tiles(
            files,
            output,
            min_zoom=self.min_zoom,
            max_zoom=self.max_zoom,
            fields=self.fields,
            where=self.where,
            labels=labels,
            open_options=self.open_options,
        )
