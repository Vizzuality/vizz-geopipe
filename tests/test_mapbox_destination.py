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
    """The parts of ``requests.Response`` that ``MapboxDestination`` reads.

    A ``str`` payload is an answer that is not JSON, such as an HTML error page.
    """

    status_code: int
    payload: dict | str

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    @property
    def text(self) -> str:
        if isinstance(self.payload, str):
            return self.payload
        return json.dumps(self.payload)

    def json(self) -> dict:
        if isinstance(self.payload, str):
            raise requests.JSONDecodeError("Expecting value", self.payload, 0)
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


def test_creating_reads_no_environment(monkeypatch):
    monkeypatch.setenv("MAPBOX_USER", "vizz")
    monkeypatch.setenv("MAPBOX_TOKEN", TOKEN)

    destination = MapboxDestination()

    assert destination.username is None
    assert destination.token is None


def test_publishing_reads_the_environment(monkeypatch, mapbox, mbtiles):
    monkeypatch.setenv("MAPBOX_USER", "vizz")
    monkeypatch.setenv("MAPBOX_TOKEN", TOKEN)

    result = MapboxDestination().publish(mbtiles, name="mangroves")

    assert result == "vizz.mangroves"
    assert {params["access_token"] for _, _, params, _ in mapbox.calls} == {TOKEN}


def test_given_values_win_over_the_environment(monkeypatch, mapbox, destination, mbtiles):
    monkeypatch.setenv("MAPBOX_USER", "other")

    assert destination.publish(mbtiles, name="mangroves") == "vizz.mangroves"


def test_missing_variables_raise_publish_error_naming_them(monkeypatch, mapbox, mbtiles):
    monkeypatch.delenv("MAPBOX_USER", raising=False)
    monkeypatch.delenv("MAPBOX_TOKEN", raising=False)

    with pytest.raises(PublishError, match="MAPBOX_USER and MAPBOX_TOKEN"):
        MapboxDestination().publish(mbtiles, name="mangroves")

    assert mapbox.calls == []


def test_the_token_from_the_environment_is_never_shown(monkeypatch, mapbox, mbtiles, caplog):
    monkeypatch.setenv("MAPBOX_USER", "vizz")
    monkeypatch.setenv("MAPBOX_TOKEN", TOKEN)
    destination = MapboxDestination()

    with caplog.at_level(logging.DEBUG):
        destination.publish(mbtiles, name="mangroves")

    assert TOKEN not in repr(destination)
    assert TOKEN not in caplog.text


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


def test_a_failed_staging_upload_raises_publish_error(destination, mapbox, mbtiles):
    mapbox.credentials = FakeAnswer(200, {**STAGING, "bucket": "missing"})

    with pytest.raises(PublishError, match="MapboxDestination.*NoSuchBucket"):
        destination.publish(mbtiles, name="mangroves")


def test_urllib3_debug_lines_never_show_the_token(destination, caplog):
    # requests hands urllib3 the path with its query, and urllib3 logs it at DEBUG, in
    # these formats (urllib3/connectionpool.py and urllib3/util/retry.py).
    caplog.set_level(logging.DEBUG)
    path = f"/uploads/v1/vizz/credentials?access_token={TOKEN}"

    logging.getLogger("urllib3.connectionpool").debug(
        '%s://%s:%s "%s %s %s" %s %s',
        "https",
        "api.mapbox.com",
        443,
        "POST",
        path,
        "HTTP/1.1",
        200,
        None,
    )
    logging.getLogger("urllib3.connectionpool").debug("Retry: %s", path)
    logging.getLogger("urllib3.util.retry").debug(
        "Incremented Retry for (url='%s'): %r", path, None
    )

    assert len(caplog.records) == 3
    assert TOKEN not in caplog.text
    assert "access_token=***" in caplog.text


def test_accented_titles_keep_their_letters(destination, mapbox, mbtiles):
    destination.publish(mbtiles, name="poblacion", title="Población de Ñuñoa (2020)")

    assert mapbox.calls[1][3]["name"] == "Poblacion de Nunoa 2020"


def test_an_error_page_is_cut_short_in_the_error(destination, mapbox, mbtiles):
    page = "<html>" + "x" * 5000 + "</html>"
    mapbox.credentials = FakeAnswer(403, page)

    with pytest.raises(PublishError, match="403") as caught:
        destination.publish(mbtiles, name="mangroves")

    assert len(str(caught.value)) < 400


def test_a_title_of_only_punctuation_falls_back_to_the_name(destination, mapbox, mbtiles):
    destination.publish(mbtiles, name="mangroves", title="(...)")

    assert mapbox.calls[1][3]["name"] == "mangroves"


def test_debug_logs_never_show_the_staging_credentials(destination, mapbox, mbtiles, caplog):
    caplog.set_level(logging.DEBUG)

    destination.publish(mbtiles, name="mangroves")

    assert STAGING["sessionToken"] not in caplog.text
    assert STAGING["secretAccessKey"] not in caplog.text
