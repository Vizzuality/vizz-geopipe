"""Publishing MBTiles to a Mapbox account with the Uploads API.

See https://docs.mapbox.com/api/maps/uploads/. The token must be a secret token with the
``uploads:write`` scope.
"""

import logging
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any
from typing import ClassVar

import boto3
import requests
from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import BotoCoreError
from botocore.exceptions import ClientError

from vizz_geopipe.destinations._base import Destination
from vizz_geopipe.errors import PublishError

logger = logging.getLogger(__name__)

UPLOADS_API = "https://api.mapbox.com/uploads/v1"
REQUEST_TIMEOUT = 30
# Mapbox's limit for an MBTiles upload is 25 GB; the smaller reading of "GB".
MAX_UPLOAD_BYTES = 25 * 10**9
POLL_SECONDS = 5
TIMEOUT_SECONDS = 3600
TILESET_NAME = re.compile(r"[A-Za-z0-9_-]{1,32}")
# Mapbox rejects display names with punctuation such as brackets or commas.
DISPLAY_NAME_UNSAFE = re.compile(r"[^A-Za-z0-9 _-]+")
SECRET = re.compile(r"(access_token=|x-amz-security-token'?:\s*b?'?)[^&\s'\"]+", re.IGNORECASE)


class _HideSecrets(logging.Filter):
    """Replace the tokens in a log record's message with ``***``.

    urllib3 logs each request's path and query (with the Mapbox token) at ``DEBUG``, and
    botocore each signed request (with the staging token), so a script that turns ``DEBUG``
    on for everything would print them.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        hidden = SECRET.sub(r"\1***", message)
        if hidden != message:
            record.msg = hidden
            record.args = None
        return True


# The loggers that print a token. A filter on a logger sees the records logged on that
# logger, before any handler.
for _name in ("urllib3.connectionpool", "urllib3.util.retry", "botocore.auth", "botocore.endpoint"):
    logging.getLogger(_name).addFilter(_HideSecrets())


def _display_name(title: str) -> str:
    """Return ``title`` as Mapbox accepts it: accents dropped, other punctuation removed.

    ``"Población de Ñuñoa (2020)"`` becomes ``"Poblacion de Nunoa 2020"``.
    """
    letters = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    return " ".join(DISPLAY_NAME_UNSAFE.sub(" ", letters).split())


@dataclass(frozen=True, kw_only=True)
class MapboxDestination(Destination):
    """A Mapbox account: each MBTiles file becomes the tileset ``<username>.<name>``.

    Publishing replaces an existing tileset of the same name, and waits until Mapbox has
    processed it. The credentials, when not given, are read from ``MAPBOX_USER`` and
    ``MAPBOX_TOKEN`` when a file is published, so a project can declare
    ``MapboxDestination()`` on a machine without them.

    Attributes:
        username: The Mapbox account name. Defaults to ``MAPBOX_USER``.
        token: A secret token with the ``uploads:write`` scope. Defaults to
            ``MAPBOX_TOKEN``. Never shown in ``repr``, logs or errors.
    """

    suffixes: ClassVar[frozenset[str] | None] = frozenset({".mbtiles"})

    username: str | None = None
    token: str | None = field(default=None, repr=False)

    def validate(self, name: str) -> None:
        """Check that ``name`` is a valid tileset name (without the ``username.``).

        Raises:
            ValueError: Unless ``name`` is 1 to 32 letters, digits, ``-`` or ``_``.
        """
        if not TILESET_NAME.fullmatch(name):
            raise ValueError(
                f"invalid Mapbox tileset name {name!r}: use 1 to 32 letters, digits, '-' or '_'"
            )

    def _upload(self, artifact: Path, name: str, title: str) -> str:
        """Stage ``artifact`` in Mapbox's bucket, create the tileset and wait for it."""
        username = self.username or os.environ.get("MAPBOX_USER")
        token = self.token or os.environ.get("MAPBOX_TOKEN")
        if missing := [
            key for key, value in (("MAPBOX_USER", username), ("MAPBOX_TOKEN", token)) if not value
        ]:
            raise PublishError(
                type(self).__name__, f"set {' and '.join(missing)} to publish to Mapbox"
            )
        tileset = f"{username}.{name}"
        size = artifact.stat().st_size
        if size > MAX_UPLOAD_BYTES:
            raise PublishError(
                type(self).__name__,
                f"{artifact} is {size} bytes, over Mapbox's limit of 25 GB",
            )
        credentials = self._request("POST", f"{username}/credentials", token)
        session = boto3.Session(
            aws_access_key_id=credentials["accessKeyId"],
            aws_secret_access_key=credentials["secretAccessKey"],
            aws_session_token=credentials["sessionToken"],
        )
        staging = session.client("s3", region_name="us-east-1")
        staging.upload_file(str(artifact), credentials["bucket"], credentials["key"])
        display_name = _display_name(title) or name  # a title of only punctuation
        upload = self._request(
            "POST",
            username,
            token,
            json={"url": credentials["url"], "tileset": tileset, "name": display_name},
        )
        self._wait(tileset, upload["id"], username, token)
        return tileset

    def _wait(self, tileset: str, upload_id: str, username: str, token: str) -> None:
        """Poll the upload until Mapbox has processed it.

        Raises:
            PublishError: If Mapbox reports an error, or the upload is not complete after
                ``TIMEOUT_SECONDS``.
        """
        deadline = time.monotonic() + TIMEOUT_SECONDS
        while True:
            status = self._request("GET", f"{username}/{upload_id}", token)
            if status["error"]:
                raise PublishError(
                    type(self).__name__, f"Mapbox could not process {tileset}: {status['error']}"
                )
            logger.debug("Mapbox is processing %s: %d%%", tileset, status["progress"] * 100)
            if status["complete"]:
                return
            if time.monotonic() > deadline:
                raise PublishError(
                    type(self).__name__,
                    f"Mapbox had not processed {tileset} after {TIMEOUT_SECONDS} s",
                )
            time.sleep(POLL_SECONDS)

    def _request(self, method: str, path: str, token: str, **kwargs: Any) -> dict:
        """Call the Uploads API and return its JSON answer.

        The token goes in the URL (Mapbox takes it there), so the text of a ``requests``
        error, which includes the URL, is never used.

        Raises:
            PublishError: If the request fails or Mapbox answers with an error.
        """
        failure = None
        try:
            response = requests.request(
                method,
                f"{UPLOADS_API}/{path}",
                params={"access_token": token},
                timeout=REQUEST_TIMEOUT,
                **kwargs,
            )
        except requests.RequestException as error:
            failure = f"{method} {path} failed: {type(error).__name__}"
        # Raised outside the except block, so the requests error (and its URL) is not
        # chained to the PublishError.
        if failure is not None:
            raise PublishError(type(self).__name__, failure)
        if not response.ok:
            raise PublishError(
                type(self).__name__,
                f"Mapbox answered {response.status_code} to {method} {path}: {response.text[:200]}",
            )
        return response.json()

    def _errors(self) -> tuple[type[Exception], ...]:
        """The errors of the upload to Mapbox's staging bucket.

        ``upload_file`` wraps a failed upload in ``S3UploadFailedError``.
        """
        return (BotoCoreError, ClientError, S3UploadFailedError)
