"""The inbox keeps a reply as a draft and never stores a token."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from inbox import refresh_inbox, save_inbox_reply, suggest_inbox_reply  # noqa: E402
from meta import MetaError, gather_inbox  # noqa: E402
from store import empty_state, load, roster, save  # noqa: E402
from voice import guide_for  # noqa: E402


def test_inbox_snapshot_keeps_replies_and_redacts_tokens(tmp_path: Path):
    path = tmp_path / "state.json"
    state = empty_state()
    state = {
        **state,
        "connections": [{
            "brand_id": "misfit-mindset",
            "platform": "facebook",
            "external_id": "page",
            "token_vault": "vault:example",
        }],
        "pulls": {"misfit-mindset": {"posts": [{"id": "post-1", "platform": "facebook"}]}},
    }
    save(state, path)

    def gather(platform, external_id, token, post_ids):
        assert token == "fixture-token"
        assert post_ids == ["post-1"]
        return {
            "items": [
                {
                    "id": "facebook:comment:1",
                    "kind": "comment",
                    "platform": "facebook",
                    "author": "A",
                    "text": "Does this land?",
                    "at": "2026-10-21T15:00:00+00:00",
                    "permalink": "https://example.com/c",
                },
                {
                    "id": "facebook:dm:2",
                    "kind": "dm",
                    "platform": "facebook",
                    "author": "B",
                    "text": "access_token=fixture-token hello",
                    "at": "2026-10-21T14:00:00+00:00",
                    "permalink": "",
                },
            ],
            "errors": ["facebook messages: access_token=fixture-token"],
        }

    view = refresh_inbox(load(path), "misfit-mindset", path, reader=lambda _name: "fixture-token", gather=gather)
    assert view["sending"] is False
    assert view["items"][0]["needs_attention"] is True
    raw = path.read_text(encoding="utf-8")
    assert "fixture-token" not in raw
    assert "REDACTED" in raw
    save_inbox_reply(load(path), "facebook:comment:1", {"reply": "You can name it."}, path)
    again = refresh_inbox(load(path), "misfit-mindset", path, reader=lambda _name: "fixture-token", gather=gather)
    kept = next(item for item in again["items"] if item["id"] == "facebook:comment:1")
    assert kept["reply"] == "You can name it."
    quiet = save_inbox_reply(load(path), "facebook:dm:2", {"reply": "", "dismissed": True}, path)
    assert quiet["needs_attention"] is False

    def complete(messages):
        assert "just stay positive" in messages[0]["content"].lower()
        return json.dumps({"text": "Just stay positive. You felt it."})

    suggested = suggest_inbox_reply(load(path), "facebook:comment:1", guide_for("misfit-mindset"), complete, path)
    assert "just stay positive" not in suggested["reply"].lower()
    assert "you" in suggested["reply"].lower()
    assert suggested["sending"] is False

    def getter(url, token, params):
        if str(url).endswith("/comments"):
            return {"data": [{"id": "9", "message": "Hi?", "created_time": "2026-10-21T15:00:00+0000"}]}
        raise MetaError("nope access_token=SECRET")

    found = gather_inbox("facebook", "page", "tok", ["post"], getter=getter)
    assert found["items"][0]["kind"] == "comment"
    assert "SECRET" not in json.dumps(found)
    threads = gather_inbox("threads", "user", "tok", [], getter=getter)
    assert any("Threads messages are not" in line for line in threads["errors"])
    assert any(section["id"] == "inbox" for section in roster(empty_state())[0]["sections"])


def test_a_comment_becomes_an_idea_only_when_the_post_is_ahead_or_it_asks(tmp_path: Path):
    path = tmp_path / "state.json"
    posts = [{"id": "big", "engagements": 30, "preview": "You felt that dread."}]
    posts += [{"id": f"q{i}", "engagements": 4, "preview": "A quiet line."} for i in range(3)]
    state = {
        **empty_state(),
        "inbox": [
            {"id": "c-ahead", "brand_id": "misfit-mindset", "kind": "comment", "platform": "facebook", "author": "A", "text": "Say more about the dread.", "post_id": "big", "reply": ""},
            {"id": "c-ask", "brand_id": "misfit-mindset", "kind": "comment", "platform": "facebook", "author": "B", "text": "Does the night keep it?", "post_id": "q0", "reply": "You can leave it there."},
            {"id": "c-quiet", "brand_id": "misfit-mindset", "kind": "comment", "platform": "facebook", "author": "C", "text": "Nice.", "post_id": "q0", "reply": ""},
            {"id": "c-dm", "brand_id": "misfit-mindset", "kind": "dm", "platform": "facebook", "author": "D", "text": "Can you answer this?", "reply": ""},
        ],
    }
    save(state, path)
    from inbox import inbox_for, keep_inbox_idea, keep_inbox_voice

    view = inbox_for(load(path), "misfit-mindset", posts)
    ahead = next(item for item in view["items"] if item["id"] == "c-ahead")
    assert ahead["ahead"] is True
    assert ahead["needs_attention"] is True
    assert "30" in ahead["prompt"]
    assert "3×" in ahead["prompt"]
    assert "%" not in ahead["prompt"]
    assert ahead["sending"] is False
    quiet = next(item for item in view["items"] if item["id"] == "c-quiet")
    assert quiet["ahead"] is False
    assert "not on a post" in quiet["prompt"]
    kept = keep_inbox_idea(load(path), "c-ahead", posts, path)
    assert kept["source"] == "comment"
    assert kept["text"] == "Say more about the dread."
    asked = keep_inbox_idea(load(path), "c-ask", posts, path)
    assert "?" in asked["text"]
    try:
        keep_inbox_idea(load(path), "c-quiet", posts, path)
    except Exception as exc:
        assert "not a question" in str(exc)
    else:
        raise AssertionError("a quiet comment became an idea")
    try:
        keep_inbox_idea(load(path), "c-dm", posts, path)
    except Exception as exc:
        assert "not a content idea" in str(exc)
    else:
        raise AssertionError("a message became an idea")
    try:
        keep_inbox_voice(load(path), "c-ahead", path=path)
    except Exception as exc:
        assert "Write the reply" in str(exc)
    else:
        raise AssertionError("an empty reply entered the voice")
    voiced = keep_inbox_voice(load(path), "c-ask", path=path)
    texts = [item["text"] for item in voiced["voice"]["examples"]]
    assert "You can leave it there." in texts
    assert "Does the night keep it?" not in texts
