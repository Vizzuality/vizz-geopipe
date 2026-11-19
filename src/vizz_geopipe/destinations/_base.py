"""The interface every destination follows, and the publish shared by all of them."""

import logging
from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from vizz_geopipe.errors import PublishError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class Destination(ABC):
    """Somewhere a built artifact is published: a Mapbox account, an S3 or GCS bucket.

    ``publish`` is written once, here: check the call, check the file, upload, and turn
    the service's errors into ``PublishError``. A subclass writes ``_upload`` and lists
    the errors its service raises in ``_errors``.

    Attributes:
        suffixes: The file suffixes this destination accepts. ``None`` accepts any file.
    """

    suffixes: ClassVar[frozenset[str] | None] = None

    def accepts(self, artifact: Path) -> bool:
        """Return whether this destination can publish a file like ``artifact``."""
        return self.suffixes is None or artifact.suffix in self.suffixes

    def validate(self, name: str) -> None:
        """Check that ``name`` can be published here. Nothing to check by default.

        Raises:
            ValueError: In a subclass, if the destination cannot use ``name``.
        """
        return None

    def publish(self, artifact: Path, *, name: str, title: str | None = None) -> str:
        """Publish ``artifact`` under ``name``.

        Args:
            artifact: The file to publish.
            name: The name to publish it under, e.g. a layer's name.
            title: A human-readable name, where the destination shows one. Defaults to
                ``name``.

        Returns:
            Where it was published: a tileset id or a URI.

        Raises:
            ValueError: If this destination does not accept the file's suffix, or
                cannot use ``name``.
            PublishError: If ``artifact`` is not a file, or the upload fails.
        """
        destination = type(self).__name__
        if not self.accepts(artifact):
            accepted = ", ".join(sorted(self.suffixes or ()))
            raise ValueError(
                f"{destination} cannot publish {artifact.suffix or 'files without a suffix'}"
                f" files, only {accepted}"
            )
        self.validate(name)
        # Before any network call: a typo in a path must not cost a login or an upload.
        if not artifact.is_file():
            raise PublishError(destination, f"{artifact} is not a file")
        logger.info("Publishing %s to %s", name, destination)
        reason = None
        try:
            result = self._upload(artifact, name, title or name)
        except self._errors() as error:
            reason = str(error)
        # Raised here, outside the except block, so the service's error is neither the
        # cause nor the context of the PublishError: it may hold a URL with a token.
        if reason is not None:
            raise PublishError(destination, reason)
        logger.info("Published %s to %s: %s", name, destination, result)
        return result

    @abstractmethod
    def _upload(self, artifact: Path, name: str, title: str) -> str:
        """Upload ``artifact`` and return where it was published."""

    def _errors(self) -> tuple[type[Exception], ...]:
        """Return the errors the service raises, which ``publish`` turns into ``PublishError``.

        They must not hold secrets in their text. None by default.
        """
        return ()
