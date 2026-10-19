# vizz-geopipe

Download, transform and publish map-ready geospatial data with GDAL.

Vizzuality projects repeatedly download raster and vector data, transform it and publish it
to Mapbox or a bucket. `vizz-geopipe` holds the generic parts of that work so each project
only declares its layers.

Status: early development (`0.x`). The GDAL tier is the first part being built.

## Requirements

- Python 3.12 or 3.13 and [uv](https://docs.astral.sh/uv/)
- GDAL 3.13 or newer on PATH (`brew install gdal`, or the `ghcr.io/osgeo/gdal` Docker image)

## Development

```bash
uv sync
uv run pre-commit install --hook-type pre-commit --hook-type commit-msg
uv run pytest
```

See `docs/style.md` for the code style.
