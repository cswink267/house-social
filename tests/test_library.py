"""The library keeps files out of state and remembers what performed."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapt import DraftError  # noqa: E402
from library import library_for, open_asset_file, record_use, revise_asset, save_asset  # noqa: E402
from store import create_piece, empty_state, load, record_stat, roster, save  # noqa: E402


PNG = base64.b64encode(bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)).decode()


def test_library_versions_search_and_performance(tmp_path, monkeypatch):
    monkeypatch.setenv("HOUSE_SOCIAL_ASSETS", str(tmp_path / "files"))
    path = tmp_path / "state.json"
    saved = save_asset(
        empty_state(),
        "misfit-mindset",
        {
            "kind": "copy",
            "name": "The line",
            "folder": "cards/ember",
            "tags": ["ember", "sunday"],
            "body": "That dread you feel is data.",
        },
        path,
    )
    assert saved["kind"] == "copy"
    assert len(saved["versions"]) == 1
    renamed = revise_asset(load(path), saved["id"], {"tags": ["ember"]}, path)
    assert len(renamed["versions"]) == 1
    revised = revise_asset(load(path), saved["id"], {"body": "A later line."}, path)
    assert revised["body"] == "A later line."
    assert revised["versions"][0]["body"] == "That dread you feel is data."
    restored = revise_asset(load(path), saved["id"], {"restore": revised["versions"][0]["id"]}, path)
    assert restored["body"] == "That dread you feel is data."
    assert len(restored["versions"]) == 3

    found = library_for(load(path), "misfit-mindset", q="ember", folder="cards")
    assert found["assets"][0]["id"] == saved["id"]
    assert library_for(load(path), "josie-blackthorn")["assets"] == []
    assert any(section["id"] == "library" for section in roster(empty_state())[0]["sections"])

    piece = create_piece(load(path), "misfit-mindset", "Sunday dread", path=path)
    record_use(load(path), saved["id"], {"piece_id": piece["id"]}, path)
    record_use(load(path), saved["id"], {"piece_id": piece["id"]}, path)
    record_stat(
        load(path),
        {"brand_id": "misfit-mindset", "platform": "facebook", "piece_id": piece["id"], "engagements": 11, "impressions": 40},
        path,
    )
    state = load(path)
    state = {**state, "pulls": {"misfit-mindset": {"posts": [{"id": "post-9", "engagements": 7}]}}}
    save(state, path)
    record_use(load(path), saved["id"], {"post_id": "post-9"}, path)
    card = library_for(load(path), "misfit-mindset")["assets"][0]
    assert card["performance"]["uses"] == 2
    assert card["performance"]["samples"] == 2
    assert card["performance"]["engagements"] == 18
    assert card["performance"]["impressions"] == 40
    assert PNG not in path.read_text(encoding="utf-8")

    other = create_piece(load(path), "jamhaul", "What is a haul?", path=path)
    with pytest.raises(DraftError, match="another brand"):
        record_use(load(path), saved["id"], {"piece_id": other["id"]}, path)


def test_library_file_stays_beside_state_and_rejects_escape(tmp_path, monkeypatch):
    root = tmp_path / "files"
    monkeypatch.setenv("HOUSE_SOCIAL_ASSETS", str(root))
    path = tmp_path / "state.json"
    saved = save_asset(
        empty_state(),
        "josie-blackthorn",
        {"kind": "logo", "name": "Mark", "folder": "logos", "data": PNG, "file_name": "../nope.png"},
        path,
    )
    assert saved["has_file"] is True
    opened = open_asset_file(load(path), saved["id"], root=root)
    assert opened["path"].read_bytes().startswith(b"\x89PNG")
    assert root.resolve() in opened["path"].parents
    raw = load(path)
    asset = raw["assets"][0]
    escaped = {**asset, "file": "../../etc/passwd"}
    with pytest.raises(DraftError, match="not allowed"):
        open_asset_file({**raw, "assets": [escaped]}, saved["id"], root=root)
    with pytest.raises(DraftError, match="Folders"):
        save_asset(load(path), "josie-blackthorn", {"kind": "copy", "name": "No", "folder": "../secret", "body": "no"}, path)
