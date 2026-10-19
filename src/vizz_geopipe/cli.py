"""The ``geopipe`` command line."""

import argparse
from collections.abc import Sequence

from vizz_geopipe import __version__


def main(argv: Sequence[str] | None = None) -> int:
    """Run the ``geopipe`` command.

    Args:
        argv: Command-line arguments without the program name. ``None`` reads them from
            ``sys.argv``, which is what the installed ``geopipe`` script does.

    Returns:
        The process exit code.
    """
    parser = argparse.ArgumentParser(
        prog="geopipe", description="A command line interface for geopipe."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    parser.parse_args(argv)

    return 0
