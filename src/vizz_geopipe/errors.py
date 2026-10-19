"""Exceptions raised by vizz-geopipe."""

import shlex
from collections.abc import Sequence


class GdalError(RuntimeError):
    """A ``gdal`` command failed, or GDAL is missing or too old.

    Attributes:
        command: The full command that was run, starting with ``gdal``.
        stderr: What GDAL printed on standard error.
    """

    def __init__(self, command: Sequence[str], stderr: str) -> None:
        self.command = list(command)
        self.stderr = stderr
        # Only the first words of the command: the full one can be very long.
        super().__init__(f"`{shlex.join(self.command[:3])}` failed: {stderr}")
