"""Tests for the geopipe command line."""

import pytest

from vizz_geopipe import __version__
from vizz_geopipe.cli import main


def test_version_flag_prints_the_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out == f"geopipe {__version__}\n"


def test_no_arguments_returns_zero():
    assert main([]) == 0
