"""Publishing files to an Amazon S3 bucket."""

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import boto3
from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import BotoCoreError
from botocore.exceptions import ClientError

from vizz_geopipe.destinations._bucket import _BucketDestination


@dataclass(frozen=True, kw_only=True)
class S3Destination(_BucketDestination):
    """An S3 bucket: each file becomes the object ``<prefix>/<name><suffix>``.

    Credentials come from boto3's usual chain (environment variables, ``~/.aws``, an
    instance role), read when a file is published, never when the module is imported.
    Large files are uploaded in parts.
    """

    scheme: ClassVar[str] = "s3"

    def _put(self, artifact: Path, key: str, content_type: str) -> None:
        """Upload ``artifact`` with ``upload_file``, which splits large files into parts."""
        boto3.client("s3").upload_file(
            str(artifact), self.bucket, key, ExtraArgs={"ContentType": content_type}
        )

    def _errors(self) -> tuple[type[Exception], ...]:
        """The errors of boto3 and botocore. Their text names the bucket, never credentials.

        ``upload_file`` wraps a failed upload in ``S3UploadFailedError``.
        """
        return (BotoCoreError, ClientError, S3UploadFailedError)
