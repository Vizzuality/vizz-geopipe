"""One step of a ``gdal vector pipeline`` or ``gdal raster pipeline`` command."""

from dataclasses import dataclass

from vizz_geopipe.gdal._flags import to_flags


@dataclass(frozen=True)
class Step:
    """A pipeline step: its name and its command-line arguments.

    Attributes:
        name: GDAL step name, e.g. ``"read"`` or ``"make-valid"``.
        args: Arguments that follow the name on the command line.
    """

    name: str
    args: tuple[str, ...] = ()

    @classmethod
    def build(cls, name: str, *positional: object, **options: object) -> "Step":
        """Create a step from positional values (e.g. input paths) and keyword options."""
        return cls(name, (*(str(value) for value in positional), *to_flags(**options)))
