"""Tests for building gdal vector pipeline commands."""

from pathlib import Path

from vizz_geopipe.gdal.vector import VectorPipeline


def test_steps_are_chained_in_order():
    pipe = (
        VectorPipeline.read(Path("in.shp"), open_options={"ENCODING": "ISO-8859-1"})
        .filter("STATUS = 'Designated'")
        .clip((-180.0, -85.0, 180.0, 85.0), bbox_crs="EPSG:4326")
        .make_valid(method="structure")
        .select(("name", "type"))
    )

    assert pipe.args() == [
        "vector", "pipeline", "--quiet",
        "!", "read", "in.shp", "--oo", "ENCODING=ISO-8859-1",
        "!", "filter", "--where", "STATUS = 'Designated'",
        "!", "clip", "--bbox", "-180.0,-85.0,180.0,85.0", "--bbox-crs", "EPSG:4326",
        "!", "make-valid", "--method", "structure",
        "!", "select", "--fields", "name,type",
    ]  # fmt: skip


def test_adding_a_step_leaves_the_original_unchanged():
    base = VectorPipeline.read(Path("in.gpkg"))

    filtered = base.filter("a = 1")

    assert len(base.steps) == 1
    assert len(filtered.steps) == 2


def test_str_quotes_paths_with_spaces():
    pipe = VectorPipeline.read(Path("my data/in.gpkg"))

    assert pipe.args()[-1] == "my data/in.gpkg"
    assert str(pipe) == "gdal vector pipeline --quiet '!' read 'my data/in.gpkg'"


def test_write_runs_the_pipeline_and_returns_the_output(gdal_calls, tmp_path):
    output = tmp_path / "out" / "a.gpkg"

    result = VectorPipeline.read(Path("in.gpkg")).write(output, overwrite=True)

    assert result == output
    assert output.parent.is_dir()
    assert gdal_calls == [
        [
            "vector",
            "pipeline",
            "--quiet",
            "!",
            "read",
            "in.gpkg",
            "!",
            "write",
            str(output),
            "--overwrite",
        ],
    ]
