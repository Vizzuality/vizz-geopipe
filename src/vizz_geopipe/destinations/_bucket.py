"""What S3 and Google Cloud Storage destinations share: object keys, URLs, content types."""

import mimetypes
from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from vizz_geopipe.destinations._base import Destination

# Types that mimetypes does not know, or guesses differently on each system.
CONTENT_TYPES = {
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".pmtiles": "application/vnd.pmtiles",
    ".mbtiles": "application/vnd.sqlite3",
}


def content_type(path: Path) -> str:
    """Return the ``Content-Type`` to store ``path`` with, from its suffix."""
    known = CONTENT_TYPES.get(path.suffix.lower())
    return known or mimetypes.guess_type(path.name)[0] or "application/octet-stream"


@dataclass(frozen=True, kw_only=True)
class _BucketDestination(Destination):
    """A bucket: each file becomes the object ``<prefix>/<name><suffix>``.

    A subclass sets ``scheme`` and writes ``_put``, the upload itself.

    Attributes:
        bucket: The bucket's name, e.g. ``"my-project-layers"``.
        prefix: The folder inside the bucket, e.g. ``"layers/v1"``. Empty for the top.
        public_base_url: The public URL of the bucket and prefix's parent, e.g.
            ``"https://cdn.example.com"``. When set, ``publish`` returns the public URL of
            the object instead of its ``s3://`` or ``gs://`` URI.
    """

    scheme: ClassVar[str]

    bucket: str
    prefix: str = ""
    public_base_url: str | None = None

    def __post_init__(self) -> None:
        """Check the bucket name when the destination is created.

        Raises:
            ValueError: If ``bucket`` is empty or contains ``/`` (a folder belongs in
                ``prefix``).
        """
        if not self.bucket or "/" in self.bucket:
            raise ValueError(
                f"invalid bucket {self.bucket!r}: give the bucket's name only, "
                "and any folder as prefix"
            )

    def key(self, name: str, suffix: str) -> str:
        """Return the object key for ``name``: ``<prefix>/<name><suffix>``."""
        return "/".join(part for part in (self.prefix.strip("/"), f"{name}{suffix}") if part)

    def _upload(self, artifact: Path, name: str, title: str) -> str:
        """Upload ``artifact`` under its key and return its URL or URI."""
        key = self.key(name, artifact.suffix)
        self._put(artifact, key, content_type(artifact))
        if self.public_base_url:
            return f"{self.public_base_url.rstrip('/')}/{key}"
        return f"{self.scheme}://{self.bucket}/{key}"

    @abstractmethod
    def _put(self, artifact: Path, key: str, content_type: str) -> None:
        """Upload ``artifact`` to ``key`` in the bucket, stored as ``content_type``."""
