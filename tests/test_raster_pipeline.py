"""Tests for building gdal raster pipeline commands."""

from pathlib import Path

from vizz_geopipe.gdal.raster import RasterPipeline


def test_read_starts_a_raster_pipeline():
    pipe = RasterPipeline.read(Path("in.tif"))

    assert pipe.args() == ["raster", "pipeline", "--quiet", "!", "read", "in.tif"]


def test_mosaic_reads_several_inputs():
    pipe = RasterPipeline.mosaic([Path("a.tif"), Path("b.tif")])

    assert pipe.args()[3:] == ["!", "mosaic", "a.tif", "b.tif"]


def test_clip_adds_bbox_and_crs():
    pipe = RasterPipeline.read(Path("in.tif")).clip(
        bbox=(-180.0, -85.0, 180.0, 85.0), bbox_crs="EPSG:4326"
    )

    assert pipe.args()[6:] == [
        "!",
        "clip",
        "--bbox",
        "-180.0,-85.0,180.0,85.0",
        "--bbox-crs",
        "EPSG:4326",
    ]


def test_resize_produces_width_and_height():
    pipe = RasterPipeline.read(Path("in.tif")).resize(size=(256, 256), resampling="bilinear")

    assert pipe.args()[6:] == ["!", "resize", "--size", "256,256", "--resampling", "bilinear"]


def test_adding_a_step_leaves_the_original_unchanged():
    base = RasterPipeline.read(Path("in.tif"))

    resized = base.resize(size=(256, 256))

    assert len(base.steps) == 1
    assert len(resized.steps) == 2


def test_edit_keeps_zero_nodata():
    pipe = RasterPipeline.read(Path("in.tif")).edit(nodata=0)

    assert pipe.args()[-4:] == ["!", "edit", "--nodata", "0"]


def test_optional_arguments_left_out_add_no_flags():
    pipe = RasterPipeline.read(Path("in.tif")).reproject("EPSG:3857")

    assert pipe.args()[-4:] == ["!", "reproject", "--dst-crs", "EPSG:3857"]


def test_write_runs_the_pipeline_and_returns_the_output(gdal_calls, tmp_path):
    output = tmp_path / "out" / "in.tif"

    result = RasterPipeline.read(Path("in.tif")).write(output, overwrite=True)

    assert result == output
    assert output.parent.is_dir()
    assert gdal_calls == [
        [
            "raster",
            "pipeline",
            "--quiet",
            "!",
            "read",
            "in.tif",
            "!",
            "write",
            str(output),
            "--overwrite",
        ],
    ]
