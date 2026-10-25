"""A reply follows the brand mode. A message stays a draft.

pytest imports this. Callers are offer_reply and send_approved_replies.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapt import DraftError  # noqa: E402
from inbox_send import offer_reply, send_approved_replies  # noqa: E402
from store import empty_state, load, save  # noqa: E402


def _state(mode: str, house: bool = True, brand: bool = True) -> dict:
    state = empty_state()
    state["modes"] = {"okay": mode}
    state["publishing"] = {"on": house, "brands": {"okay": brand}}
    state["connections"] = [{
        "brand_id": "okay",
        "platform": "facebook",
        "external_id": "1447",
        "token_vault": "vault:house-social.okay.facebook.token",
    }]
    state["voices"] = {"okay": {"banned": ["rise and grind"]}}
    state["inbox"] = [{
        "id": "facebook:comment:55",
        "brand_id": "okay",
        "kind": "comment",
        "platform": "facebook",
        "author": "A fan",
        "text": "Does this work?",
        "reply": "It does. Stay with it.",
    }, {
        "id": "facebook:dm:9",
        "brand_id": "okay",
        "kind": "dm",
        "platform": "facebook",
        "text": "A private note",
        "reply": "Not from here.",
    }]
    state["approval_steps"] = {"okay": [{"name": "Chris", "email": "chris@example.com"}]}
    state["mail"] = {
        "provider": "agentmail",
        "agentmail": {"inbox": "approvals@agentmail.to", "key_vault": "vault:house-social.agentmail.api_key"},
    }
    return state


class Poster:
    def __init__(self):
        self.calls = []

    def __call__(self, method, url, params):
        self.calls.append((method, url, params))
        return {"id": "sent-1"}


def test_manual_only_suggests_and_a_message_stays_a_draft(tmp_path: Path):
    path = tmp_path / "state.json"
    save(_state("manual"), path)
    poster = Poster()
    with pytest.raises(DraftError, match="suggests"):
        offer_reply(load(path), "facebook:comment:55", path, http=poster, reader=lambda _name: "fixture-token")
    with pytest.raises(DraftError, match="Direct messages stay drafts"):
        offer_reply(load(path), "facebook:dm:9", path, http=poster, reader=lambda _name: "fixture-token")
    assert poster.calls == []
    assert load(path)["mode_log"][0]["action"] == "reply"
    assert "fixture-token" not in path.read_text(encoding="utf-8")


def test_auto_sends_only_when_both_switches_are_on(tmp_path: Path):
    path = tmp_path / "state.json"
    save(_state("auto", house=False), path)
    poster = Poster()
    with pytest.raises(DraftError, match="House settings"):
        offer_reply(load(path), "facebook:comment:55", path, http=poster, reader=lambda _name: "fixture-token")
    assert poster.calls == []
    save(_state("auto", brand=False), path)
    with pytest.raises(DraftError, match="this brand"):
        offer_reply(load(path), "facebook:comment:55", path, http=poster, reader=lambda _name: "fixture-token")
    save(_state("auto"), path)
    state = load(path)
    state["inbox"][0]["reply"] = "Rise and grind."
    save(state, path)
    with pytest.raises(DraftError, match="banned"):
        offer_reply(load(path), "facebook:comment:55", path, http=poster, reader=lambda _name: "fixture-token")
    state = load(path)
    state["inbox"][0]["reply"] = "It does. Stay with it."
    save(state, path)
    sent = offer_reply(load(path), "facebook:comment:55", path, http=poster, reader=lambda _name: "fixture-token")
    assert sent["reply_state"] == "sent"
    assert poster.calls[0][0] == "POST"
    assert poster.calls[0][1].endswith("/55/comments")
    assert "fixture-token" not in path.read_text(encoding="utf-8")
    log = load(path)["mode_log"][0]
    assert log["action"] == "reply"
    assert log["outcome"].startswith("Sent")


def test_approval_emails_the_draft_and_a_yes_lets_the_worker_send(tmp_path: Path, monkeypatch):
    path = tmp_path / "state.json"
    save(_state("approval"), path)
    mailed = {}

    def mail(state, item, text, path=None, reader=None, http=None):
        mailed["to"] = "chris@example.com"
        return {"to": "chris@example.com", "code": "ab12cd"}

    monkeypatch.setattr("inbox_send.send_reply_mail", mail)
    offered = offer_reply(load(path), "facebook:comment:55", path, http=Poster(), reader=lambda _name: "fixture-token")
    assert offered["reply_state"] == "pending"
    assert mailed["to"] == "chris@example.com"
    state = load(path)
    state["inbox"][0]["reply_state"] = "approved"
    save(state, path)
    poster = Poster()
    send_approved_replies(load(path), path, http=poster, reader=lambda _name: "fixture-token")
    assert poster.calls
    assert load(path)["inbox"][0]["reply_state"] == "sent"


def test_an_emailed_reply_approval_is_read_back_and_sent(tmp_path: Path, monkeypatch):
    import approval_mail
    from approval import save_steps
    from approval_mail import poll_replies

    path = tmp_path / "state.json"
    save(_state("approval"), path)
    save_steps(load(path), "okay", [{"name": "Chris", "email": "chris@example.com"}], path)
    sent, inbox = [], []

    def mail(method, url, key, payload):
        if url.endswith("/inboxes"):
            return {"inboxes": [{"inbox_id": "approvals@agentmail.to"}]}
        if method == "POST":
            sent.append(payload)
            return {"message_id": "m1"}
        if url.endswith("/messages"):
            return {"messages": inbox}
        return {"extracted_text": "approve"}

    monkeypatch.setattr(approval_mail, "_call", mail)
    monkeypatch.setattr(approval_mail, "_read_vault", lambda _name: "am-fixture-key")
    offered = offer_reply(load(path), "facebook:comment:55", path, reader=lambda _name: "fixture-token")
    assert offered["reply_state"] == "pending"
    code = load(path)["inbox"][0]["reply_code"]
    assert code == code.upper() and len(code) == 6
    assert f"[HS-{code}]" in sent[0]["subject"]
    # Mail clients sometimes change the case of a subject. It still counts.
    inbox.append({"message_id": "x1", "from": "Chris <chris@example.com>", "subject": f"Re: [hs-{code.lower()}] Reply", "labels": ["received"]})
    read = poll_replies(load(path), path)
    assert read["decided"][0]["decision"] == "approved"
    assert load(path)["inbox"][0]["reply_state"] == "approved"
    poster = Poster()
    send_approved_replies(load(path), path, http=poster, reader=lambda _name: "fixture-token")
    assert load(path)["inbox"][0]["reply_state"] == "sent"
