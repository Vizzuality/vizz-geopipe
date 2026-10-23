"""Sources stored as objects in an S3 or Google Cloud Storage bucket."""

from collections.abc import Callable
from dataclasses import dataclass
from fnmatch import fnmatchcase
from functools import partial
from pathlib import Path
from typing import BinaryIO
from urllib.parse import urlparse

import boto3
from google.cloud import storage

from vizz_geopipe.errors import SourceError
from vizz_geopipe.sources._base import CachedSource
from vizz_geopipe.sources._files import atomic_write


@dataclass(frozen=True, kw_only=True)
class BucketSource(CachedSource):
    """Objects in an S3 or Google Cloud Storage bucket, downloaded into ``dest``.

    An object is selected when its key, relative to the URI's prefix, matches a pattern in
    ``files`` (``fnmatch.fnmatchcase``). Each selected object is saved under that relative
    key, so ``s3://layers/dem/a.tif`` with the URI ``s3://layers/dem`` becomes
    ``dest/a.tif``.

    Credentials come from each client's standard chain (environment variables, config
    files, instance roles); none are read when this module is imported. ``gs://`` needs
    the ``gcs`` extra: ``vizz-geopipe[gcs]``.

    Attributes:
        uri: The bucket and prefix, ``s3://<bucket>/<prefix>`` or ``gs://<bucket>/<prefix>``.
    """

    uri: str

    def __post_init__(self) -> None:
        """Check the URI's scheme when the source is created, not when it is fetched.

        Raises:
            ValueError: If ``uri`` does not start with ``s3://`` or ``gs://``.
        """
        if urlparse(self.uri).scheme not in {"s3", "gs"}:
            raise ValueError(f"Invalid bucket URI: {self.uri}")

    def identity(self) -> dict[str, str]:
        """Return the URI and the version of each selected object.

        The version is the ETag on S3 and the generation on Google Cloud Storage, so
        replacing an object changes the identity.

        Raises:
            SourceError: If ``gs://`` is used without the ``gcs`` extra installed.
        """
        return {"uri": self.uri, **{key: version for key, version, _ in self._objects()}}

    def _download(self, dest: Path) -> None:
        for relative_key, _, write_to in self._objects():
            with atomic_write(dest / relative_key) as file:
                write_to(file)

    def _objects(self) -> list[tuple[str, str, Callable[[BinaryIO], None]]]:
        """Return each selected object's relative key, version, and a way to download it.

        Returns:
            A list of tuples ``(relative_key, version, write_to)``. ``write_to(file)``
            writes the object's bytes into ``file``, a file object opened for writing bytes.

        Raises:
            SourceError: If ``gs://`` is used without the ``gcs`` extra installed.
        """
        url = urlparse(self.uri)
        bucket = url.netloc
        prefix = url.path.strip("/")
        prefix = f"{prefix}/" if prefix else ""
        if url.scheme == "s3":
            client = boto3.client("s3")
            pages = client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix)
            found = [
                (item["Key"], item["ETag"], partial(client.download_fileobj, bucket, item["Key"]))
                for page in pages
                for item in page.get("Contents", [])
            ]
        else:
            try:
                client = _gcs_client()
            except ImportError as error:
                raise SourceError(
                    self.uri, "install vizz-geopipe[gcs] to read gs:// buckets"
                ) from error
            found = [
                (blob.name, str(blob.generation), blob.download_to_file)
                for blob in client.list_blobs(bucket, prefix=prefix)
            ]
        return [
            (key.removeprefix(prefix), version, write_to)
            for key, version, write_to in found
            if any(fnmatchcase(key.removeprefix(prefix), pattern) for pattern in self.files)
        ]


def _gcs_client():
    """Return a Google Cloud Storage client, importing the library only when needed.

    Raises:
        ImportError: If ``google-cloud-storage`` is not installed.
    """

    return storage.Client()
