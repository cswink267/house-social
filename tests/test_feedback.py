"""Feedback replaces itself and restores the earlier mark on delete.

pytest imports this. Callers are save_feedback, delete_feedback, and
apply_series. The user said continue, one todo item at a time.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from feedback import apply_series, apply_tags, correct_feedback, delete_feedback, save_feedback  # noqa: E402
from store import empty_state, load  # noqa: E402


def test_a_mark_hides_an_ahead_shape_and_delete_restores_it(tmp_path: Path):
    path = tmp_path / "state.json"
    state = empty_state()
    suggestions = [{"id": "question", "name": "Question", "detail": "Question averaged 20 engagements (n=3)."}]
    first = save_feedback(state, "okay", {"kind": "series", "target": "question", "verdict": "better", "note": "keep the question"}, path)
    assert first["lines"] == ["Better: 1"]
    assert "%" not in " ".join(first["lines"])
    second = correct_feedback(load(path), "okay", first["entries"][0]["id"], {"verdict": "off-brand", "note": "not this"}, path)
    assert second["lines"] == ["Off-brand: 1"]
    assert apply_series(suggestions, load(path), "okay") == []
    restored = delete_feedback(load(path), "okay", second["entries"][0]["id"], path)
    assert restored["entries"][0]["verdict"] == "better"
    assert apply_series(suggestions, load(path), "okay")[0]["id"] == "question"
    cleared = delete_feedback(load(path), "okay", restored["entries"][0]["id"], path)
    assert cleared["lines"] == ["No feedback yet."]
    assert apply_series(suggestions, load(path), "okay")[0]["detail"].startswith("Question averaged")


def test_a_better_tag_is_kept_without_inventing_a_gap(tmp_path: Path):
    path = tmp_path / "state.json"
    save_feedback(empty_state(), "okay", {"kind": "hashtags", "target": "ember", "verdict": "better"}, path)
    found = apply_tags({"tags": [], "detail": "No hashtag is clearly ahead for this brand."}, load(path), "okay")
    assert found["tags"] == ["ember"]
    assert "not a gap" in found["detail"]
    assert "%" not in found["detail"]
    save_feedback(load(path), "okay", {"kind": "hashtags", "target": "ember", "verdict": "irrelevant"}, path)
    gone = apply_tags({"tags": ["ember"], "detail": "These tags are ahead on this brand's posts."}, load(path), "okay")
    assert gone["tags"] == []
    assert "marked off" in gone["detail"]
