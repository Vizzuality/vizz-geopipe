"""Tests for publishing files to an S3 bucket."""

from pathlib import Path

import boto3
import pytest
from moto import mock_aws

from vizz_geopipe.destinations import S3Destination
from vizz_geopipe.errors import PublishError


@pytest.fixture
def s3(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_aws():
        client = boto3.client("s3")
        client.create_bucket(Bucket="layers")
        yield client


@pytest.fixture
def dem(tmp_path) -> Path:
    path = tmp_path / "dem.tif"
    path.write_bytes(b"tif")
    return path


def test_publishing_puts_the_file_under_the_prefix(s3, dem):
    uri = S3Destination(bucket="layers", prefix="maps").publish(dem, name="dem")

    assert uri == "s3://layers/maps/dem.tif"
    assert s3.get_object(Bucket="layers", Key="maps/dem.tif")["Body"].read() == b"tif"


def test_the_content_type_follows_the_suffix(s3, tmp_path):
    pmtiles = tmp_path / "places.pmtiles"
    pmtiles.write_bytes(b"pm")

    S3Destination(bucket="layers").publish(pmtiles, name="places")

    head = s3.head_object(Bucket="layers", Key="places.pmtiles")
    assert head["ContentType"] == "application/vnd.pmtiles"


@pytest.mark.parametrize(
    ("prefix", "key"),
    [
        ("", "dem.tif"),
        ("maps", "maps/dem.tif"),
        ("maps/", "maps/dem.tif"),
        ("/maps/", "maps/dem.tif"),
        ("a/b", "a/b/dem.tif"),
    ],
)
def test_object_keys_for_every_way_of_writing_the_prefix(s3, dem, prefix, key):
    uri = S3Destination(bucket="layers", prefix=prefix).publish(dem, name="dem")

    assert uri == f"s3://layers/{key}"
    assert s3.get_object(Bucket="layers", Key=key)["Body"].read() == b"tif"


def test_a_public_base_url_gives_a_public_url(s3, dem):
    destination = S3Destination(
        bucket="layers", prefix="maps", public_base_url="https://cdn.example.com/"
    )

    assert destination.publish(dem, name="dem") == "https://cdn.example.com/maps/dem.tif"


def test_a_missing_bucket_raises_publish_error(s3, dem):
    with pytest.raises(PublishError, match="S3Destination.*NoSuchBucket"):
        S3Destination(bucket="nope").publish(dem, name="dem")


def test_a_bucket_with_a_slash_is_rejected():
    with pytest.raises(ValueError, match="layers/maps"):
        S3Destination(bucket="layers/maps")


def test_any_file_is_accepted():
    assert S3Destination(bucket="layers").accepts(Path("a.csv"))
