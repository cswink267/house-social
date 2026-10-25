"""A sent reply learns from counts a pull actually returned.

pytest imports this. Callers are note_sent, apply_counts, and reply_lessons.
State rows keep likes and replies, each an int or null. The user said: continue.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reply_learn import apply_counts, note_sent, reply_lessons  # noqa: E402
from store import empty_state  # noqa: E402


def _row(name: str, reply: str, likes, replies, likes_at_send=0, replies_at_send=0) -> dict:
    return {
        "id": name,
        "brand_id": "okay",
        "platform": "facebook",
        "reply": reply,
        "sent_at": "2026-10-24T20:00:00-04:00",
        "likes": likes,
        "replies": replies,
        "likes_at_send": likes_at_send,
        "replies_at_send": replies_at_send,
    }


def test_a_sent_reply_starts_without_a_count_and_a_pull_can_fill_one():
    state = note_sent(empty_state(), {"id": "facebook:comment:1", "brand_id": "okay", "platform": "facebook", "reply": "Stay with it."}, "2026-10-24T20:00:00-04:00")
    saved = state["reply_outcomes"][0]
    assert saved["likes"] is None
    assert saved["replies"] is None
    assert saved["likes_at_send"] is None
    filled = apply_counts(state, [{"id": "facebook:comment:1", "likes": 0}])
    assert filled["reply_outcomes"][0]["likes"] is None
    assert filled["reply_outcomes"][0]["likes_at_send"] == 0
    assert filled["reply_outcomes"][0]["replies"] is None
    again = apply_counts(filled, [{"id": "facebook:comment:1", "replies": 2}])
    assert again["reply_outcomes"][0]["replies"] is None
    assert again["reply_outcomes"][0]["replies_at_send"] == 2
    later = apply_counts(again, [{"id": "facebook:comment:1", "likes": 3}])
    assert later["reply_outcomes"][0]["likes"] == 3
    assert later["reply_outcomes"][0]["likes_at_send"] == 0


def test_learning_waits_for_three_and_three_and_skips_a_missing_count():
    thin = [
        _row("a", "Does this hold?", 4, None),
        _row("b", "Leave it.", 1, None),
    ]
    waiting = reply_lessons(thin, "okay")
    assert waiting[0]["clear"] is False
    assert "three" in waiting[0]["detail"]
    assert "%" not in waiting[0]["detail"]
    rows = [
        _row("q1", "Does the night keep it?", 12, 0),
        _row("q2", "Does it stay?", 11, 1),
        _row("q3", "Will you leave it?", 10, 2),
        _row("n1", "Stay.", 2, 0),
        _row("n2", "Leave it there.", 1, 0),
        _row("n3", "It held.", 2, 1),
        _row("missing", "Does a blank count?", None, None, None, None),
    ]
    found = {item["id"]: item for item in reply_lessons(rows, "okay")}
    lesson = found["reply-question"]
    assert lesson["clear"] is True
    assert "n=3" in lesson["detail"]
    assert "%" not in lesson["detail"]
    close = [
        _row("q1", "Does it?", 6, None),
        _row("q2", "Does it stay?", 6, None),
        _row("q3", "Will it?", 6, None),
        _row("n1", "Stay.", 5, None),
        _row("n2", "Leave it.", 5, None),
        _row("n3", "It held.", 5, None),
    ]
    quiet = next(item for item in reply_lessons(close, "okay") if item["id"] == "reply-question")
    assert quiet["clear"] is False
    assert "close" in quiet["detail"]


def test_sending_records_the_reply_and_a_later_pull_can_fill_the_count(tmp_path: Path):
    from inbox import refresh_inbox
    from inbox_send import offer_reply
    from store import load, save

    path = tmp_path / "state.json"
    state = empty_state()
    state["modes"] = {"okay": "auto"}
    state["publishing"] = {"on": True, "brands": {"okay": True}}
    state["connections"] = [{
        "brand_id": "okay",
        "platform": "facebook",
        "external_id": "1447",
        "token_vault": "vault:house-social.okay.facebook.token",
    }]
    state["inbox"] = [{
        "id": "facebook:comment:55",
        "brand_id": "okay",
        "kind": "comment",
        "platform": "facebook",
        "text": "Does this work?",
        "reply": "It does. Stay with it.",
    }]
    state["pulls"] = {"okay": {"posts": [{"id": "post-1", "platform": "facebook"}]}}
    save(state, path)

    class Poster:
        def __call__(self, method, url, params):
            return {"id": "sent-1"}

    offer_reply(load(path), "facebook:comment:55", path, http=Poster(), reader=lambda _name: "fixture-token")
    saved = load(path)["reply_outcomes"][0]
    assert saved["likes"] is None
    assert saved["likes_at_send"] is None
    assert saved["reply"].startswith("It does")
    assert "fixture-token" not in path.read_text(encoding="utf-8")

    def gather(platform, external_id, token, post_ids):
        assert token == "fixture-token"
        return {"items": [{
            "id": "facebook:comment:55",
            "kind": "comment",
            "platform": "facebook",
            "text": "Does this work?",
            "likes": 4,
        }], "errors": []}

    refresh_inbox(load(path), "okay", path, reader=lambda _name: "fixture-token", gather=gather)
    filled = load(path)["reply_outcomes"][0]
    assert filled["likes_at_send"] == 4
    assert filled["likes"] is None

    def later(platform, external_id, token, post_ids):
        return {"items": [{
            "id": "facebook:comment:55",
            "kind": "comment",
            "platform": "facebook",
            "text": "Does this work?",
            "likes": 7,
        }], "errors": []}

    refresh_inbox(load(path), "okay", path, reader=lambda _name: "fixture-token", gather=later)
    grown = load(path)["reply_outcomes"][0]
    assert grown["likes_at_send"] == 4
    assert grown["likes"] == 7
