"""Tests for running the gdal command, with a fake gdal so they run anywhere."""

import subprocess

import pytest

from vizz_geopipe.errors import GdalError
from vizz_geopipe.gdal import _runner

VERSION_OUTPUT = 'GDAL 3.13.0 "Iowa City", released 2026/05/04\n'


@pytest.fixture(autouse=True)
def forget_the_gdal_version():
    """Each test starts without a cached GDAL version, as if gdal had never been called."""
    _runner.gdal_version.cache_clear()
    yield
    _runner.gdal_version.cache_clear()


def fake_gdal(monkeypatch, *, version=VERSION_OUTPUT, returncode=0, stderr=""):
    """Replace ``subprocess.run`` with a fake gdal and return the list of commands it got."""
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        if command == ["gdal", "--version"]:
            return subprocess.CompletedProcess(command, 0, stdout=version, stderr="")
        return subprocess.CompletedProcess(command, returncode, stdout="", stderr=stderr)

    monkeypatch.setattr(subprocess, "run", fake_run)
    return commands


def test_run_gdal_runs_the_gdal_command(monkeypatch):
    commands = fake_gdal(monkeypatch)

    _runner.run_gdal(["vector", "info", "a.gpkg"])

    assert commands[-1] == ["gdal", "vector", "info", "a.gpkg"]


def test_a_failing_command_raises_gdal_error_with_its_stderr(monkeypatch):
    fake_gdal(monkeypatch, returncode=1, stderr="ERROR 4: nope.gpkg: No such file\n")

    with pytest.raises(GdalError, match="nope.gpkg") as error_info:
        _runner.run_gdal(["vector", "info", "nope.gpkg"])

    assert error_info.value.stderr == "ERROR 4: nope.gpkg: No such file"


def test_an_old_gdal_is_rejected(monkeypatch):
    fake_gdal(monkeypatch, version='GDAL 3.12.1 "Chicoutimi", released 2025/12/01\n')

    with pytest.raises(GdalError, match="3.12.1 is too old"):
        _runner.run_gdal(["vector", "info", "a.gpkg"])


def test_unreadable_version_output_raises_gdal_error(monkeypatch):
    fake_gdal(monkeypatch, version="something unexpected\n")

    with pytest.raises(GdalError, match="Could not read the GDAL version"):
        _runner.gdal_version()


def test_missing_gdal_raises_with_an_install_hint(monkeypatch):
    def gdal_not_installed(command, **kwargs):
        raise FileNotFoundError(command[0])

    monkeypatch.setattr(subprocess, "run", gdal_not_installed)

    with pytest.raises(GdalError, match="brew install gdal"):
        _runner.gdal_version()
