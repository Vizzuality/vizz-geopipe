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


class SourceError(RuntimeError):
    """A source could not be fetched.

    Attributes:
        source: The URL, URI or path of the source.
        reason: What went wrong.
    """

    def __init__(self, source: str, reason: str) -> None:
        self.source = source
        self.reason = reason
        super().__init__(f"{source}: {reason}")


class PublishError(RuntimeError):
    """An artifact could not be published.

    Attributes:
        destination: The destination's name, e.g. ``"mapbox"``.
        reason: What went wrong.
    """

    def __init__(self, destination: str, reason: str) -> None:
        self.destination = destination
        self.reason = reason
        super().__init__(f"{destination}: {reason}")
