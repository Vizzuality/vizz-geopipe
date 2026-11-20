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

## Layers

A layer is one dataset built from its sources into one artifact: `VectorLayer` makes
MBTiles or PMTiles, `CogLayer` a Cloud Optimized GeoTIFF.

```python
from pathlib import Path

from vizz_geopipe.layers import VectorLayer
from vizz_geopipe.sources import HttpSource
from vizz_geopipe.workdir import Workdir

layer = VectorLayer(
    name="mangroves",
    title="Mangroves",
    sources=(HttpSource(url="https://example.com/mangroves.zip", files=("*.shp",)),),
    max_zoom=10,
)
workdir = Workdir(Path("data"))
if not layer.is_built(workdir):
    layer.build(workdir)  # Path("data/processed/mangroves/mangroves.mbtiles")
```

`is_built` is true when the artifact exists and was built from the layer as it is now:
change an option, a source's URL or its files and the layer must be built again; change
only `title` or `publish_to` and it does not. A build that fails keeps the previous
artifact in place. `build` logs its progress through `logging` (the `vizz_geopipe`
logger), which shows nothing until your script configures it, e.g. with
`logging.basicConfig(level=logging.INFO)`.

## Destinations

A destination is where an artifact is published: a Mapbox account, an S3 bucket or a
Google Cloud Storage bucket. `publish` takes a file and a name, and returns where the file
ended up.

```python
from pathlib import Path

from vizz_geopipe.destinations import MapboxDestination
from vizz_geopipe.destinations import S3Destination

mbtiles = Path("data/processed/mangroves/mangroves.mbtiles")

mapbox = MapboxDestination.from_env()
mapbox.publish(mbtiles, name="mangroves", title="Mangroves")  # "<user>.mangroves"

s3 = S3Destination(bucket="my-project-layers", prefix="layers/v1")
s3.publish(mbtiles, name="mangroves")  # "s3://my-project-layers/layers/v1/mangroves.mbtiles"
```

- `MapboxDestination.from_env()` reads `MAPBOX_USER` and `MAPBOX_TOKEN`. It publishes
  MBTiles only, and returns the tileset id once Mapbox has finished processing it.
- `S3Destination` and `GCSDestination` take `bucket`, `prefix` and an optional
  `public_base_url`; with it, `publish` returns the file's public URL instead of its
  `s3://` or `gs://` URI. They hold no credentials: S3 uses boto3's usual chain
  (environment variables, `~/.aws`, an instance role) and GCS Google's Application Default
  Credentials. `GCSDestination` needs the `gcs` extra, as `gs://` sources do.
- Every failure to publish is a `PublishError` (from `vizz_geopipe.errors`), naming the
  destination and the reason, and never a token.

## Development

```bash
uv sync
uv run pre-commit install --hook-type pre-commit --hook-type commit-msg
uv run pytest
```

See `docs/style.md` for the code style.
