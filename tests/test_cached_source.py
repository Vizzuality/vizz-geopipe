"""Tests for the cache rule shared by every source that downloads."""

import json
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

from vizz_geopipe.sources._base import CachedSource


@dataclass(frozen=True, kw_only=True)
class ChangingSource(CachedSource):
    """A source whose data changes every time its identity is asked for."""

    asked: list[int] = field(default_factory=list)

    def identity(self) -> dict[str, str]:
        self.asked.append(1)
        return {"version": str(len(self.asked))}

    def _download(self, dest: Path) -> None:
        (dest / "a.txt").write_text("a")


def test_the_record_holds_the_identity_the_cache_was_checked_with(tmp_path):
    source = ChangingSource(files=("*.txt",))
    source.fetch(tmp_path)

    source.fetch(tmp_path)

    assert json.loads((tmp_path / ".source.json").read_text())["identity"] == {"version": "2"}
    assert len(source.asked) == 2
