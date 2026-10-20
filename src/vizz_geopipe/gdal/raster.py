"""Raster pipelines, and conversion of rasters to Cloud Optimized GeoTIFFs."""

from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar
from typing import Self

from vizz_geopipe.gdal._pipeline import Pipeline


class RasterPipeline(Pipeline):
    """A ``gdal raster pipeline`` command, built one step at a time."""

    command: ClassVar[tuple[str, ...]] = ("raster", "pipeline")

    @classmethod
    def read(cls, path: Path, **options: object) -> Self:
        """Start by reading one raster."""
        return cls().step("read", path, **options)

    @classmethod
    def mosaic(cls, paths: Sequence[Path], **options: object) -> Self:
        """Start by mosaicking several rasters into one."""
        return cls().step("mosaic", *paths, **options)

    def reproject(self, dst_crs: str, resampling: str | None = None) -> Self:
        """Reproject to ``dst_crs``, e.g. ``"EPSG:3857"``, with a resampling method."""
        return self.step("reproject", dst_crs=dst_crs, resampling=resampling)

    def clip(self, bbox: Sequence[float], bbox_crs: str | None = None) -> Self:
        """Clip to ``(xmin, ymin, xmax, ymax)``, in ``bbox_crs`` or the raster's CRS."""
        return self.step("clip", bbox=bbox, bbox_crs=bbox_crs)

    def resize(self, size: tuple[int, int], resampling: str | None = None) -> Self:
        """Resize to ``(width, height)`` pixels."""
        return self.step("resize", size=size, resampling=resampling)

    def edit(self, nodata: float | None = None, crs: str | None = None) -> Self:
        """Set the nodata value, or override the CRS without reprojecting."""
        return self.step("edit", nodata=nodata, crs=crs)
