"""Tests for what every destination does: check the call, upload, report errors safely."""

import logging
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import ClassVar

import pytest

from vizz_geopipe.destinations import Destination
from vizz_geopipe.errors import PublishError


@dataclass(frozen=True, kw_only=True)
class FakeDestination(Destination):
    """Records what it was asked to upload; raises ``OSError`` if ``fail``."""

    suffixes: ClassVar[frozenset[str] | None] = frozenset({".txt"})
    fail: bool = False
    uploads: list[tuple[str, str]] = field(default_factory=list)

    def validate(self, name):
        if name == "bad":
            raise ValueError("bad name")

    def _errors(self):
        return (OSError,)

    def _upload(self, artifact, name, title):
        if self.fail:
            raise OSError("disk on fire")
        self.uploads.append((name, title))
        return f"fake://{name}"


@pytest.fixture
def artifact(tmp_path) -> Path:
    path = tmp_path / "notes.txt"
    path.write_text("data")
    return path


def test_publish_returns_what_the_upload_returns(artifact):
    destination = FakeDestination()

    result = destination.publish(artifact, name="notes", title="Notes")

    assert result == "fake://notes"
    assert destination.uploads == [("notes", "Notes")]


def test_the_title_defaults_to_the_name(artifact):
    destination = FakeDestination()

    destination.publish(artifact, name="notes")

    assert destination.uploads == [("notes", "notes")]


def test_an_artifact_with_another_suffix_is_rejected(tmp_path):
    destination = FakeDestination()
    other = tmp_path / "dem.tif"
    other.write_bytes(b"tif")

    with pytest.raises(ValueError, match=r"\.tif"):
        destination.publish(other, name="dem")

    assert destination.uploads == []


def test_an_invalid_name_is_rejected_before_uploading(artifact):
    destination = FakeDestination()

    with pytest.raises(ValueError, match="bad name"):
        destination.publish(artifact, name="bad")

    assert destination.uploads == []


def test_a_missing_artifact_raises_before_uploading(tmp_path):
    destination = FakeDestination()

    with pytest.raises(PublishError, match="FakeDestination: .*notes.txt is not a file"):
        destination.publish(tmp_path / "notes.txt", name="notes")

    assert destination.uploads == []


def test_service_errors_become_publish_errors(artifact):
    with pytest.raises(PublishError) as caught:
        FakeDestination(fail=True).publish(artifact, name="notes")

    error = caught.value
    assert str(error) == "FakeDestination: disk on fire"
    # Nothing chained: the original error may hold a URL with a token.
    assert error.__cause__ is None
    assert error.__context__ is None


def test_publish_logs_its_start_and_end(artifact, caplog):
    caplog.set_level(logging.INFO, logger="vizz_geopipe")

    FakeDestination().publish(artifact, name="notes")

    assert [record.getMessage() for record in caplog.records] == [
        "Publishing notes to FakeDestination",
        "Published notes to FakeDestination: fake://notes",
    ]


def test_without_suffixes_any_file_is_accepted():
    @dataclass(frozen=True, kw_only=True)
    class AnyFile(FakeDestination):
        suffixes: ClassVar[frozenset[str] | None] = None

    assert AnyFile().accepts(Path("a.tif"))


def test_suffixes_are_matched_whatever_their_case():
    assert FakeDestination().accepts(Path("NOTES.TXT"))
