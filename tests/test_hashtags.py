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


def test_sets_follow_a_pillar_and_suggestions_stay_on_this_brand(tmp_path: Path):
    path = tmp_path / "state.json"
    saved = save_set(
        empty_state(),
        "misfit-mindset",
        {"name": "Campfire", "tags": ["ember", "camp"], "pillar": "campfire", "campaign": "October"},
        path,
    )
    assert saved["pillar"] == "campfire"
    assert saved["campaign"] == "October"
    yes = [_post(f"y{i}", 20, "#ember #camp", format="feed") for i in range(3)]
    no = [_post(f"n{i}", 4, "quiet night", format="text") for i in range(3)]
    banned = [_post(f"g{i}", 30, "#good", format="feed") for i in range(3)]
    quiet = [_post(f"q{i}", 4, "no tag", format="text") for i in range(3)]
    view = hashtags_for(load(path), "misfit-mindset", yes + no)
    card = view["sets"][0]
    assert card["performance"]["ahead"] is True
    assert "20.0" in card["performance"]["detail"]
    assert "%" not in card["performance"]["detail"]
    assert "ember" in view["suggestion"]["tags"]
    assert "popularity chart" in view["suggestion"]["detail"]
    held = hashtags_for(load(path), "misfit-mindset", banned + quiet)
    assert "good" not in held["suggestion"]["tags"]
    assert held["suggestion"]["tags"] == []
    pillar = hashtags_for(load(path), "misfit-mindset", yes + no)
    music = next(item for item in pillar["by_pillar"] if item["pillar"] == "music")
    assert music["tags"] == []
    fire = next(item for item in pillar["by_pillar"] if item["pillar"] == "campfire")
    assert "ember" in fire["tags"]

    inside = save_trend(load(path), "misfit-mindset", {"kind": "topic", "name": "campfire night", "note": "From the pillar."}, path)
    outside = save_trend(load(path), "misfit-mindset", {"kind": "sound", "name": "the low drone", "note": "Heard it on a reel."}, path)
    shaped = save_trend(load(path), "misfit-mindset", {"kind": "format", "name": "feed", "note": "Our own posts."}, path)
    shown = hashtags_for(load(path), "misfit-mindset", yes + no)
    assert any(item["id"] == inside["id"] for item in shown["feed"])
    assert any(item["id"] == outside["id"] for item in shown["outside"])
    form = next(item for item in shown["trends"] if item["id"] == shaped["id"])
    assert form["rising"] is False
    assert "ahead" in form["result"]
    assert "popularity chart" in form["result"]
    assert "%" not in form["result"]

    from hashtags import use_ahead

    piece = create_piece(load(path), "misfit-mindset", "The fire held. The night did not.", path=path)
    used = use_ahead(load(path), "misfit-mindset", piece["id"], yes + no, path=path)
    stored = next(item for item in load(path)["pieces"] if item["id"] == piece["id"])
    assert "ember" in stored["variants"]["instagram"]["hashtags"]
    assert "#ember" not in stored["variants"]["instagram"]["body"]
    assert used["tags"]
    with pytest.raises(DraftError, match="clearly ahead"):
        use_ahead(load(path), "misfit-mindset", piece["id"], yes + no, pillar="music", path=path)
