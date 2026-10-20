"""The immutable builder shared by ``gdal vector pipeline`` and ``gdal raster pipeline``."""

import shlex
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path
from typing import ClassVar
from typing import Self

from vizz_geopipe.gdal._runner import run_gdal
from vizz_geopipe.gdal._step import Step


@dataclass(frozen=True)
class Pipeline:
    """A chain of GDAL pipeline steps. Every method returns a new pipeline.

    Pipelines never change once created, so a common start can be shared and extended in
    different ways. Subclasses set ``command`` and add one method per GDAL step they wrap;
    ``step()`` reaches the steps that are not wrapped.

    Attributes:
        steps: The steps so far, in order. The first one reads the input.
    """

    command: ClassVar[tuple[str, ...]] = ()
    steps: tuple[Step, ...] = ()

    def step(self, name: str, *positional: object, **options: object) -> Self:
        """Return a copy of this pipeline with one more step, wrapped or not.

        Args:
            name: GDAL step name, e.g. ``"explode-collections"``.
            *positional: Values that follow the step name, e.g. input paths.
            **options: Step options, turned into flags by ``to_flags``.
        """
        return replace(self, steps=(*self.steps, Step.build(name, *positional, **options)))

    def args(self) -> list[str]:
        """Return the arguments to pass to ``gdal``.

        Raises:
            ValueError: If the pipeline has no steps yet.
        """
        if not self.steps:
            raise ValueError("Start the pipeline with read(), concat() or mosaic().")
        args = [*self.command, "--quiet"]
        for step in self.steps:
            args += ["!", step.name, *step.args]
        return args

    def __str__(self) -> str:
        """Return the command as a shell line, to copy and run by hand when debugging."""
        return shlex.join(["gdal", *self.args()])

    def write(
        self, output: Path, *, config: Mapping[str, str] | None = None, **options: object
    ) -> Path:
        """Add the ``write`` step and run the pipeline.

        Args:
            output: File to write. Its folder is created if needed.
            config: GDAL configuration options for this run.
            **options: Write options, e.g. ``output_format="MBTiles"``, ``overwrite=True``,
                ``creation_options={"MINZOOM": 0}``.

        Returns:
            ``output``.

        Raises:
            GdalError: If GDAL fails.
        """
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        run_gdal(self.step("write", output, **options).args(), config=config)
        return output
