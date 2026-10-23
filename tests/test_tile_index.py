"""Tests for rasters split into tiles listed by an index."""

import json

import pytest

from vizz_geopipe.errors import SourceError
from vizz_geopipe.sources import ArcGISTileIndex
from vizz_geopipe.sources import TextTileIndex
from vizz_geopipe.sources import TileIndexSource

INDEX = "https://example.com/tiles.txt"
ARCGIS = "https://example.com/FeatureServer/0"


def test_text_index_names_tiles_after_their_file(fake_web):
    fake_web.pages[INDEX] = b"https://example.com/t/10N_000E.tif\nhttps://example.com/t/b.tif\n"

    assert TextTileIndex(url=INDEX).tile_urls() == {
        "10N_000E": "https://example.com/t/10N_000E.tif",
        "b": "https://example.com/t/b.tif",
    }


def test_arcgis_index_reads_the_name_and_url_fields(fake_web):
    feature = {"attributes": {"tile_id": "a", "link": "https://example.com/a.tif"}}
    fake_web.pages[f"{ARCGIS}/query"] = json.dumps({"features": [feature]}).encode()

    index = ArcGISTileIndex(url=ARCGIS, name_field="tile_id", url_field="link")

    assert index.tile_urls() == {"a": "https://example.com/a.tif"}


@pytest.mark.parametrize(
    "answer", [{"error": {"code": 400}}, {"features": [], "exceededTransferLimit": True}]
)
def test_arcgis_errors_and_cut_lists_raise_source_error(fake_web, answer):
    fake_web.pages[f"{ARCGIS}/query"] = json.dumps(answer).encode()
    index = ArcGISTileIndex(url=ARCGIS, name_field="tile_id", url_field="link")

    with pytest.raises(SourceError):
        index.tile_urls()


def test_selected_tiles_are_downloaded(tmp_path, fake_web):
    fake_web.pages[INDEX] = b"https://example.com/t/a.tif\nhttps://example.com/t/b.tif\n"
    fake_web.pages["https://example.com/t/a.tif"] = b"a"
    source = TileIndexSource(index=TextTileIndex(url=INDEX), tiles=("a",))

    assert source.fetch(tmp_path) == [tmp_path / "a.tif"]
    assert "https://example.com/t/b.tif" not in fake_web.requested


def test_unknown_tiles_raise_source_error(tmp_path, fake_web):
    fake_web.pages[INDEX] = b"https://example.com/t/a.tif\n"
    source = TileIndexSource(index=TextTileIndex(url=INDEX), tiles=("zz",))

    with pytest.raises(SourceError, match="zz"):
        source.fetch(tmp_path)
