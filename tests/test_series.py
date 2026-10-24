"""A series stays on its brand and only when the posts support it.

pytest imports this. Callers are save_series, keep_series, and apply_series.
The user said continue, one todo item at a time.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapt import DraftError  # noqa: E402
from series import apply_series, keep_series, save_series, series_for, suggest_series  # noqa: E402
from store import empty_state, load, save  # noqa: E402


def _post(name, preview, engagements, day="20", piece=""):
    return {
        "id": name,
        "brand_id": "okay",
        "preview": preview,
        "published_at": f"2026-10-{day}T15:00:00-04:00",
        "engagements": engagements,
        "piece_id": piece,
        "source": "history",
    }


def _split():
    yes = [_post(f"q{i}", "You felt that?", 20) for i in range(3)]
    no = [_post(f"n{i}", "A quiet evening post.", 4) for i in range(3)]
    return yes + no


def test_a_shape_is_suggested_only_when_it_is_already_ahead():
    found = suggest_series(_split())
    question = next(item for item in found if item["id"] == "question")
    assert "n=3" in question["detail"]
    assert "%" not in question["detail"]
    assert suggest_series(_split()[:4]) == []


def test_apply_stays_on_the_brand_and_stats_wait_for_three_uses(tmp_path: Path):
    path = tmp_path / "state.json"
    state = empty_state()
    state["history"] = _split()
    saved = save_series(
        state,
        "okay",
        {"name": "Ask", "structure": ["{topic}", "Ask the question."], "examples": ["q0"], "tags": ["raw-truth", "ask"], "hook": "Open on the feeling."},
        path,
    )
    assert saved["examples"][0]["engagements"] == 20
    assert saved["stats"]["ready"] is False
    with pytest.raises(DraftError, match="not on this brand"):
        save_series(load(path), "okay", {"name": "Nope", "structure": ["{topic}"], "examples": ["missing"]}, path)
    opened = apply_series(load(path), "okay", saved["id"], "the rent", path)
    piece = next(item for item in load(path)["pieces"] if item["id"] == opened["piece_id"])
    assert piece["series_id"] == saved["id"]
    assert "the rent" in piece["idea"]
    assert piece["brand_id"] == "okay"
    with pytest.raises(DraftError, match="stays on its brand"):
        apply_series(load(path), "josie-blackthorn", saved["id"], "another", path)
    view = series_for(load(path), "okay", q="ask", tag="raw-truth")
    assert view["items"][0]["uses"] == 1
    assert view["items"][0]["stats"]["detail"].startswith("Not enough")


def test_a_paused_series_stays_on_the_desk_and_cannot_open(tmp_path: Path):
    from support import set_series_pause

    path = tmp_path / "state.json"
    saved = save_series(empty_state(), "okay", {"name": "Ask", "structure": ["{topic}", "Ask."]}, path)
    assert series_for(load(path), "okay")["items"][0]["paused"] is False
    set_series_pause(load(path), "okay", saved["id"], True, path)
    card = series_for(load(path), "okay")["items"][0]
    assert card["paused"] is True
    assert card["name"] == "Ask"
    with pytest.raises(DraftError, match="paused"):
        apply_series(load(path), "okay", saved["id"], "the rent", path)
    assert load(path)["pieces"] == []


def test_keep_uses_the_ahead_shape_and_a_later_drop_is_only_a_notice(tmp_path: Path):
    path = tmp_path / "state.json"
    state = empty_state()
    state["history"] = _split()
    kept = keep_series(state, "okay", "question", path)
    assert kept["name"] == "Question"
    assert kept["examples"]
    early = [_post(f"e{i}", "You felt that?", 30, day=str(10 + i), piece=f"p{i}") for i in range(3)]
    late = [_post(f"l{i}", "You felt that?", 4, day=str(20 + i), piece=f"r{i}") for i in range(3)]
    current = load(path)
    current["history"] = list(current["history"]) + early + late
    current["series"][0]["uses"] = [{"piece_id": post["piece_id"], "topic": "x", "at": ""} for post in early + late]
    save(current, path)
    card = series_for(load(path), "okay")["items"][0]
    assert card["stats"]["ready"] is True
    assert card["stats"]["n"] >= 3
    assert "Nothing was deleted." in card["notice"]
    assert "%" not in card["notice"]
    with pytest.raises(DraftError, match="not ahead"):
        keep_series(empty_state(), "okay", "question", path)
