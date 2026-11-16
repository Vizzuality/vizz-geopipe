"""Tests for what every layer does: fetch, convert, move into place, record."""

import shutil
from dataclasses import dataclass

import pytest

from vizz_geopipe.layers import Layer
from vizz_geopipe.sources import LocalSource


@dataclass(frozen=True, kw_only=True)
class CopyLayer(Layer):
    """A layer whose artifact is a copy of its first input, or a failure if ``fail``."""

    fail: bool = False

    @property
    def suffix(self) -> str:
        return ".txt"

    def convert(self, inputs, output):
        output.write_text("half")
        if self.fail:
            raise RuntimeError("conversion failed")
        shutil.copy(inputs[0][0], output)
        return output


@pytest.fixture
def layer(tmp_path) -> CopyLayer:
    (tmp_path / "in.txt").write_text("data")
    source = LocalSource(files=(str(tmp_path / "in.txt"),))
    return CopyLayer(name="notes", title="Notes", sources=(source,))


def test_build_puts_the_artifact_in_processed(workdir, layer):
    artifact = layer.build(workdir)

    assert artifact == workdir.root / "processed" / "notes" / "notes.txt"
    assert artifact.read_text() == "data"


def test_a_built_layer_is_built(workdir, layer):
    layer.build(workdir)

    assert layer.is_built(workdir)


def test_changing_an_option_makes_the_layer_not_built(workdir, layer):
    layer.build(workdir)
    changed = CopyLayer(name="notes", title="Notes", sources=layer.sources, fail=True)

    assert not changed.is_built(workdir)


def test_changing_the_title_keeps_the_layer_built(workdir, layer):
    layer.build(workdir)

    assert CopyLayer(name="notes", title="New title", sources=layer.sources).is_built(workdir)


def test_failed_build_keeps_the_previous_artifact(workdir, layer):
    layer.build(workdir)
    failing = CopyLayer(name="notes", title="Notes", sources=layer.sources, fail=True)

    with pytest.raises(RuntimeError):
        failing.build(workdir)

    assert layer.artifact(workdir).read_text() == "data"
    assert list((workdir.root / "tmp").iterdir()) == []


def test_a_layer_needs_a_source():
    with pytest.raises(ValueError):
        CopyLayer(name="notes", title="Notes", sources=())
