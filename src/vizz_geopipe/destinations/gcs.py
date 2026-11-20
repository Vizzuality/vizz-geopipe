"""Publishing files to a Google Cloud Storage bucket."""

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from vizz_geopipe.destinations._bucket import _BucketDestination
from vizz_geopipe.errors import PublishError


def _gcs_client():
    """Return a Google Cloud Storage client, importing the library only when needed.

    Raises:
        ImportError: If ``google-cloud-storage`` is not installed.
    """
    # Imported here, so vizz_geopipe imports without the gcs extra.
    from google.cloud import storage

    return storage.Client()


@dataclass(frozen=True, kw_only=True)
class GCSDestination(_BucketDestination):
    """A Google Cloud Storage bucket: each file becomes the object ``<prefix>/<name><suffix>``.

    Credentials come from Google's Application Default Credentials, read when a file is
    published. Needs the ``gcs`` extra: ``pip install vizz-geopipe[gcs]``.
    """

    scheme: ClassVar[str] = "gs"

    def _put(self, artifact: Path, key: str, content_type: str) -> None:
        """Upload ``artifact`` to ``key``, stored as ``content_type``.

        Raises:
            PublishError: If the ``gcs`` extra is not installed.
        """
        try:
            storage_client = _gcs_client()
        except ImportError:
            raise PublishError(
                "GCSDestination", "install vizz-geopipe[gcs] to publish to gs:// buckets"
            ) from None
        bucket = storage_client.bucket(self.bucket)

        blob = bucket.blob(key)
        blob.upload_from_filename(str(artifact), content_type=content_type)

    def _errors(self) -> tuple[type[Exception], ...]:
        """The errors of the Google Cloud libraries, or none without the ``gcs`` extra.

        Without the extra no Google code ran, so an empty tuple, which catches nothing, is
        right. Importing unguarded would replace the error being handled with ``ImportError``.
        """
        try:
            from google.api_core.exceptions import GoogleAPIError
            from google.auth.exceptions import GoogleAuthError
        except ImportError:
            return ()
        return (GoogleAPIError, GoogleAuthError)
