"""Tests for the project data folders."""

import pytest

from vizz_geopipe.workdir import Workdir


def test_raw_dir_is_created_under_root(tmp_path):
    raw = Workdir(tmp_path).raw_dir("mangroves")

    assert raw == tmp_path / "raw" / "mangroves"
    assert raw.is_dir()


@pytest.mark.parametrize("name", ["", ".", "..", "../outside", "a/b"])
def test_rejects_names_that_are_not_one_folder(tmp_path, name):
    with pytest.raises(ValueError):
        Workdir(tmp_path).raw_dir(name)
