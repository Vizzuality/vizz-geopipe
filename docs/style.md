# Code style

These rules keep the codebase consistent. Ruff enforces the mechanical ones; the rest are
checked in review.

## Docstrings

We use Google-style docstrings.

- Every module starts with a docstring saying what the module is for.
- Every public class and function has a docstring. Private helpers (`_name`) get one only
  when the name is not enough.
- First line: a one-sentence summary, ending with a period. Then a blank line, then details.
- Use `Args:`, `Returns:` and `Raises:` sections when they add information. Do not repeat
  what the type hints already say.
- Dataclass fields are documented in the class docstring under `Attributes:`.

```python
def to_cog(inputs: Sequence[Path], output: Path, *, resampling: str = "average") -> Path:
    """Convert one raster, or a mosaic of several, to a Cloud Optimized GeoTIFF.

    Args:
        inputs: Rasters to convert. Several are mosaicked first.
        output: Destination file. An existing file is replaced.
        resampling: Overview resampling method, e.g. "nearest" for categories.

    Returns:
        The path of the written COG.

    Raises:
        GdalError: If GDAL fails.
    """
```

## Type hints

Every function signature and dataclass field has type hints. Use built-in generics
(`list[str]`, `dict[str, int]`), `X | None` instead of `Optional[X]`, and
`collections.abc` types (`Sequence`, `Mapping`) for arguments.

## Comments

Comments explain why the code is the way it is, never what it does. If a comment is needed
to explain what a line does, rename or split the code instead.

## Imports

One import per line (`from x import a` and `from x import b` on separate lines). Ruff sorts
them.

## Text

- No em-dashes or en-dashes; use a colon, a semicolon, a comma, parentheses or two
  sentences. No section sign; write "Section 4.1".
- Line length 100.

## Tests

- Plain `test_*` functions, no test classes.
- One behaviour per test, named after the behaviour (`test_zero_is_kept`).
- Arrange, act, assert, in that order, separated by blank lines when the test is longer
  than three lines.
- Tests that run the real `gdal` are marked `@pytest.mark.gdal`.
