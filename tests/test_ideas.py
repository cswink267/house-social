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
