"""Tests for publishing MBTiles to Mapbox with the Uploads API."""

import json
import logging
import traceback
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

import boto3
import pytest
import requests
from moto import mock_aws

from vizz_geopipe.destinations import MapboxDestination
from vizz_geopipe.destinations import mapbox as mapbox_module
from vizz_geopipe.errors import PublishError

TOKEN = "sk.secret"
STAGING = {
    "accessKeyId": "AKIA",
    "secretAccessKey": "staging-secret",
    "sessionToken": "staging-session",
    "bucket": "staging",
    "key": "k",
    "url": "s3://staging/k",
}


@dataclass
class FakeAnswer:
    """The parts of ``requests.Response`` that ``MapboxDestination`` reads."""

    status_code: int
    payload: dict

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    @property
    def text(self) -> str:
        return json.dumps(self.payload)

    def json(self) -> dict:
        return self.payload


@dataclass
class FakeMapbox:
    """Answers ``requests.request`` as the Uploads API would, for the user ``vizz``.

    Attributes:
        credentials: The answer to the staging credentials request.
        statuses: The answers to the status polls, in order; the last one repeats.
        calls: ``(method, url, params, json)`` of every request, in order.
    """

    credentials: FakeAnswer = field(default_factory=lambda: FakeAnswer(200, STAGING))
    statuses: list[dict] = field(
        default_factory=lambda: [{"complete": True, "error": None, "progress": 1.0}]
    )
    calls: list[tuple] = field(default_factory=list)

    def request(self, method, url, params=None, json=None, timeout=None):
        self.calls.append((method, url, params, json))
        path = url.removeprefix(f"{mapbox_module.UPLOADS_API}/")
        if path == "vizz/credentials":
            return self.credentials
        if method == "POST" and path == "vizz":
            return FakeAnswer(201, {"id": "u1"})
        if path == "vizz/u1":
            status = self.statuses[0]
            if len(self.statuses) > 1:
                self.statuses.pop(0)
            return FakeAnswer(200, status)
        return FakeAnswer(404, {"message": "Not Found"})


@pytest.fixture
def mapbox(monkeypatch) -> FakeMapbox:
    """A fake Mapbox API, and a fake S3 with Mapbox's ``staging`` bucket."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setattr(mapbox_module, "POLL_SECONDS", 0)
    fake = FakeMapbox()
    monkeypatch.setattr(requests, "request", fake.request)
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="staging")
        yield fake


@pytest.fixture
def destination() -> MapboxDestination:
    return MapboxDestination(username="vizz", token=TOKEN)


@pytest.fixture
def mbtiles(tmp_path) -> Path:
    path = tmp_path / "mangroves.mbtiles"
    path.write_bytes(b"tiles")
    return path


def test_from_env_reads_the_user_and_token(monkeypatch):
    monkeypatch.setenv("MAPBOX_USER", "vizz")
    monkeypatch.setenv("MAPBOX_TOKEN", TOKEN)

    destination = MapboxDestination.from_env()

    assert destination.username == "vizz"
    assert destination.token == TOKEN


def test_from_env_names_the_missing_variables(monkeypatch):
    monkeypatch.delenv("MAPBOX_USER", raising=False)
    monkeypatch.delenv("MAPBOX_TOKEN", raising=False)

    with pytest.raises(ValueError, match="MAPBOX_USER and MAPBOX_TOKEN"):
        MapboxDestination.from_env()


def test_the_token_is_not_in_the_repr(destination):
    assert TOKEN not in repr(destination)


def test_tileset_names_follow_mapbox_rules(destination):
    for name in ("a" * 33, "a.b"):
        with pytest.raises(ValueError):
            destination.validate(name)

    destination.validate("mangroves_2020-v1")


def test_pmtiles_are_rejected_before_any_request(destination, mapbox, tmp_path):
    pmtiles = tmp_path / "mangroves.pmtiles"
    pmtiles.write_bytes(b"tiles")

    with pytest.raises(ValueError):
        destination.publish(pmtiles, name="mangroves")

    assert mapbox.calls == []


def test_publishing_uploads_and_returns_the_tileset_id(destination, mapbox, mbtiles):
    tileset = destination.publish(mbtiles, name="mangroves", title="Mangroves (2020)")

    staged = boto3.client("s3", region_name="us-east-1").get_object(Bucket="staging", Key="k")
    create = mapbox.calls[1]
    assert tileset == "vizz.mangroves"
    assert staged["Body"].read() == b"tiles"
    assert create[:2] == ("POST", f"{mapbox_module.UPLOADS_API}/vizz")
    assert create[3] == {
        "url": "s3://staging/k",
        "tileset": "vizz.mangroves",
        "name": "Mangroves 2020",
    }
    assert all(params == {"access_token": TOKEN} for _, _, params, _ in mapbox.calls)


def test_a_mapbox_processing_error_raises(destination, mapbox, mbtiles):
    mapbox.statuses = [{"complete": False, "error": "bad file", "progress": 0}]

    with pytest.raises(PublishError, match="bad file"):
        destination.publish(mbtiles, name="mangroves")


def test_an_upload_that_never_completes_times_out(destination, mapbox, mbtiles, monkeypatch):
    monkeypatch.setattr(mapbox_module, "TIMEOUT_SECONDS", 0)
    mapbox.statuses = [{"complete": False, "error": None, "progress": 0.5}]

    with pytest.raises(PublishError, match="vizz.mangroves"):
        destination.publish(mbtiles, name="mangroves")


def test_a_file_over_the_limit_is_rejected_before_any_request(
    destination, mapbox, mbtiles, monkeypatch
):
    monkeypatch.setattr(mapbox_module, "MAX_UPLOAD_BYTES", 1)

    with pytest.raises(PublishError, match="25 GB"):
        destination.publish(mbtiles, name="mangroves")

    assert mapbox.calls == []


def test_an_error_answer_shows_mapbox_message(destination, mapbox, mbtiles):
    mapbox.credentials = FakeAnswer(401, {"message": "Not Authorized - Invalid Token"})

    with pytest.raises(PublishError, match="401.*Invalid Token"):
        destination.publish(mbtiles, name="mangroves")


def test_a_failed_request_never_shows_the_token(destination, mbtiles, monkeypatch):
    def unreachable(method, url, **kwargs):
        raise requests.ConnectionError(f"Max retries exceeded with url: {url}?access_token={TOKEN}")

    monkeypatch.setattr(requests, "request", unreachable)

    with pytest.raises(PublishError) as caught:
        destination.publish(mbtiles, name="mangroves")

    error = caught.value
    assert TOKEN not in str(error)
    assert error.__cause__ is None
    assert error.__context__ is None
    assert TOKEN not in "".join(traceback.format_exception(error))


def test_publishing_never_logs_the_token(destination, mapbox, mbtiles, caplog):
    caplog.set_level(logging.DEBUG, logger="vizz_geopipe")

    destination.publish(mbtiles, name="mangroves")

    assert caplog.records
    assert TOKEN not in caplog.text
