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


COG_CREATION_OPTIONS = {
    "COMPRESS": "ZSTD",
    "BLOCKSIZE": 512,
    "NUM_THREADS": "ALL_CPUS",
}
"""COG options shared by every output, ready for TiTiler.
"""


def to_cog(
    inputs: Sequence[Path],
    output: Path,
    *,
    resampling: str = "average",
    nodata: float | None = None,
    dst_crs: str | None = "EPSG:3857",
    bbox: tuple[float, float, float, float] | None = None,
) -> Path:
    """Convert one raster, or a mosaic of several, to a Cloud Optimized GeoTIFF.

    Steps, in order: read (or mosaic), set nodata, clip to ``bbox``, reproject, write. Clip
    comes before reproject because clipping a reprojected raster at its edge fails.

    Args:
        inputs: Rasters to convert. Several are mosaicked first.
        output: The COG to write. An existing file is replaced.
        resampling: Resampling for overviews and reprojection, e.g. "nearest" or "mode"
            for categories, "average" for continuous values.
        nodata: Nodata value to set. ``None`` keeps the source's.
        dst_crs: CRS to reproject to before writing. Web Mercator by default, the CRS of
            web maps. ``None`` keeps the source's, e.g. for analysis.
        bbox: Area to keep, as ``(xmin, ymin, xmax, ymax)`` in EPSG:4326 degrees.

    Returns:
        ``output``.

    Raises:
        ValueError: If ``inputs`` is empty.
        GdalError: If GDAL fails.
    """
    if not inputs:
        raise ValueError("Give at least one input.")

    if len(inputs) == 1:
        pipe = RasterPipeline.read(inputs[0])
    else:
        pipe = RasterPipeline.mosaic(inputs)
    if nodata is not None:
        pipe = pipe.edit(nodata=nodata)
    if bbox is not None:
        pipe = pipe.clip(bbox, bbox_crs="EPSG:4326")
    if dst_crs is not None:
        pipe = pipe.reproject(dst_crs=dst_crs, resampling=resampling)
    return pipe.write(
        output,
        output_format="COG",
        overwrite=True,
        creation_options={**COG_CREATION_OPTIONS, "OVERVIEW_RESAMPLING": resampling},
    )
