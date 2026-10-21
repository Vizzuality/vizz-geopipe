"""Vector pipelines, and conversions of vector data to MBTiles and PMTiles."""

from collections.abc import Mapping
from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar
from typing import Self

from vizz_geopipe.gdal._pipeline import Pipeline

WEB_MERCATOR_BBOX = (-180.0, -85.0511287798066, 180.0, 85.0511287798066)
"""The area Web Mercator can show, in degrees. Vertices beyond it cannot be projected."""


class VectorPipeline(Pipeline):
    """A ``gdal vector pipeline`` command, built one step at a time.

    Example:
        >>> VectorPipeline.read(Path("in.gpkg")).filter("pop > 0").args()[-3:]
        ['filter', '--where', 'pop > 0']
    """

    command: ClassVar[tuple[str, ...]] = ("vector", "pipeline")

    @classmethod
    def read(cls, path: Path, **options: object) -> Self:
        """Start by reading one dataset, e.g. with ``open_options={"ENCODING": "UTF-8"}``."""
        return cls().step("read", path, **options)

    @classmethod
    def concat(cls, paths: Sequence[Path], **options: object) -> Self:
        """Start by reading several datasets as one, e.g. with ``mode="single"``."""
        return cls().step("concat", *paths, **options)

    def filter(self, where: str) -> Self:
        """Keep the features matching an attribute filter, e.g. ``"pop > 0"``."""
        return self.step("filter", where=where)

    def clip(self, bbox: Sequence[float], bbox_crs: str | None = None) -> Self:
        """Clip to ``(xmin, ymin, xmax, ymax)``, in ``bbox_crs`` or the layer's CRS."""
        return self.step("clip", bbox=bbox, bbox_crs=bbox_crs)

    def make_valid(self, method: str | None = None) -> Self:
        """Repair invalid geometries, e.g. with ``method="structure"``."""
        return self.step("make-valid", method=method)

    def select(self, fields: Sequence[str]) -> Self:
        """Keep only ``fields``. List ``"_ogr_geometry_"`` to keep the geometry too."""
        return self.step("select", fields=tuple(fields))

    def sql(self, statement: str, dialect: str | None = None) -> Self:
        """Replace the features with the result of an SQL statement."""
        return self.step("sql", statement, dialect=dialect)

    def reproject(self, dst_crs: str) -> Self:
        """Reproject to ``dst_crs``, e.g. ``"EPSG:3857"``."""
        return self.step("reproject", dst_crs=dst_crs)

    def simplify(self, tolerance: float) -> Self:
        """Simplify geometries with a distance tolerance in the layer's units."""
        return self.step("simplify", tolerance)


def to_mbtiles(
    inputs: Sequence[Path],
    output: Path,
    *,
    min_zoom: int = 0,
    max_zoom: int = 12,
    fields: Sequence[str] | None = None,
    where: str | None = None,
    labels: Sequence[str] | None = None,
    open_options: Mapping[str, str] | None = None,
    layer_name: str | None = None,
) -> Path:
    """Convert one or more vector files (GeoJSON, GPKG, SHP, ...) to an MBTiles file.

    Several inputs are merged into one tile layer. Features are clipped to the Web Mercator
    latitude limits and invalid geometries are repaired. An existing ``output`` is replaced.

    Args:
        inputs: Vector files to convert.
        output: The ``.mbtiles`` file to write.
        min_zoom: Lowest zoom level to generate.
        max_zoom: Highest zoom level to generate.
        fields: Attributes to keep. ``None`` keeps all of them. Include ``"type"`` to keep
            the labels.
        where: Attribute filter, e.g. ``"STATUS = 'Designated'"``.
        labels: One value per input, written to a ``type`` attribute. With labels, only
            the attributes found in every input are kept.
        open_options: GDAL open options, e.g. ``{"ENCODING": "ISO-8859-1"}``. Only with a
            single input.
        layer_name: Name of the tile layer. Defaults to the stem of ``output``.

    Returns:
        ``output``.

    Raises:
        ValueError: If there are no inputs, ``labels`` does not match ``inputs``,
            ``open_options`` is given with several inputs, or ``min_zoom > max_zoom``.
        GdalError: If GDAL fails.
    """
    return _to_vector_tiles(
        "MBTiles", inputs, output, min_zoom=min_zoom, max_zoom=max_zoom, fields=fields,
        where=where, labels=labels, open_options=open_options, layer_name=layer_name,
    )  # fmt: skip


def to_pmtiles(
    inputs: Sequence[Path],
    output: Path,
    *,
    min_zoom: int = 0,
    max_zoom: int = 12,
    fields: Sequence[str] | None = None,
    where: str | None = None,
    labels: Sequence[str] | None = None,
    open_options: Mapping[str, str] | None = None,
    layer_name: str | None = None,
) -> Path:
    """Convert one or more vector files to a PMTiles file, like ``to_mbtiles``.

    PMTiles can be served straight from a bucket, without a tile server.
    """
    return _to_vector_tiles(
        "PMTiles", inputs, output, min_zoom=min_zoom, max_zoom=max_zoom, fields=fields,
        where=where, labels=labels, open_options=open_options, layer_name=layer_name,
    )  # fmt: skip


def _to_vector_tiles(
    output_format: str,
    inputs: Sequence[Path],
    output: Path,
    *,
    min_zoom: int,
    max_zoom: int,
    fields: Sequence[str] | None,
    where: str | None,
    labels: Sequence[str] | None,
    open_options: Mapping[str, str] | None,
    layer_name: str | None,
) -> Path:
    if not inputs:
        raise ValueError("Give at least one input.")
    if labels is not None and len(labels) != len(inputs):
        raise ValueError("labels must have one value per input.")
    if open_options and len(inputs) > 1:
        raise ValueError("open_options are only supported with a single input.")
    if min_zoom > max_zoom:
        raise ValueError(f"min_zoom ({min_zoom}) is greater than max_zoom ({max_zoom}).")
    output = Path(output)
    layer = layer_name or output.stem

    if len(inputs) == 1 and labels is None:
        pipe = VectorPipeline.read(inputs[0], open_options=open_options)
    else:
        labelled = labels is not None
        pipe = VectorPipeline.concat(
            inputs,
            mode="single",
            field_strategy="intersection" if labelled else None,
            output_layer=layer,
            source_layer_field_name="_source" if labelled else None,
            source_layer_field_content="{DS_INDEX}" if labelled else None,
        )
    if labels is not None:
        pipe = pipe.sql(_label_statement(labels, layer), dialect="SQLITE")
        pipe = pipe.step("select", fields="_source", exclude=True)
    if where:
        pipe = pipe.filter(where)
    pipe = pipe.make_valid(method="structure").clip(WEB_MERCATOR_BBOX, bbox_crs="EPSG:4326")
    if fields:
        pipe = pipe.select((*fields, "_ogr_geometry_"))
    return pipe.write(
        output,
        output_format=output_format,
        overwrite=True,
        output_layer=layer,
        creation_options={"MINZOOM": min_zoom, "MAXZOOM": max_zoom},
    )


def _label_statement(labels: Sequence[str], layer: str) -> str:
    """Return SQL that adds a ``type`` attribute holding each input's label."""
    cases = " ".join(
        f"WHEN '{index}' THEN {_sql_string(label)}" for index, label in enumerate(labels)
    )
    return f'SELECT *, CASE _source {cases} END AS type FROM "{layer}"'


def _sql_string(value: str) -> str:
    """Quote ``value`` as an SQL string, doubling the quotes inside it (``d'I`` to ``'d''I'``)."""
    return "'" + value.replace("'", "''") + "'"
