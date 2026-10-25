"""Send a comment reply when the mode and the posting switches allow it.

Manual only suggests. Approval emails the draft. Fully autonomous sends a
comment when both posting switches are on. Direct messages stay drafts.
Every attempt is written to the activity log. Tokens stay in the vault.

Callers: offer_reply from POST /inbox/{id}/offer, send_approved_replies from
the posting worker, take_reply_mail from the approval-mail poll.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from adapt import DraftError
from meta import GRAPH, THREADS, redact
from modes import _log, _mode
from publish import is_live
from store import _copy, _read_vault, load, resolve_brand, save

REPLY_LIMIT = 8
_ZONE = ZoneInfo("America/New_York")


def offer_reply(state: dict, item_id: str, path: Path | None = None, *, http=None, reader=None, spec: dict | None = None) -> dict:
    """The button. Manual refuses. Approval emails. Auto sends when posting is on."""
    if isinstance(spec, dict) and str(spec.get("reply") or "").strip():
        from inbox import save_inbox_reply

        save_inbox_reply(state, item_id, {"reply": spec.get("reply")}, path)
        state = load(path) if path else load()
    item = _item(state, item_id)
    brand = resolve_brand(state, str(item.get("brand_id") or ""))
    mode = _mode(state, brand.id)
    try:
        if item.get("reply_state") == "sent":
            raise DraftError("That reply was already sent. Nothing else was sent.")
        if item.get("reply_state") == "pending":
            raise DraftError("That reply is already waiting on email. Nothing else was sent.")
        if item.get("reply_state") == "approved":
            raise DraftError("That reply is approved. It sends when posting is on.")
        _guard(state, item)
        if mode == "manual":
            raise DraftError("Manual only suggests a reply. Nothing was sent.")
        if mode == "approval":
            return _email(state, item, path, reader=reader, http=http)
        if mode != "auto":
            raise DraftError("Manual only suggests a reply. Nothing was sent.")
        _switches(state, brand.id)
        return _send(state, item, path, http=http, reader=reader, mode=mode)
    except DraftError as exc:
        _record(state, brand.id, mode, item, str(exc), path)
        raise


def send_approved_replies(state: dict, path: Path | None = None, *, http=None, reader=None) -> list[str]:
    """Send replies an approver already accepted, when posting is on."""
    sent = []
    for item in list(state.get("inbox") or []):
        if item.get("reply_state") != "approved":
            continue
        brand_id = str(item.get("brand_id") or "")
        mode = _mode(state, brand_id)
        try:
            _guard(load(path) if path else load(), _item(load(path) if path else load(), item["id"]))
            _switches(load(path) if path else load(), brand_id)
            _send(load(path) if path else load(), _item(load(path) if path else load(), item["id"]), path, http=http, reader=reader, mode=mode)
            sent.append(item.get("id") or "")
        except DraftError as exc:
            fresh = _item(load(path) if path else load(), item["id"])
            if fresh.get("reply_hold") == str(exc):
                continue
            current = _record(load(path) if path else load(), brand_id, mode, fresh, str(exc), path)
            _mark(current, item["id"], {"reply_hold": str(exc)[:180]}, path)
    return sent


def take_reply_mail(state: dict, code: str, sender: str, text: str, path: Path | None = None) -> dict | None:
    """An APPROVE on a reply email lets the worker send it. CHANGES keeps the draft."""
    from approval import _steps
    from approval_mail import _same, approver_email, read_reply

    item = next(
        (row for row in state.get("inbox") or [] if str(row.get("reply_code") or "").upper() == str(code or "").upper() and row.get("reply_state") == "pending"),
        None,
    )
    if not item:
        return None
    brand_id = str(item.get("brand_id") or "")
    name = (_steps(state, brand_id) or ["Approver"])[0]
    expected = approver_email(state, brand_id, name)
    verdict, note = read_reply(text)
    known = _same(sender, expected)
    if not known:
        _record(state, brand_id, "approval", item, f"A reply came from {sender or 'an unknown sender'}, not {name}. Nothing was sent.", path)
        return {"id": item["id"], "decision": "", "status": "pending"}
    if verdict == "approved":
        _mark(state, item["id"], {"reply_state": "approved", "reply_hold": ""}, path)
        _record(load(path) if path else load(), brand_id, "approval", item, f"{name} approved the reply. It sends when posting is on.", path)
        return {"id": item["id"], "decision": "approved", "status": "approved"}
    if verdict == "changes":
        _mark(state, item["id"], {"reply_state": "", "reply_note": note, "reply_hold": ""}, path)
        _record(load(path) if path else load(), brand_id, "approval", item, f"{name} asked for changes. Nothing was sent.", path)
        return {"id": item["id"], "decision": "changes", "status": "draft"}
    _record(state, brand_id, "approval", item, f"{name}'s reply did not start with APPROVE or CHANGES. Nothing was sent.", path)
    return {"id": item["id"], "decision": "", "status": "pending"}


def send_reply_mail(state: dict, item: dict, text: str, path: Path | None = None, reader=None, http=None) -> dict:
    from approval import _steps
    from approval_mail import _html, _ready, _send, approver_email, new_code

    book = state.get("mail") if isinstance(state.get("mail"), dict) else {}
    if not _ready(book):
        raise DraftError("Approval email is not ready. The reply stays a draft.")
    brand_id = str(item.get("brand_id") or "")
    name = (_steps(state, brand_id) or ["Approver"])[0]
    to = approver_email(state, brand_id, name)
    if not to:
        raise DraftError("The first approver needs an email. The reply stays a draft.")
    code = new_code()
    body = (
        f"Reply for {brand_id} on {item.get('platform')}.\n\n"
        f"They wrote: {item.get('text')}\n\n"
        f"Draft: {text}\n\n"
        "Reply with APPROVE on the first line to let it send, or CHANGES and what to change.\n"
        "A direct message is never sent from this desk.\n"
    )
    _send(book, to, f"[HS-{code}] Reply on {item.get('platform')}", body, _html(body), reader=reader, http=http)
    return {"to": to, "code": code}


def _email(state: dict, item: dict, path: Path | None, *, reader, http) -> dict:
    text = str(item.get("reply") or "").strip()
    mailed = send_reply_mail(state, item, text, path, reader=reader, http=http)
    updated = _mark(state, item["id"], {"reply_state": "pending", "reply_code": mailed["code"], "reply_hold": ""}, path)
    logged = _record(updated, item["brand_id"], "approval", item, f"Emailed {mailed['to']}. Nothing was sent.", path)
    return _view(_item(logged, item["id"]))


def _send(state: dict, item: dict, path: Path | None, *, http, reader, mode: str) -> dict:
    brand_id = str(item.get("brand_id") or "")
    if _sent_today(state, brand_id) >= REPLY_LIMIT:
        raise DraftError(f"The reply limit is {REPLY_LIMIT} today. Nothing was sent.")
    fresh = _item(load(path) if path else load(), item["id"])
    if fresh.get("reply_state") == "sent":
        raise DraftError("That reply was already sent. Nothing else was sent.")
    text = str(fresh.get("reply") or "").strip()
    token = (reader or _read_vault)(_vault_name(state, fresh))
    if not token:
        raise DraftError("No token in the vault. Connect the account again. Nothing was sent.")
    _post(http, state, item, token, text)
    stamp = datetime.now(_ZONE).isoformat(timespec="seconds")
    updated = _mark(state, item["id"], {"reply_state": "sent", "sent_at": stamp, "reply_hold": ""}, path)
    from reply_learn import note_sent

    updated = note_sent(updated, {**fresh, "reply": text, "brand_id": brand_id}, stamp)
    logged = _record(updated, brand_id, mode, item, f"Sent on {item.get('platform')}.", path)
    return _view(_item(logged, item["id"]))


def _guard(state: dict, item: dict) -> None:
    if item.get("kind") == "dm":
        raise DraftError("Direct messages stay drafts. Nothing was sent.")
    if item.get("kind") != "comment":
        raise DraftError("Mentions stay drafts. Nothing was sent.")
    text = str(item.get("reply") or "").strip()
    if not text:
        raise DraftError("Write the reply first. Nothing was sent.")
    if len(text) > 2000:
        raise DraftError("That reply is too long. Nothing was sent.")
    from voice import guide_for

    guide = guide_for(str(item.get("brand_id") or ""), (state.get("voices") or {}).get(item.get("brand_id")))
    folded = text.lower()
    for phrase in guide.get("banned") or []:
        if phrase and str(phrase).lower() in folded:
            raise DraftError("That reply uses a banned phrase. Nothing was sent.")


def _switches(state: dict, brand_id: str) -> None:
    if not is_live(state, brand_id):
        book = state.get("publishing") if isinstance(state.get("publishing"), dict) else {}
        if not book.get("on"):
            raise DraftError("Posting is off in House settings. Nothing was sent.")
        raise DraftError("Posting is off for this brand. Nothing was sent.")
    from support import assert_running

    assert_running(state, brand_id)


def _post(http, state: dict, item: dict, token: str, text: str) -> None:
    parts = str(item.get("id") or "").split(":", 2)
    if len(parts) < 3:
        raise DraftError("That comment has no id to answer. Nothing was sent.")
    platform, _kind, target = parts
    call = http
    if call is None:
        from publish import _call

        call = _call
    if platform == "facebook":
        call("POST", f"{GRAPH}/{target}/comments", {"message": text, "access_token": token})
    elif platform == "instagram":
        call("POST", f"{GRAPH}/{target}/replies", {"message": text, "access_token": token})
    elif platform == "threads":
        me = _external(state, item)
        made = call("POST", f"{THREADS}/{me}/threads", {"media_type": "TEXT", "text": text, "reply_to_id": target, "access_token": token})
        creation = str((made or {}).get("id") or "")
        if not creation:
            raise DraftError("Threads did not accept the reply. Nothing else was sent.")
        call("POST", f"{THREADS}/{me}/threads_publish", {"creation_id": creation, "access_token": token})
    else:
        raise DraftError("Channels are facebook, instagram, and threads. Nothing was sent.")


def _record(state: dict, brand_id: str, mode: str, item: dict, outcome: str, path: Path | None) -> dict:
    updated = _log(state, brand_id, mode or "manual", "reply", str(item.get("id") or ""), str(item.get("platform") or ""), redact(outcome))
    save(updated, path)
    return updated


def _mark(state: dict, item_id: str, changes: dict, path: Path | None) -> dict:
    updated = _copy(state)
    found = False
    rows = []
    for item in updated.get("inbox") or []:
        if item.get("id") == item_id:
            rows.append({**item, **changes})
            found = True
        else:
            rows.append(item)
    if not found:
        raise DraftError("That note is not in the inbox.")
    updated["inbox"] = rows
    save(updated, path)
    return updated


def _item(state: dict, item_id: str) -> dict:
    found = next((item for item in state.get("inbox") or [] if item.get("id") == item_id), None)
    if not found:
        raise DraftError("That note is not in the inbox.")
    return found


def _view(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "reply_state": item.get("reply_state") or "",
        "reply": item.get("reply") or "",
        "sent": item.get("reply_state") == "sent",
    }


def _sent_today(state: dict, brand_id: str) -> int:
    today = datetime.now(_ZONE).date().isoformat()
    count = 0
    for item in state.get("inbox") or []:
        if item.get("brand_id") != brand_id or item.get("reply_state") != "sent":
            continue
        if str(item.get("sent_at") or "").startswith(today):
            count += 1
    return count


def _vault_name(state: dict, item: dict) -> str:
    connection = next(
        (
            row for row in state.get("connections") or []
            if row.get("brand_id") == item.get("brand_id") and row.get("platform") == item.get("platform") and row.get("via") != "facebook"
        ),
        None,
    )
    if connection is None and item.get("platform") == "instagram":
        connection = next(
            (
                row for row in state.get("connections") or []
                if row.get("brand_id") == item.get("brand_id") and row.get("platform") == "facebook"
            ),
            None,
        )
    if not connection:
        return ""
    return str(connection.get("token_vault") or "").removeprefix("vault:")


def _external(state: dict, item: dict) -> str:
    connection = next(
        (
            row for row in state.get("connections") or []
            if row.get("brand_id") == item.get("brand_id") and row.get("platform") == item.get("platform")
        ),
        {},
    )
    return str(connection.get("external_id") or "")
