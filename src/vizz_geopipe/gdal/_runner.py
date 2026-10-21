"""Run the unified ``gdal`` command line. Every GDAL call in vizz-geopipe goes through here.

Keeping the subprocess call in one place means a switch to the GDAL Python bindings would
only change this module.
"""

import functools
import logging
import re
import shlex
import subprocess
from collections.abc import Mapping
from collections.abc import Sequence

from vizz_geopipe.errors import GdalError
from vizz_geopipe.gdal._flags import to_flags

logger = logging.getLogger(__name__)

MIN_VERSION = (3, 13)
INSTALL_HINT = (
    "Install GDAL 3.13 or newer: `brew install gdal` on macOS, the ghcr.io/osgeo/gdal "
    "Docker image, or conda-forge."
)


@functools.cache
def gdal_version() -> tuple[int, int, int]:
    """Return the installed GDAL version as ``(major, minor, patch)``.

    The result is cached: GDAL does not change while Python runs.

    Raises:
        GdalError: If ``gdal`` is not on PATH, cannot be run, or its version cannot be read.
    """
    command = ["gdal", "--version"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as error:
        raise GdalError(command, f"`gdal` could not be run ({error}). {INSTALL_HINT}") from error
    match = re.search(r"GDAL (\d+)\.(\d+)\.(\d+)", result.stdout)
    if match is None:
        output = (result.stdout + result.stderr).strip()
        raise GdalError(command, f"Could not read the GDAL version from {output!r}. {INSTALL_HINT}")
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def run_gdal(args: Sequence[str], config: Mapping[str, str] | None = None) -> None:
    """Run ``gdal <args>``.

    Args:
        args: Arguments after ``gdal``, e.g. ``["vector", "pipeline", ...]``.
        config: GDAL configuration options, e.g. ``{"GDAL_NUM_THREADS": "ALL_CPUS"}``.

    Raises:
        GdalError: If GDAL is missing or older than 3.13, or if the command fails.
    """
    version = gdal_version()
    if version[:2] < MIN_VERSION:
        installed = ".".join(str(part) for part in version)
        raise GdalError(["gdal", "--version"], f"GDAL {installed} is too old. {INSTALL_HINT}")
    command = ["gdal", *args, *to_flags(config=config)]
    logger.debug("Running %s", shlex.join(command))
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise GdalError(command, result.stderr.strip())
