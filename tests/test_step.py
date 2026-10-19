"""Tests for a single GDAL pipeline step."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from vizz_geopipe.gdal._step import Step


def test_build_puts_positional_arguments_before_flags():
    step = Step.build("read", Path("in.shp"), open_options={"ENCODING": "ISO-8859-1"})

    assert step == Step("read", ("in.shp", "--oo", "ENCODING=ISO-8859-1"))


def test_build_without_arguments():
    assert Step.build("make-valid") == Step("make-valid")


def test_steps_cannot_be_changed():
    step = Step("read", ("in.shp",))

    with pytest.raises(FrozenInstanceError):
        step.name = "write"
