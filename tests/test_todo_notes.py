"""Todo notes stay off until they are turned on, and they do not delete.

pytest imports this. Callers are set_notes and append_note.
The user said continue, and that the notes matter because he trusts them.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapt import DraftError  # noqa: E402
from store import empty_state, load  # noqa: E402
from todo_notes import append_note, notes_view, set_notes  # noqa: E402


def _spec(heading="Series fill is not on the desk"):
    return {
        "heading": heading,
        "happened": "fill_series works in code. The Series desk has no control for it. vault:house.secret",
        "why": "A paused series cannot be filled from the desk.",
        "next": "Add pause and fill on the Series desk. Do not invent a topic.",
        "desk": "Series",
    }


def test_notes_are_off_until_enabled_and_a_repeat_is_refused(tmp_path: Path):
    path = tmp_path / "state.json"
    todo = tmp_path / "TODO.md"
    todo.write_text("# Later\n\n## 1. Already\n\n**Status: complete.**\n", encoding="utf-8")
    state = empty_state()
    assert notes_view(state, "okay")["on"] is False
    with pytest.raises(DraftError, match="off"):
        append_note(state, "okay", _spec(), path, todo)
    turned = set_notes(state, "okay", True, "global", path)
    assert turned["global"] is True
    added = append_note(load(path), "okay", _spec(), path, todo)
    assert added["added"] is True
    text = todo.read_text(encoding="utf-8")
    assert "Series fill is not on the desk" in text
    assert "Already" in text
    assert "house.secret" not in text
    assert "/home/" not in text
    again = append_note(load(path), "okay", _spec(), path, todo)
    assert again["added"] is False
    second = append_note(load(path), "okay", _spec("A different gap"), path, todo)
    assert second["added"] is True
    held = append_note(load(path), "okay", _spec("A third gap"), path, todo)
    assert held["added"] is False
    assert "held" in held["reason"]
    assert "### A third gap" not in todo.read_text(encoding="utf-8")


def test_a_mention_inside_a_sentence_is_not_the_section(tmp_path: Path):
    path = tmp_path / "state.json"
    todo = tmp_path / "TODO.md"
    todo.write_text('See "## Suggested improvements" in a sentence.\n', encoding="utf-8")
    set_notes(empty_state(), "okay", True, "global", path)
    append_note(load(path), "okay", _spec("A real gap"), path, todo)
    lines = todo.read_text(encoding="utf-8").splitlines()
    assert "## Suggested improvements" in lines
    assert "### A real gap" in lines
