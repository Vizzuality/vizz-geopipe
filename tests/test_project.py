"""Tests for a project: its configuration checks, which layers a call selects, and build."""

import logging
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

import pytest

from vizz_geopipe.destinations import Destination
from vizz_geopipe.destinations import MapboxDestination
from vizz_geopipe.errors import SourceError
from vizz_geopipe.layers import Layer
from vizz_geopipe.project import Project
from vizz_geopipe.sources import LocalSource


@dataclass(frozen=True, kw_only=True)
class FakeLayer(Layer):
    """Copies its sources' files into a ``.txt`` artifact; raises ``fail`` when built."""

    fail: str | None = None  # "source", "value" or "bug": SourceError, ValueError, TypeError

    @property
    def suffix(self) -> str:
        return ".txt"

    def convert(self, inputs, output):
        errors = {
            "source": lambda: SourceError("in.txt", "lost"),
            "value": lambda: ValueError("bad"),
            "bug": lambda: TypeError(),
        }
        if self.fail:
            raise errors[self.fail]()
        output.write_text("".join(path.read_text() for files in inputs for path in files))
        return output


@dataclass(frozen=True, kw_only=True)
class FakeDestination(Destination):
    """Records ``(name, title)`` per upload; raises ``OSError`` if ``fail``."""

    fail: bool = False
    uploads: list[tuple[str, str]] = field(default_factory=list)

    def _errors(self):
        return (OSError,)

    def _upload(self, artifact, name, title):
        if self.fail:
            raise OSError("disk on fire")
        self.uploads.append((name, title))
        return f"fake://{name}"


@pytest.fixture
def source(tmp_path) -> Path:
    """A text file with one line."""
    path = tmp_path / "in.txt"
    path.write_text("data")
    return path


@pytest.fixture
def layer(source):
    """Make a ``FakeLayer`` called ``name``, reading ``source``."""

    def make(name, **kwargs):
        sources = (LocalSource(files=(str(source),)),)
        return FakeLayer(name=name, title=name.title(), sources=sources, **kwargs)

    return make


def test_layer_names_must_be_unique(tmp_path, layer):
    with pytest.raises(ValueError, match="two layers are named 'x'"):
        Project(data_dir=tmp_path, layers=[layer("x"), layer("x")])


def test_layer_names_must_be_folder_names(tmp_path, layer):
    with pytest.raises(ValueError, match="layer 'a/b'"):
        Project(data_dir=tmp_path, layers=[layer("a/b")])


def test_publish_to_must_name_a_destination(tmp_path, layer):
    with pytest.raises(ValueError, match="layer 'x' publishes to 'mapbox'"):
        Project(data_dir=tmp_path, layers=[layer("x", publish_to=("mapbox",))])


def test_a_destination_must_accept_the_layer_suffix(tmp_path, layer):
    with pytest.raises(ValueError, match=r"layer 'x': MapboxDestination cannot publish \.txt"):
        Project(
            data_dir=tmp_path,
            layers=[layer("x", publish_to=("mapbox",))],
            destinations={"mapbox": MapboxDestination()},
        )


def test_a_destination_must_accept_the_layer_name(tmp_path, source):
    @dataclass(frozen=True, kw_only=True)
    class TilesLayer(FakeLayer):
        @property
        def suffix(self) -> str:
            return ".mbtiles"

    sources = (LocalSource(files=(str(source),)),)
    tiles = TilesLayer(name="a.b", title="A", sources=sources, publish_to=("mapbox",))

    with pytest.raises(ValueError, match=r"layer 'a\.b': invalid Mapbox tileset name"):
        Project(data_dir=tmp_path, layers=[tiles], destinations={"mapbox": MapboxDestination()})


def test_unknown_names_are_rejected(tmp_path, layer):
    project = Project(data_dir=tmp_path, layers=[layer("a")])

    with pytest.raises(ValueError, match="b, c"):
        project._select(["b", "a", "c"])


def test_unknown_destination_is_rejected(tmp_path, layer):
    project = Project(data_dir=tmp_path, layers=[layer("a")])

    with pytest.raises(ValueError, match="'nowhere'"):
        project._select(None, to="nowhere")


def test_selection_keeps_declaration_order(tmp_path, layer):
    project = Project(data_dir=tmp_path, layers=[layer("a"), layer("b"), layer("c")])

    selected = project._select(["c", "a"])

    assert [item.name for item in selected] == ["a", "c"]


def test_publishing_all_leaves_out_layers_with_nothing_to_publish(tmp_path, layer):
    project = Project(
        data_dir=tmp_path,
        layers=[layer("a"), layer("b", publish_to=("fake",))],
        destinations={"fake": FakeDestination()},
    )

    selected = project._select(None, publishing=True)

    assert [item.name for item in selected] == ["b"]


def test_publishing_a_named_layer_with_nothing_to_publish_is_rejected(tmp_path, layer):
    project = Project(data_dir=tmp_path, layers=[layer("a")])

    with pytest.raises(ValueError, match="'a'"):
        project._select(["a"], publishing=True)


def test_build_builds_every_layer(tmp_path, layer):
    project = Project(data_dir=tmp_path / "data", layers=[layer("a"), layer("b")])

    results = project.build()

    assert [(r.layer, r.step, r.outcome) for r in results] == [
        ("a", "build", "built"),
        ("b", "build", "built"),
    ]
    assert all(Path(r.detail).is_file() for r in results)


def test_an_unchanged_layer_is_skipped(tmp_path, layer):
    project = Project(data_dir=tmp_path / "data", layers=[layer("a")])
    project.build()

    results = project.build()

    assert [r.outcome for r in results] == ["skipped"]


def test_force_rebuilds_an_unchanged_layer(tmp_path, layer):
    project = Project(data_dir=tmp_path / "data", layers=[layer("a")])
    project.build()

    results = project.build(force=True)

    assert [r.outcome for r in results] == ["built"]


def test_refresh_rebuilds_an_unchanged_layer(tmp_path, layer):
    project = Project(data_dir=tmp_path / "data", layers=[layer("a")])
    project.build()

    results = project.build(refresh=True)

    assert [r.outcome for r in results] == ["built"]


def test_a_changed_source_is_rebuilt(tmp_path, layer, source):
    project = Project(data_dir=tmp_path / "data", layers=[layer("a")])
    project.build()
    source.write_text("new data")

    results = project.build()

    assert [r.outcome for r in results] == ["built"]


def test_a_failing_layer_does_not_stop_the_next(tmp_path, layer):
    project = Project(data_dir=tmp_path / "data", layers=[layer("a", fail="source"), layer("b")])

    results = project.build()

    assert [r.outcome for r in results] == ["failed", "built"]
    assert isinstance(results[0].error, SourceError)
    assert results[0].failed
    assert not results[1].failed


def test_a_value_error_during_a_build_is_a_failed_result(tmp_path, layer):
    project = Project(data_dir=tmp_path / "data", layers=[layer("a", fail="value")])

    results = project.build()

    assert [r.outcome for r in results] == ["failed"]
    assert results[0].detail == "bad"


def test_a_bug_propagates(tmp_path, layer):
    project = Project(data_dir=tmp_path / "data", layers=[layer("a", fail="bug")])

    with pytest.raises(TypeError):
        project.build()


def test_a_failure_is_logged_with_the_layer_name(tmp_path, layer, caplog):
    project = Project(data_dir=tmp_path / "data", layers=[layer("a", fail="source")])

    with caplog.at_level(logging.INFO):
        project.build()

    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert [r.getMessage() for r in errors] == ["a failed: in.txt: lost"]
