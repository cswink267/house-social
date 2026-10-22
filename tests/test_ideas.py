"""Ideas stay on the board until one becomes a single draft."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapt import DraftError  # noqa: E402
from ideas import draft_idea, ideas_for, save_idea  # noqa: E402
from store import empty_state, load, roster  # noqa: E402


def test_an_idea_becomes_one_draft_and_stays_on_its_brand(tmp_path: Path):
    path = tmp_path / "state.json"
    spark = save_idea(
        empty_state(),
        "misfit-mindset",
        {"text": "The Sunday dread is data.", "source": "spark", "priority": "high", "tags": ["sunday", "sunday"]},
        path,
    )
    question = save_idea(
        load(path),
        "misfit-mindset",
        {"text": "What do you do with the quiet?", "source": "question", "priority": "low"},
        path,
    )
    note = save_idea(
        load(path),
        "misfit-mindset",
        {"text": "Their line about grinding.", "source": "competitor", "link": "https://example.com/post", "priority": "normal"},
        path,
    )
    board = ideas_for(load(path), "misfit-mindset")
    assert [item["id"] for item in board["ideas"]][0] == spark["id"]
    assert spark["tags"] == ["sunday"]
    assert note["link"] == "https://example.com/post"
    assert ideas_for(load(path), "josie-blackthorn")["ideas"] == []
    made = draft_idea(load(path), question["id"], path)
    assert made["created"] is True
    assert load(path)["pieces"][0]["id"] == made["piece_id"]
    assert "quiet" in load(path)["pieces"][0]["idea"]
    again = draft_idea(load(path), question["id"], path)
    assert again["created"] is False
    assert again["piece_id"] == made["piece_id"]
    assert len(load(path)["pieces"]) == 1
    with pytest.raises(DraftError, match="http"):
        save_idea(load(path), "misfit-mindset", {"text": "Nope", "link": "javascript:alert(1)"}, path)
    assert any(section["id"] == "ideas" for section in roster(empty_state())[0]["sections"])


def test_ideas_follow_real_posts_and_do_not_invent_a_score(tmp_path: Path):
    from ideas import idea_brief, keep_shape

    path = tmp_path / "state.json"
    short = "You felt that dread."
    posts = [{"id": f"s{i}", "preview": short, "engagements": 20, "published_at": "2026-10-20T16:00:00+00:00", "piece_id": f"c{i}"} for i in range(3)]
    posts += [{"id": f"l{i}", "preview": "Monday morning still carries the same quiet mark for them.", "engagements": 4, "published_at": "2026-10-20T16:00:00+00:00", "piece_id": f"k{i}"} for i in range(3)]
    saved = save_idea(empty_state(), "misfit-mindset", {"text": short, "source": "comment", "pillar": "raw-truth"}, path)
    board = ideas_for({**load(path), "pulls": {"misfit-mindset": {"posts": posts}}}, "misfit-mindset", posts)
    card = board["ideas"][0]
    assert card["pattern"] == "Matches a pattern that is ahead."
    assert "score" not in card["pattern"].lower() or card["pattern"].startswith("No pattern")
    assert card["performed"] is False
    made = draft_idea(load(path), saved["id"], path)
    assert load(path)["pieces"][0]["pillar"] == "raw-truth"
    state = load(path)
    state["ideas"][0]["piece_id"] = "winner"
    state["pulls"] = {"misfit-mindset": {"posts": [
        {"id": "big", "preview": "You felt that dread.", "engagements": 30, "published_at": "2026-10-20T16:00:00+00:00", "piece_id": "winner"},
        *[{"id": f"q{i}", "preview": "A quiet evening post.", "engagements": 4, "published_at": "2026-10-20T16:00:00+00:00"} for i in range(3)],
    ]}}
    from store import save
    save(state, path)
    lived = ideas_for(load(path), "misfit-mindset", state["pulls"]["misfit-mindset"]["posts"])
    assert lived["archive"][0]["performed"] is True
    kept = keep_shape(load(path), "misfit-mindset", "big", path)
    assert "ahead" in kept["note"]
    try:
        keep_shape(load(path), "misfit-mindset", "q0", path)
    except DraftError as exc:
        assert "not ahead" in str(exc)
    else:
        raise AssertionError("a quiet post became a template")
    brief = idea_brief([{"name": "Raw truth"}], [], [])
    assert "No post is at least 3×" in brief
    assert "%" not in brief
    assert made["piece_id"]
