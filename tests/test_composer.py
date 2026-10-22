"""The composer can name a pattern. It cannot invent a score.

pytest imports this. Callers are read_draft, remix_source, and assist.
A draft reading stores pattern lines, misses, and similar posts. The user
asked the composer to use voice and real performance, including a remix
only from a post that is actually ahead.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapt import DraftError  # noqa: E402
from analytics_desk import read_draft, remix_source  # noqa: E402
from assist import assist  # noqa: E402
from voice import guide_for  # noqa: E402


def _post(name, preview, engagements):
    return {
        "id": name,
        "preview": preview,
        "engagements": engagements,
        "published_at": "2026-10-20T16:00:00+00:00",
    }


def _split():
    short = [_post(f"s{i}", "You felt that dread.", 20) for i in range(3)]
    long = [_post(f"l{i}", "Monday morning still carries the same quiet mark for them.", 4) for i in range(3)]
    return short + long


def test_draft_reading_uses_a_real_pattern_and_refuses_a_score():
    posts = _split()
    missed = read_draft("Monday morning still carries the same quiet mark for them today.", posts)
    assert missed["misses"]
    assert "first sentence" in missed["misses"][0].lower()
    assert "score" not in json.dumps(missed)
    assert "%" not in json.dumps(missed)
    held = read_draft("You felt that dread extra.", posts)
    assert held["misses"] == []
    assert "already matches" in held["improve"]
    assert any(item["engagements"] == 20 and item["ahead"] is False for item in held["similar"])
    thin = read_draft("You felt that dread.", posts[:2] + posts[3:5])
    assert thin["misses"] == []
    assert "clear enough" in thin["improve"]


def test_remix_only_starts_from_a_post_that_is_ahead():
    loud = [_post("big", "You felt that dread.", 30)] + [_post(f"s{i}", "A quiet evening post.", 4) for i in range(3)]
    reading = read_draft("Something else entirely here.", loud)
    assert reading["remix"]["ready"] is True
    assert remix_source(loud, "You felt that dread.")["id"] == "big"
    try:
        remix_source(loud, "A quiet evening post.")
    except DraftError as exc:
        assert "not ahead" in str(exc)
    else:
        raise AssertionError("a quiet post was remixed")
    close = [_post("mid", "You felt that dread.", 8)] + [_post(f"n{i}", "A quiet evening post.", 4) for i in range(3)]
    assert read_draft("", close)["remix"]["ready"] is False


def test_draft_needs_a_subject_and_a_comment_stays_in_voice():
    guide = guide_for("misfit-mindset")

    def complete(messages):
        blob = json.dumps(messages)
        assert "first comment" in blob.lower()
        assert "just stay positive" in blob.lower()
        return json.dumps({"text": "Just stay positive. You can sit with that."})

    with pytest.raises(DraftError, match="subject"):
        assist(guide, "draft", "", complete=complete)
    result = assist(guide, "comment", "You felt the dread.", complete=complete)
    assert "just stay positive" not in result["text"].lower()
    assert result["text"]
