"""An approver gets the post by email and answers by replying."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import approval_mail  # noqa: E402
from adapt import DraftError  # noqa: E402
from approval import approval_for, save_steps, submit_review  # noqa: E402
from approval_mail import mail_view, poll_replies, read_reply, save_mail_settings, send_test_mail, send_waiting  # noqa: E402
from store import create_piece, empty_state, load, update_piece  # noqa: E402

IDEA = "The fire held. The night did not."
INBOX = "approvals@agentmail.to"
KEYS = {"house-social.agentmail.api_key": "am-fixture-key", "house-social.resend.api_key": "re-fixture-key"}


class FakeMail:
    def __init__(self):
        self.sent = []
        self.inbox = []
        self.bodies = {}
        self.fail = False

    def __call__(self, method, url, key, payload):
        assert key in KEYS.values()
        if self.fail:
            raise approval_mail.MailError("The mail service said (403): forbidden")
        if method == "POST":
            self.sent.append((url, payload))
            return {"message_id": f"m{len(self.sent)}", "thread_id": "t1", "id": f"r{len(self.sent)}"}
        if url.endswith("/messages"):
            return {"count": len(self.inbox), "messages": self.inbox}
        message_id = url.rsplit("/", 1)[1]
        return self.bodies[message_id]

    def reply(self, message_id, sender, subject, text):
        self.inbox.append({"message_id": message_id, "from": sender, "subject": subject, "labels": ["received"]})
        self.bodies[message_id] = {"message_id": message_id, "extracted_text": text, "text": text + "\n\nOn Tue, House wrote:\n> old"}


@pytest.fixture
def fake(monkeypatch):
    mail = FakeMail()
    monkeypatch.setattr(approval_mail, "_call", mail)
    monkeypatch.setattr(approval_mail, "_read_vault", KEYS.get)
    return mail


def _house(tmp_path: Path, provider="agentmail", steps=None) -> Path:
    path = tmp_path / "state.json"
    save_mail_settings(
        empty_state(),
        {
            "provider": provider,
            "agentmail": {"inbox": INBOX, "key": "am-fixture-key"},
            "resend": {"from": "House <approvals@house.example>", "reply_to": INBOX, "key": "re-fixture-key"},
            "dashboard_url": "https://desk.example/house-social",
        },
        path,
        lambda _name, _value: True,
    )
    save_steps(load(path), "okay", steps or [{"name": "Chris", "email": "Chris@Example.com"}], path)
    return path


def _review(path: Path, when: datetime | None = None) -> str:
    piece = create_piece(load(path), "okay", IDEA, path=path)
    if when:
        update_piece(load(path), piece["id"], scheduled_for=when.isoformat(), path=path)
    submit_review(load(path), piece["id"], path)
    return piece["id"]


def _piece(path: Path, piece_id: str) -> dict:
    return next(item for item in load(path)["pieces"] if item["id"] == piece_id)


def _code(path: Path, piece_id: str) -> str:
    return _piece(path, piece_id)["approval"]["mail"]["code"]


def test_settings_keep_keys_in_the_vault(tmp_path: Path):
    written = {}
    path = tmp_path / "state.json"
    view = save_mail_settings(
        empty_state(),
        {"provider": "agentmail", "agentmail": {"inbox": "Approvals@AgentMail.to", "key": "am-fixture-key"}},
        path,
        lambda name, value: written.update({name: value}) or True,
    )
    assert written == {"house-social.agentmail.api_key": "am-fixture-key"}
    assert view["ready"] is True and view["reads_replies"] is True
    assert view["agentmail"] == {"inbox": "approvals@agentmail.to", "key_saved": True}
    assert "am-fixture-key" not in path.read_text(encoding="utf-8")
    with pytest.raises(DraftError, match="from address"):
        save_mail_settings(load(path), {"provider": "resend", "resend": {"key": "re-fixture-key"}}, path, lambda _n, _v: True)
    with pytest.raises(DraftError, match="email"):
        save_steps(load(path), "okay", [{"name": "Chris", "email": "not an address"}], path)
    assert mail_view(empty_state())["ready"] is False


def test_review_emails_the_approver_and_an_approve_reply_schedules_it(tmp_path: Path, fake: FakeMail):
    path = _house(tmp_path)
    future = datetime.now(timezone.utc) + timedelta(days=2)
    piece_id = _review(path, future)
    assert len(fake.sent) == 1
    url, payload = fake.sent[0]
    assert url.endswith(f"/inboxes/{INBOX.replace('@', '%40')}/messages/send")
    assert payload["to"] == ["chris@example.com"]
    code = _code(path, piece_id)
    assert f"[HS-{code}]" in payload["subject"]
    assert "Reply with APPROVE" in payload["text"]
    assert "hs_review=" + piece_id in payload["text"]
    assert approval_for(load(path), "okay")["people"] == [{"name": "Chris", "email": "chris@example.com"}]
    fake.reply("x1", "Chris <chris@example.com>", f"Re: [HS-{code}] Approve for Okay", "Approve. Lovely.")
    result = poll_replies(load(path), path)
    assert result["decided"] == [{"piece_id": piece_id, "decision": "approved", "status": "scheduled"}]
    piece = _piece(path, piece_id)
    assert piece["status"] == "scheduled"
    assert any("approved" in item["text"] and "by email" in item["text"] for item in load(path)["notices"])
    again = poll_replies(load(path), path)
    assert again["decided"] == []


def test_only_the_approver_counts_and_only_a_clear_first_line(tmp_path: Path, fake: FakeMail):
    path = _house(tmp_path)
    piece_id = _review(path)
    code = _code(path, piece_id)
    fake.reply("x1", "someone@else.example", f"Re: [HS-{code}]", "Approve")
    fake.reply("x2", "chris@example.com", f"Re: [HS-{code}]", "Yes, but change the hook")
    result = poll_replies(load(path), path)
    assert result["decided"] == []
    assert len(result["ignored"]) == 2
    assert _piece(path, piece_id)["status"] == "pending"
    texts = " ".join(item["text"] for item in load(path)["notices"])
    assert "not counted" in texts
    fake.reply("x3", "chris@example.com", f"RE: [HS-{code}]", "CHANGES: shorter Threads line, please")
    poll_replies(load(path), path)
    piece = _piece(path, piece_id)
    assert piece["status"] == "draft"
    assert piece["approval"]["comments"][-1]["text"] == "shorter Threads line, please"


def test_two_steps_mail_the_second_approver_after_the_first_replies(tmp_path: Path, fake: FakeMail):
    path = _house(tmp_path, steps=[{"name": "Chris", "email": "chris@example.com"}, {"name": "Dana", "email": "dana@example.com"}])
    piece_id = _review(path)
    code = _code(path, piece_id)
    fake.reply("x1", "chris@example.com", f"Re: [HS-{code}]", "approved")
    poll_replies(load(path), path)
    assert fake.sent[-1][1]["to"] == ["dana@example.com"]
    assert _piece(path, piece_id)["status"] == "pending"
    second = _code(path, piece_id)
    fake.reply("x2", "chris@example.com", f"Re: [HS-{second}]", "approve")
    poll_replies(load(path), path)
    assert _piece(path, piece_id)["status"] == "pending"
    fake.reply("x3", "dana@example.com", f"Re: [HS-{second}]", "Approve")
    poll_replies(load(path), path)
    assert _piece(path, piece_id)["status"] == "approved"


def test_resend_sends_with_the_agentmail_inbox_as_reply_to(tmp_path: Path, fake: FakeMail):
    path = _house(tmp_path, provider="resend")
    assert mail_view(load(path))["reads_replies"] is True
    _review(path)
    url, payload = fake.sent[0]
    assert url == "https://api.resend.com/emails"
    assert payload["reply_to"] == INBOX
    assert payload["from"] == "House <approvals@house.example>"
    sent = send_test_mail(load(path), "chris@example.com")
    assert sent["provider"] == "resend"


def test_mail_trouble_leaves_a_notice_and_the_review_stands(tmp_path: Path, fake: FakeMail):
    path = _house(tmp_path)
    fake.fail = True
    piece_id = _review(path)
    piece = _piece(path, piece_id)
    assert piece["status"] == "pending"
    assert "forbidden" in piece["approval"]["mail"]["error"]
    assert any("did not send" in item["text"] for item in load(path)["notices"])


def test_quiet_hours_hold_the_mail_until_they_end(tmp_path: Path, fake: FakeMail, monkeypatch):
    path = _house(tmp_path)
    state = load(path)
    state["mail_prefs"] = {"okay": {"cadence": "immediate", "body": "full", "quiet_start": 0, "quiet_end": 23}}
    from store import save

    save(state, path)
    monkeypatch.setattr(approval_mail, "_quiet", lambda *_args: True)
    piece_id = _review(path)
    assert fake.sent == []
    assert _piece(path, piece_id)["approval"]["mail"]["pending"] is True
    monkeypatch.setattr(approval_mail, "_quiet", lambda *_args: False)
    assert send_waiting(load(path), path) == 1
    assert len(fake.sent) == 1
    assert _piece(path, piece_id)["approval"]["mail"]["pending"] is False


def test_read_reply_reads_only_the_new_words():
    assert read_reply("Approve\n\nOn Mon, House wrote:\n> CHANGES") == ("approved", "")
    assert read_reply("**APPROVED** ship it") == ("approved", "ship it")
    assert read_reply("Changes - cut the second line\nand the emoji") == ("changes", "cut the second line and the emoji")
    assert read_reply("Looks good, approve") == ("", "")
    assert read_reply("> Approve") == ("", "")
