"""Tests for publishing files to a Google Cloud Storage bucket."""

import sys
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

import pytest

from vizz_geopipe.destinations import GCSDestination
from vizz_geopipe.destinations import gcs
from vizz_geopipe.errors import PublishError

GOOGLE_MODULES = (
    "google.cloud.storage",
    "google.cloud.exceptions",
    "google.api_core.exceptions",
    "google.auth.exceptions",
)


@dataclass
class FakeGcsClient:
    """Stands in for ``google.cloud.storage.Client``: records every upload.

    Attributes:
        uploads: ``(bucket, key, path, content_type)`` of every upload, in order.
        error: Raised by every upload instead of recording it, when set.
    """

    uploads: list[tuple] = field(default_factory=list)
    error: Exception | None = None

    def bucket(self, name):
        return FakeBucket(self, name)


@dataclass
class FakeBucket:
    client: FakeGcsClient
    name: str

    def blob(self, key):
        return FakeBlob(self, key)


@dataclass
class FakeBlob:
    bucket: FakeBucket
    key: str

    def upload_from_filename(self, filename, content_type=None):
        if self.bucket.client.error:
            raise self.bucket.client.error
        self.bucket.client.uploads.append((self.bucket.name, self.key, filename, content_type))


@pytest.fixture
def client(monkeypatch) -> FakeGcsClient:
    fake = FakeGcsClient()
    monkeypatch.setattr(gcs, "_gcs_client", lambda: fake)
    return fake


@pytest.fixture
def dem(tmp_path) -> Path:
    path = tmp_path / "dem.tif"
    path.write_bytes(b"tif")
    return path


def test_publishing_puts_the_file_under_the_prefix(client, dem):
    uri = GCSDestination(bucket="layers", prefix="maps").publish(dem, name="dem")

    assert uri == "gs://layers/maps/dem.tif"
    assert client.uploads == [("layers", "maps/dem.tif", str(dem), "image/tiff")]


def test_publishing_without_the_gcs_extra_says_how_to_install_it(dem, monkeypatch):
    def missing():
        raise ImportError("No module named 'google'")

    monkeypatch.setattr(gcs, "_gcs_client", missing)
    # As if the google packages were not installed: importing a module set to None
    # in sys.modules raises ImportError. CI has no extras, so this is what it sees.
    for module in GOOGLE_MODULES:
        monkeypatch.setitem(sys.modules, module, None)
    destination = GCSDestination(bucket="layers")

    with pytest.raises(PublishError, match=r"vizz-geopipe\[gcs\]"):
        destination.publish(dem, name="dem")


def test_the_content_type_follows_the_suffix(client, tmp_path):
    pmtiles = tmp_path / "places.pmtiles"
    pmtiles.write_bytes(b"pm")

    GCSDestination(bucket="layers").publish(pmtiles, name="places")

    assert client.uploads == [("layers", "places.pmtiles", str(pmtiles), "application/vnd.pmtiles")]


def test_a_public_base_url_gives_a_public_url(client, dem):
    destination = GCSDestination(
        bucket="layers", prefix="maps", public_base_url="https://cdn.example.com/"
    )

    assert destination.publish(dem, name="dem") == "https://cdn.example.com/maps/dem.tif"
    assert [key for _, key, _, _ in client.uploads] == ["maps/dem.tif"]


def test_a_google_error_raises_publish_error(client, dem):
    exceptions = pytest.importorskip("google.api_core.exceptions")
    client.error = exceptions.NotFound("bucket gone")

    with pytest.raises(PublishError, match="GCSDestination.*bucket gone"):
        GCSDestination(bucket="layers").publish(dem, name="dem")
