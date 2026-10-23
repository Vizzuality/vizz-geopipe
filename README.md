# vizz-geopipe

Download, transform and publish map-ready geospatial data with GDAL.

Vizzuality projects repeatedly download raster and vector data, transform it and publish it
to Mapbox or a bucket. `vizz-geopipe` holds the generic parts of that work so each project
only declares its layers.

Status: early development (`0.x`). The GDAL tier is the first part being built.

## Requirements

- Python 3.12 or 3.13 and [uv](https://docs.astral.sh/uv/)
- GDAL 3.13 or newer on PATH (`brew install gdal`, or the `ghcr.io/osgeo/gdal` Docker image)

## Quickstart: the GDAL tier

```bash
uv add "vizz-geopipe @ git+https://github.com/Vizzuality/vizz-geopipe"
```

```python
from pathlib import Path

from vizz_geopipe.gdal import VectorPipeline
from vizz_geopipe.gdal import to_cog
from vizz_geopipe.gdal import to_mbtiles

# Ready-made conversions
to_mbtiles([Path("protected_areas.gpkg")], Path("out/protected_areas.mbtiles"), max_zoom=10)
to_cog([Path("forest_cover.tif")], Path("out/forest_cover.tif"), resampling="nearest")

# Or build any gdal pipeline step by step
pipe = VectorPipeline.read(Path("roads.gpkg")).filter("type = 'primary'").reproject("EPSG:3857")
print(pipe)  # the exact gdal command, to run by hand when debugging
pipe.write(Path("out/primary_roads.gpkg"), overwrite=True)
```

## Sources

A source gets a layer's data into a folder and returns the files to read: `HttpSource`
(a URL, zips extracted), `LocalSource` (files on this computer), `BucketSource` (`s3://` or
`gs://` objects) and `TileIndexSource` (a raster split into tiles).

```python
from pathlib import Path

from vizz_geopipe.sources import HttpSource

source = HttpSource(url="https://example.com/mangroves.zip", files=("*.shp",))
paths = source.fetch(Path("data/raw/mangroves/0"))  # [Path("data/raw/mangroves/0/mangroves.shp")]
```

A fetch downloads again only when the source changes (another URL, a replaced bucket
object) or a file is missing; `fetch(dest, refresh=True)` forces it. A download first
deletes everything in `dest`, so give each source a folder of its own.

Reading `gs://` buckets needs the `gcs` extra:

```bash
uv add "vizz-geopipe[gcs] @ git+https://github.com/Vizzuality/vizz-geopipe"
```

## Development

```bash
uv sync
uv run pre-commit install --hook-type pre-commit --hook-type commit-msg
uv run pytest
```

See `docs/style.md` for the code style.
