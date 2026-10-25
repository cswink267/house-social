"""The library keeps files out of state and remembers what performed."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapt import DraftError  # noqa: E402
from library import library_for, open_asset_file, read_asset_tags, record_use, revise_asset, save_asset  # noqa: E402
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


def test_library_pairs_versions_and_keeps_tags_honest(tmp_path, monkeypatch):
    monkeypatch.setenv("HOUSE_SOCIAL_ASSETS", str(tmp_path / "files"))
    path = tmp_path / "state.json"
    first = save_asset(
        empty_state(),
        "misfit-mindset",
        {"kind": "copy", "name": "Sunday line", "tags": ["ember", "sunday"], "body": "That dread you feel is data.", "role": "hook"},
        path,
    )
    assert first["role"] == "hook"
    named = save_asset(load(path), "misfit-mindset", {"kind": "copy", "name": "Ember card", "body": "You felt it.", "role": "cta"}, path)
    assert "ember" in named["tags"]
    assert "sunday" not in [tag.lower() for tag in named["tags"]]

    version_id = first["versions"][0]["id"]
    for index in range(3):
        piece = create_piece(load(path), "misfit-mindset", f"Raw {index}", pillar="raw-truth", path=path)
        record_use(load(path), first["id"], {"piece_id": piece["id"]}, path)
        record_stat(load(path), {"brand_id": "misfit-mindset", "platform": "facebook", "piece_id": piece["id"], "engagements": 20}, path)
    revise_asset(load(path), first["id"], {"body": "A later line."}, path)
    for index in range(3):
        piece = create_piece(load(path), "misfit-mindset", f"Music {index}", pillar="music", path=path)
        record_use(load(path), first["id"], {"piece_id": piece["id"]}, path)
        record_stat(load(path), {"brand_id": "misfit-mindset", "platform": "facebook", "piece_id": piece["id"], "engagements": 4}, path)
    card = next(asset for asset in library_for(load(path), "misfit-mindset")["assets"] if asset["id"] == first["id"])
    assert card["performance"]["mean"] == 12.0
    assert card["performance"]["last_used"]
    assert card["performance"]["best_version"] == version_id
    assert card["performance"]["pairings"][0]["clear"] is True
    assert card["performance"]["pairings"][0]["name"] == "raw-truth"
    assert "educational" not in card["performance"]["pairing_detail"].lower()

    image = save_asset(
        load(path),
        "misfit-mindset",
        {"kind": "image", "name": "Mark", "data": PNG, "file_name": "mark.png"},
        path,
    )
    assert image["role"] == ""

    def complete(messages):
        assert any(isinstance(message.get("content"), list) for message in messages)
        return '{"options": ["visible", "not a tag"]}'

    tagged = read_asset_tags(load(path), image["id"], complete, path, root=tmp_path / "files")
    assert "visible" in tagged["tags"]
    assert all(" " not in tag for tag in tagged["tags"])

    def offline(_messages):
        raise DraftError("The assistant is offline.")

    with pytest.raises(DraftError, match="offline"):
        read_asset_tags(load(path), image["id"], offline, path, root=tmp_path / "files")
    again = next(asset for asset in library_for(load(path), "misfit-mindset")["assets"] if asset["id"] == image["id"])
    assert again["tags"] == tagged["tags"]


def test_tag_reading_mines_words_from_a_describing_model(tmp_path, monkeypatch):
    monkeypatch.setenv("HOUSE_SOCIAL_ASSETS", str(tmp_path / "files"))
    path = tmp_path / "state.json"
    image = save_asset(
        empty_state(),
        "misfit-mindset",
        {"kind": "image", "name": "Mark", "data": PNG, "file_name": "mark.png"},
        path,
    )

    def describing(_messages):
        return "The image features a red and black graffiti-style font with spikes and the word mm in the center."

    mined = read_asset_tags(load(path), image["id"], describing, path, root=tmp_path / "files")
    lowered = [tag.lower() for tag in mined["tags"]]
    for word in ("red", "black", "graffiti-style", "font", "spikes"):
        assert word in lowered
    for filler in ("the", "image", "features", "word", "center", "and"):
        assert filler not in lowered

