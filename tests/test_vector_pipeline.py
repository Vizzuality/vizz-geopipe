"""Tests for building gdal vector pipeline commands."""

from pathlib import Path

import pytest

from vizz_geopipe.gdal.vector import VectorPipeline


def test_read_starts_a_vector_pipeline():
    pipe = VectorPipeline.read(Path("in.gpkg"))

    assert pipe.args() == ["vector", "pipeline", "--quiet", "!", "read", "in.gpkg"]


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


def test_concat_reads_several_inputs():
    pipe = VectorPipeline.concat([Path("a.gpkg"), Path("b.gpkg")], mode="single")

    assert pipe.args()[3:] == ["!", "concat", "a.gpkg", "b.gpkg", "--mode", "single"]


def test_sql_puts_the_statement_first():
    pipe = VectorPipeline.read(Path("in.gpkg")).sql("SELECT name FROM t", dialect="SQLITE")

    assert pipe.args()[-4:] == ["sql", "SELECT name FROM t", "--dialect", "SQLITE"]


def test_step_reaches_any_gdal_step():
    pipe = VectorPipeline.read(Path("in.gpkg")).step("explode-collections")

    assert pipe.args()[-2:] == ["!", "explode-collections"]


def test_str_quotes_paths_with_spaces():
    pipe = VectorPipeline.read(Path("my data/in.gpkg"))

    assert pipe.args()[-1] == "my data/in.gpkg"
    assert str(pipe) == "gdal vector pipeline --quiet '!' read 'my data/in.gpkg'"


def test_a_pipeline_without_steps_cannot_run():
    with pytest.raises(ValueError, match="read"):
        VectorPipeline().args()


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
