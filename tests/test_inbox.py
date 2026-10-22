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
