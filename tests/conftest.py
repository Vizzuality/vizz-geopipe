"""Fixtures shared by all tests."""

import pytest

from vizz_geopipe.gdal import _pipeline


@pytest.fixture
def gdal_calls(monkeypatch) -> list[list[str]]:
    """Record pipeline runs instead of running gdal, and return the recorded arguments."""
    calls: list[list[str]] = []

    def record(args, config=None):
        calls.append(list(args))

    monkeypatch.setattr(_pipeline, "run_gdal", record)
    return calls
