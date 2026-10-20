"""Vector pipelines, and conversions of vector data to MBTiles and PMTiles."""

from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar
from typing import Self

from vizz_geopipe.gdal._pipeline import Pipeline


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
