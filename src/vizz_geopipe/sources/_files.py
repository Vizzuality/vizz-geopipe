"""Write, download and extract the files of a source."""

import tempfile
import zipfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

import requests

from vizz_geopipe.errors import SourceError

CHUNK_SIZE = 1024 * 1024


@contextmanager
def atomic_write(path: Path) -> Generator[BinaryIO, None, None]:
    """Open a file to write ``path``, which only appears there once writing has finished.

    Writes go to a temporary file next to ``path``. When the ``with`` block ends normally the
    temporary file is renamed to ``path``; when it raises, the temporary file is deleted. So
    ``path`` is never half written, and an interrupted download cannot pass for a finished one.

    Args:
        path: The file to write. Its folder is created if needed.

    Yields:
        The temporary file, opened for writing bytes.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # In the same folder as ``path``: a rename is only atomic within one file system.
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as file:
        temporary = Path(file.name)
        try:
            yield file
        except BaseException:
            file.close()
            temporary.unlink()
            raise
    temporary.replace(path)


def download_file(url: str, path: Path, *, timeout: float = 60) -> Path:
    """Download ``url`` to ``path``, streaming it in chunks.

    Args:
        url: The URL to download.
        path: Where to write it. Its folder is created if needed.
        timeout: Seconds to wait for the server to connect or send data.

    Returns:
        ``path``.

    Raises:
        SourceError: If the server cannot be reached or answers with an error status.
    """
    try:
        with requests.get(url, stream=True, timeout=timeout) as response:
            response.raise_for_status()
            with atomic_write(path) as file:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    file.write(chunk)
    except requests.RequestException as error:
        raise SourceError(url, str(error)) from error
    return path


def extract_zips(archive: Path, dest: Path) -> None:
    """Extract ``archive`` into ``dest``, then the zips it contained, and delete the zips.

    A zip found inside is extracted into a folder next to it with the same name, without
    ``.zip`` (``inner.zip`` into ``inner/``). Only one level of nesting is extracted.

    Args:
        archive: The zip file to extract.
        dest: The folder to extract into. It is created if needed.
    """
    _unzip(archive, dest)
    for nested in sorted(dest.rglob("*.zip")):
        _unzip(nested, nested.with_suffix(""))


def _unzip(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as opened:
        opened.extractall(dest)
    archive.unlink()
