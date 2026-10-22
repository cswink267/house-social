"""Hashtag sets stay small, and a tag is only ahead when the gap is real."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapt import DraftError  # noqa: E402
from hashtags import apply_set, hashtags_for, save_set, save_trend  # noqa: E402
from store import create_piece, empty_state, load, roster  # noqa: E402


def _post(name, engagements, preview="", **extra):
    row = {"id": name, "preview": preview, "engagements": engagements, "format": extra.pop("format", "feed")}
    row.update(extra)
    return row


def test_sets_are_capped_and_used_tags_need_a_real_gap(tmp_path: Path):
    path = tmp_path / "state.json"
    saved = save_set(
        empty_state(),
        "misfit-mindset",
        {"name": "Campfire", "tags": ["ember", "ember", "camp", "night", "ash", "extra"]},
        path,
    )
    assert saved["tags"] == ["ember", "camp", "night", "ash", "extra"]
    piece = create_piece(load(path), "misfit-mindset", "The fire held. The night did not.", path=path)
    applied = apply_set(load(path), saved["id"], piece["id"], path)
    assert applied["tags"][0] == "ember"
    stored = next(item for item in load(path)["pieces"] if item["id"] == piece["id"])
    assert stored["variants"]["instagram"]["hashtags"][0] == "ember"
    other = create_piece(load(path), "jamhaul", "What is a haul?", path=path)
    with pytest.raises(DraftError, match="another brand"):
        apply_set(load(path), saved["id"], other["id"], path)
    yes = [_post(f"y{i}", 20, "#Ember") for i in range(3)]
    no = [_post(f"n{i}", 4, "no tag here") for i in range(3)]
    view = hashtags_for(load(path), "misfit-mindset", yes + no)
    ember = next(item for item in view["tags"] if item["tag"].lower() == "ember")
    assert ember["clear"] is True
    assert ember["n"] == 3
    thin = hashtags_for(load(path), "misfit-mindset", [_post("one", 9, "#quiet")])
    assert thin["tags"][0]["clear"] is False
    note = save_trend(load(path), "misfit-mindset", {"kind": "sound", "name": "the low drone", "note": "Heard it on a reel."}, path)
    assert note["rising"] is False
    assert hashtags_for(load(path), "josie-blackthorn")["sets"] == []
    assert any(section["id"] == "hashtags" for section in roster(empty_state())[0]["sections"])
