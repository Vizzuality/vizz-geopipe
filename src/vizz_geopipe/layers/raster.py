"""Layers of raster data, built as Cloud Optimized GeoTIFFs."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from vizz_geopipe.gdal import to_cog
from vizz_geopipe.layers._base import Layer


@dataclass(frozen=True, kw_only=True)
class CogLayer(Layer):
    """Rasters from every source, mosaicked into one Cloud Optimized GeoTIFF.

    Attributes:
        resampling: Resampling for overviews and reprojection, e.g. "nearest" or "mode"
            for categories, "average" for continuous values.
        nodata: Nodata value to set. ``None`` keeps the source's.
        dst_crs: CRS to reproject to. ``None`` keeps the source's.
        bbox: Area to keep, as ``(xmin, ymin, xmax, ymax)`` in EPSG:4326 degrees.
    """

    resampling: str = "average"
    nodata: float | None = None
    dst_crs: str | None = "EPSG:3857"
    bbox: tuple[float, float, float, float] | None = None

    @property
    def suffix(self) -> str:
        """``".tif"``."""
        return ".tif"

    def convert(self, inputs: Sequence[Sequence[Path]], output: Path) -> Path:
        """Mosaic every source's rasters into one COG in ``output``.

        Args:
            inputs: The files of each source: ``inputs[i]`` are those of ``sources[i]``.
            output: The ``.tif`` file to write.

        Returns:
            ``output``.
        """
        files = [path for paths in inputs for path in paths]

        return to_cog(
            files,
            output,
            resampling=self.resampling,
            nodata=self.nodata,
            dst_crs=self.dst_crs,
            bbox=self.bbox,
        )
