"""Tests for sources stored in S3 or Google Cloud Storage."""

from dataclasses import dataclass

import boto3
import pytest
from moto import mock_aws

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


def test_rejects_uris_that_are_not_s3_or_gs():
    with pytest.raises(ValueError):
        BucketSource(uri="https://example.com/dem", files=("*.tif",))
