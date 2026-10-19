"""Tests for the project data folders."""

from dataclasses import FrozenInstanceError

import pytest

from vizz_geopipe.workdir import Workdir


def test_raw_dir_is_created_under_root(tmp_path):
    raw = Workdir(tmp_path).raw_dir("mangroves")

    assert raw == tmp_path / "raw" / "mangroves"
    assert raw.is_dir()


def test_processed_dir_is_created_under_root(tmp_path):
    processed = Workdir(tmp_path).processed_dir("mangroves")

    assert processed == tmp_path / "processed" / "mangroves"
    assert processed.is_dir()


def test_tmp_dir_is_created_under_root(tmp_path):
    assert Workdir(tmp_path).tmp_dir() == tmp_path / "tmp"
    assert (tmp_path / "tmp").is_dir()


def test_asking_twice_returns_the_same_folder(tmp_path):
    workdir = Workdir(tmp_path)

    assert workdir.raw_dir("a") == workdir.raw_dir("a")


@pytest.mark.parametrize("name", ["", ".", "..", "../outside", "a/b"])
def test_rejects_names_that_are_not_one_folder(tmp_path, name):
    with pytest.raises(ValueError):
        Workdir(tmp_path).raw_dir(name)


def test_workdir_cannot_be_changed(tmp_path):
    workdir = Workdir(tmp_path)

    with pytest.raises(FrozenInstanceError):
        workdir.root = tmp_path / "other"
