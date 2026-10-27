"""Fingerprints of what shapes a layer, and the records that say what was built and published."""

import hashlib
import json
from collections.abc import Mapping
from collections.abc import Sequence
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

from vizz_geopipe.sources._files import atomic_write

BUILD_RECORD = ".build.json"
PUBLISH_RECORD = ".published.json"


def build_fingerprint(config: Mapping[str, object], identities: Sequence[Mapping[str, str]]) -> str:
    """Return a short text that changes whenever the configuration or the sources change.

    Args:
        config: Everything about a layer that shapes its artifact.
        identities: The ``identity()`` of each of the layer's sources, in order.

    Returns:
        The SHA-256 hex digest of the configuration and the identities, as JSON.
    """
    # sort_keys: the same configuration must give the same text, whatever order its keys
    # were written in. default=str: paths and other values JSON does not know become text.
    text = json.dumps({"config": config, "sources": identities}, sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()


def read_build(folder: Path) -> str | None:
    """Return the fingerprint of the last build in ``folder``.

    Args:
        folder: The folder the artifact was built in.

    Returns:
        The recorded fingerprint, or ``None`` if the record is missing, is not JSON, or has
        no fingerprint.
    """
    return _read(folder / BUILD_RECORD).get("fingerprint")


def write_build(folder: Path, fingerprint: str) -> None:
    """Record that ``folder`` holds a build with ``fingerprint``, and when it was built.

    Args:
        folder: The folder the artifact was built in. It must exist.
        fingerprint: The build's fingerprint, from ``build_fingerprint``.
    """
    record = {"fingerprint": fingerprint, "built_at": datetime.now(UTC).isoformat()}
    with atomic_write(folder / BUILD_RECORD) as file:
        file.write(json.dumps(record, indent=2).encode())


def read_published(folder: Path, destination: str) -> str | None:
    """Return the fingerprint last published from ``folder`` to ``destination``.

    Args:
        folder: The folder the artifact was built in.
        destination: The name of the destination.

    Returns:
        The recorded fingerprint, or ``None`` if the record is missing, is not JSON, or the
        artifact was never published to ``destination``.
    """
    return _read(folder / PUBLISH_RECORD).get(destination, {}).get("fingerprint")


def write_published(folder: Path, destination: str, fingerprint: str, uri: str) -> None:
    """Record that the build with ``fingerprint`` was published to ``destination``.

    The records of other destinations are kept.

    Args:
        folder: The folder the artifact was built in. It must exist.
        destination: The name of the destination.
        fingerprint: The fingerprint of the build that was published.
        uri: Where the destination put it (a tileset id, an object URI).
    """
    record = _read(folder / PUBLISH_RECORD)
    record[destination] = {
        "fingerprint": fingerprint,
        "uri": uri,
        "published_at": datetime.now(UTC).isoformat(),
    }
    with atomic_write(folder / PUBLISH_RECORD) as file:
        file.write(json.dumps(record, indent=2).encode())


def _read(path: Path) -> dict[str, Any]:
    """Return the JSON record at ``path``, or ``{}`` if it is missing or not JSON."""
    try:
        return json.loads(path.read_text())
    # A missing or half-written record is no record.
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
