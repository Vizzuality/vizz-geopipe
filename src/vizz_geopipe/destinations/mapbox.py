"""Publishing MBTiles to a Mapbox account with the Uploads API.

See https://docs.mapbox.com/api/maps/uploads/. The token must be a secret token with the
``uploads:write`` scope.
"""

import logging
import os
import re
import time
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any
from typing import ClassVar

import boto3
import requests
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


@dataclass(frozen=True, kw_only=True)
class MapboxDestination(Destination):
    """A Mapbox account: each MBTiles file becomes the tileset ``<username>.<name>``.

    Publishing replaces an existing tileset of the same name, and waits until Mapbox has
    processed it.

    Attributes:
        username: The Mapbox account name.
        token: A secret token with the ``uploads:write`` scope. Never shown in ``repr``,
            logs or errors.
    """

    suffixes: ClassVar[frozenset[str] | None] = frozenset({".mbtiles"})

    username: str
    token: str = field(repr=False)

    @classmethod
    def from_env(cls) -> "MapboxDestination":
        """Read the account from the ``MAPBOX_USER`` and ``MAPBOX_TOKEN`` variables.

        Raises:
            ValueError: If either variable is missing or empty.
        """
        values = {key: os.environ.get(key) for key in ("MAPBOX_USER", "MAPBOX_TOKEN")}
        if missing := [key for key, value in values.items() if not value]:
            raise ValueError(f"set {' and '.join(missing)} to publish to Mapbox")
        return cls(username=values["MAPBOX_USER"], token=values["MAPBOX_TOKEN"])

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
        tileset = f"{self.username}.{name}"
        size = artifact.stat().st_size
        if size > MAX_UPLOAD_BYTES:
            raise PublishError(
                type(self).__name__,
                f"{artifact} is {size} bytes, over Mapbox's limit of 25 GB",
            )
        credentials = self._request("POST", f"{self.username}/credentials")
        session = boto3.Session(
            aws_access_key_id=credentials["accessKeyId"],
            aws_secret_access_key=credentials["secretAccessKey"],
            aws_session_token=credentials["sessionToken"],
        )
        staging = session.client("s3", region_name="us-east-1")
        staging.upload_file(str(artifact), credentials["bucket"], credentials["key"])
        display_name = " ".join(DISPLAY_NAME_UNSAFE.sub(" ", title).split())
        upload = self._request(
            "POST",
            self.username,
            json={"url": credentials["url"], "tileset": tileset, "name": display_name},
        )
        self._wait(tileset, upload["id"])
        return tileset

    def _wait(self, tileset: str, upload_id: str) -> None:
        """Poll the upload until Mapbox has processed it.

        Raises:
            PublishError: If Mapbox reports an error, or the upload is not complete after
                ``TIMEOUT_SECONDS``.
        """
        deadline = time.monotonic() + TIMEOUT_SECONDS
        while True:
            status = self._request("GET", f"{self.username}/{upload_id}")
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

    def _request(self, method: str, path: str, **kwargs: Any) -> dict:
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
                params={"access_token": self.token},
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
                f"Mapbox answered {response.status_code} to {method} {path}: {response.text}",
            )
        return response.json()

    def _errors(self) -> tuple[type[Exception], ...]:
        """The errors of the upload to Mapbox's staging bucket."""
        return (BotoCoreError, ClientError)
