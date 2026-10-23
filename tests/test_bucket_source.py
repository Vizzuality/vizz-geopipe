"""Tests for sources stored in S3 or Google Cloud Storage."""

import sys
from dataclasses import dataclass

import boto3
import pytest
from google.api_core.exceptions import NotFound
from moto import mock_aws

from vizz_geopipe.errors import SourceError
from vizz_geopipe.sources import BucketSource
from vizz_geopipe.sources import bucket as bucket_module


@pytest.fixture
def s3(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_aws():
        client = boto3.client("s3")
        client.create_bucket(Bucket="layers")
        client.put_object(Bucket="layers", Key="dem/a.tif", Body=b"a")
        client.put_object(Bucket="layers", Key="dem/readme.txt", Body=b"r")
        yield client


def test_s3_objects_matching_the_patterns_are_downloaded(tmp_path, s3):
    paths = BucketSource(uri="s3://layers/dem", files=("*.tif",)).fetch(tmp_path)

    assert paths == [tmp_path / "a.tif"]
    assert paths[0].read_bytes() == b"a"


def test_objects_in_subfolders_need_a_pattern_with_the_subfolder(tmp_path, s3):
    s3.put_object(Bucket="layers", Key="dem/2020/b.tif", Body=b"b")

    paths = BucketSource(uri="s3://layers/dem", files=("*.tif",)).fetch(tmp_path)

    assert paths == [tmp_path / "a.tif"]
    assert not (tmp_path / "2020").exists()


def test_folder_markers_are_not_downloaded(tmp_path, s3):
    # The S3 console's "Create folder" makes an empty object whose key ends with "/".
    s3.put_object(Bucket="layers", Key="dem/", Body=b"")
    s3.put_object(Bucket="layers", Key="dem/2020/", Body=b"")
    s3.put_object(Bucket="layers", Key="dem/2020/b.tif", Body=b"b")

    top = BucketSource(uri="s3://layers/dem", files=("*",)).fetch(tmp_path / "top")
    sub = BucketSource(uri="s3://layers/dem", files=("2020/*",)).fetch(tmp_path / "sub")

    assert top == [tmp_path / "top" / "a.tif", tmp_path / "top" / "readme.txt"]
    assert sub == [tmp_path / "sub" / "2020" / "b.tif"]


def test_keys_that_lead_outside_dest_raise_source_error(tmp_path, s3):
    s3.put_object(Bucket="layers", Key="dem/../escaped.tif", Body=b"x")
    dest = tmp_path / "dest"

    with pytest.raises(SourceError, match="outside"):
        BucketSource(uri="s3://layers/dem", files=("*/*.tif",)).fetch(dest)

    assert not (tmp_path / "escaped.tif").exists()


def test_s3_errors_raise_source_error(tmp_path, s3):
    with pytest.raises(SourceError, match="s3://missing/dem"):
        BucketSource(uri="s3://missing/dem", files=("*.tif",)).fetch(tmp_path)


def test_identity_changes_when_an_object_changes(s3):
    source = BucketSource(uri="s3://layers/dem", files=("*.tif",))
    before = source.identity()

    s3.put_object(Bucket="layers", Key="dem/a.tif", Body=b"changed")

    assert source.identity() != before


@dataclass
class FakeBlob:
    name: str
    generation: int
    data: bytes

    def download_to_file(self, file):
        file.write(self.data)


class FakeGcsClient:
    def list_blobs(self, bucket, prefix):
        return [FakeBlob("dem/a.tif", 1, b"a")]


def test_gcs_objects_are_downloaded(tmp_path, monkeypatch):
    monkeypatch.setattr(bucket_module, "_gcs_client", FakeGcsClient)

    paths = BucketSource(uri="gs://layers/dem", files=("*.tif",)).fetch(tmp_path)

    assert paths[0].read_bytes() == b"a"


class FailingGcsClient:
    def list_blobs(self, bucket, prefix):
        raise NotFound("bucket layers not found")


def test_gcs_errors_raise_source_error(tmp_path, monkeypatch):
    monkeypatch.setattr(bucket_module, "_gcs_client", FailingGcsClient)

    with pytest.raises(SourceError, match="not found"):
        BucketSource(uri="gs://layers/dem", files=("*.tif",)).fetch(tmp_path)


def test_gcs_without_the_extra_says_how_to_install_it(tmp_path, monkeypatch):
    # None in sys.modules makes the import fail, as if google-cloud-storage were missing.
    monkeypatch.setitem(sys.modules, "google.cloud", None)
    monkeypatch.setitem(sys.modules, "google.cloud.storage", None)

    with pytest.raises(SourceError, match=r"vizz-geopipe\[gcs\]"):
        BucketSource(uri="gs://layers/dem", files=("*.tif",)).fetch(tmp_path)


def test_rejects_uris_that_are_not_s3_or_gs():
    with pytest.raises(ValueError):
        BucketSource(uri="https://example.com/dem", files=("*.tif",))
