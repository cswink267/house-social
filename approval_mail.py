"""Approval email through AgentMail or Resend.

When a piece enters review, or moves to the next review step, the approver
for that step gets the three versions by email. They reply APPROVE, or
CHANGES and what to change. The desk reads replies from the AgentMail inbox
once a minute and records the decision under the approver's name, so an
approved piece with a time is scheduled and posts then.

Replies are read only from AgentMail. With Resend sending, set the reply-to
to the AgentMail inbox so replies can be read; otherwise approvers use the
link in the email. A reply counts only when it comes from the approver's own
address. API keys live in the vault, never in state.json.
"""

from __future__ import annotations

import html
import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from adapt import DraftError
from brands import PLATFORMS
from store import _copy, _read_vault, _write_vault, load, resolve_brand, roster, save

AGENTMAIL = "https://api.agentmail.to/v0"
RESEND = "https://api.resend.com/emails"
KEYS = {"agentmail": "house-social.agentmail.api_key", "resend": "house-social.resend.api_key"}
NAMES = {"facebook": "Facebook", "instagram": "Instagram", "threads": "Threads"}
_ADDRESS = re.compile(r"[^@\s<>\"']+@[^@\s<>\"']+\.[^@\s<>\"']+")
_CODE = re.compile(r"\bHS-([A-Z0-9]{6})\b")
# Strict on purpose: "yes, but change the hook" must not read as approval.
_APPROVE = re.compile(r"^(approve|approved)\b", re.I)
_CHANGES = re.compile(r"^(changes|change|reject|rejected)\b", re.I)
_QUOTED = re.compile(r"^(on .+ wrote:|-{2,}\s*original message|from: .+|>)", re.I)


class MailError(Exception):
    """The provider did not take the mail. The message never carries a key."""


# ---- Settings --------------------------------------------------------------


def mail_view(state: dict) -> dict:
    book = _book(state)
    agentmail = book.get("agentmail") or {}
    resend = book.get("resend") or {}
    provider = book.get("provider") or ""
    reads = bool(agentmail.get("inbox") and agentmail.get("key_vault"))
    return {
        "provider": provider,
        "agentmail": {"inbox": agentmail.get("inbox") or "", "key_saved": bool(agentmail.get("key_vault"))},
        "resend": {
            "from": resend.get("from") or "",
            "reply_to": resend.get("reply_to") or "",
            "key_saved": bool(resend.get("key_vault")),
        },
        "dashboard_url": book.get("dashboard_url") or "",
        "ready": _ready(book),
        "reads_replies": reads and (provider == "agentmail" or _same(resend.get("reply_to"), agentmail.get("inbox"))),
        "last_poll": book.get("last_poll") or "",
        "poll_error": book.get("poll_error") or "",
    }


def save_mail_settings(state: dict, spec: dict, path: Path | None = None, vault_write=None) -> dict:
    if not isinstance(spec, dict):
        raise DraftError("Mail settings need a provider.")
    updated = _copy(state)
    book = _book(updated)
    writer = vault_write or _write_vault
    if "provider" in spec:
        provider = str(spec.get("provider") or "").strip().lower()
        if provider not in {"", "agentmail", "resend"}:
            raise DraftError("Mail goes through AgentMail or Resend.")
        book["provider"] = provider
    pending = []
    for kind in ("agentmail", "resend"):
        row_spec = spec.get(kind)
        if not isinstance(row_spec, dict):
            continue
        row = dict(book.get(kind) or {})
        if kind == "agentmail" and "inbox" in row_spec:
            row["inbox"] = _address(row_spec.get("inbox"), "The AgentMail inbox is an address, such as approvals@agentmail.to.", allow_empty=True)
        if kind == "resend":
            if "from" in row_spec:
                row["from"] = _sender(row_spec.get("from"))
            if "reply_to" in row_spec:
                row["reply_to"] = _address(row_spec.get("reply_to"), "Replies go to an email address.", allow_empty=True)
        key = str(row_spec.get("key") or "").strip()
        if key:
            if len(key) < 8 or len(key) > 300:
                raise DraftError("That API key does not look usable.")
            pending.append((kind, key))
        book[kind] = row
    if "dashboard_url" in spec:
        book["dashboard_url"] = _dashboard(spec.get("dashboard_url"))
    for kind, key in pending:
        if not writer(KEYS[kind], key):
            raise DraftError("The API key did not reach the vault. Nothing was saved.")
        book[kind] = {**book.get(kind, {}), "key_vault": f"vault:{KEYS[kind]}"}
    if book.get("provider") and not _ready(book):
        raise DraftError(_missing(book))
    updated["mail"] = book
    save(updated, path)
    return mail_view(updated)


def send_test_mail(state: dict, to: str, *, reader=None, http=None) -> dict:
    book = _book(state)
    if not _ready(book):
        raise DraftError(_missing(book) if book.get("provider") else "Pick AgentMail or Resend first.")
    target = _address(to, "Send the test to an email address.")
    text = (
        "This is a test from House Social.\n\n"
        "Approval emails will look like this one, with the three versions of a post. "
        "The approver replies APPROVE, or CHANGES and what to change.\n"
    )
    sent = _send(book, target, "House Social test email", text, _html(text), reader=reader, http=http)
    return {"to": target, "provider": book["provider"], "message_id": sent.get("message_id") or ""}


# ---- Sending ---------------------------------------------------------------


def send_review_mail(state: dict, piece_id: str, path: Path | None = None, *, reader=None, http=None, now: datetime | None = None) -> dict | None:
    """Email the approver for the piece's current step. Failure leaves a notice, not an error."""
    from approval import _notify, _steps

    book = _book(state)
    piece = next((item for item in state.get("pieces") or [] if item.get("id") == piece_id), None)
    if not piece or piece.get("status") != "pending" or not _ready(book):
        return None
    brand = resolve_brand(state, piece["brand_id"])
    steps = _steps(state, brand.id)
    approval = piece.get("approval") or {}
    step = min(int(approval.get("step") or 0), len(steps) - 1)
    name = steps[step]
    to = approver_email(state, brand.id, name)
    if not to:
        return None
    moment = now or datetime.now(timezone.utc)
    if _quiet(state, brand.id, moment):
        record = {"to": to, "step": step, "pending": True, "code": _code(approval)}
        current = load(path) if path else load()
        save(_with_mail(current, piece_id, record), path)
        return record
    code = _code(approval)
    brand_name = next((row["name"] for row in roster(state) if row["id"] == brand.id), brand.id)
    subject = f"[HS-{code}] Approve for {brand_name}: {_short(piece.get('idea'), 60)}"
    text = _body(state, piece, brand_name, name, code, book)
    record = {"to": to, "step": step, "code": code, "pending": False, "provider": book["provider"]}
    try:
        sent = _send(book, to, subject, text, _html(text), reader=reader, http=http)
        record.update({"sent_at": moment.isoformat(timespec="seconds"), "message_id": sent.get("message_id") or "", "error": ""})
        notice = f"Approval email for {_short(piece.get('idea'), 60)} went to {to}."
    except MailError as exc:
        record.update({"sent_at": "", "error": str(exc)[:300]})
        notice = f"Approval email to {to} did not send. {exc}"
    current = load(path) if path else load()
    current = _with_mail(current, piece_id, record)
    current = _notify(current, piece, notice[:300])
    save(current, path)
    return record


def send_waiting(state: dict, path: Path | None = None, *, reader=None, http=None, now: datetime | None = None) -> int:
    """Send mail that waited for quiet hours to end."""
    moment = now or datetime.now(timezone.utc)
    count = 0
    for piece in state.get("pieces") or []:
        mail = (piece.get("approval") or {}).get("mail") or {}
        if piece.get("status") != "pending" or not mail.get("pending") or _quiet(state, piece["brand_id"], moment):
            continue
        sent = send_review_mail(load(path) if path else load(), piece["id"], path, reader=reader, http=http, now=moment)
        count += 1 if sent and not sent.get("pending") else 0
    return count


def approver_email(state: dict, brand_id: str, name: str) -> str:
    emails = (state.get("approval_emails") or {}).get(brand_id) or {}
    return str(emails.get(str(name or "").strip().lower()) or "")


# ---- Reading replies -------------------------------------------------------


def poll_replies(state: dict, path: Path | None = None, *, reader=None, http=None, now: datetime | None = None) -> dict:
    """Read new mail in the AgentMail inbox and count the approvers' answers."""
    from approval import _notify, _steps, decide

    book = _book(state)
    agentmail = book.get("agentmail") or {}
    moment = now or datetime.now(timezone.utc)
    result = {"read": 0, "decided": [], "ignored": []}
    if not (agentmail.get("inbox") and agentmail.get("key_vault")):
        return result
    waiting_posts = any(((item.get("approval") or {}).get("mail") or {}).get("code") for item in state.get("pieces") or [] if item.get("status") == "pending")
    waiting_replies = any(item.get("reply_state") == "pending" and item.get("reply_code") for item in state.get("inbox") or [])
    if not (waiting_posts or waiting_replies):
        return result
    key = (reader or _read_vault)(KEYS["agentmail"])
    if not key:
        return result
    call = http or _call
    inbox = agentmail["inbox"]
    _require_inbox(call, key, inbox)
    since = book.get("last_poll") or (moment - timedelta(days=2)).isoformat(timespec="seconds")
    seen = set(book.get("seen") or [])
    try:
        listed = call("GET", f"{AGENTMAIL}/inboxes/{quote(inbox)}/messages", key, {
            "after": _minus(since, 10), "limit": "50", "ascending": "true",
        })
    except MailError as exc:
        return _remember_poll(path, moment, seen, str(exc), result)
    for row in listed.get("messages") or []:
        message_id = str(row.get("message_id") or "")
        if not message_id or message_id in seen:
            continue
        seen.add(message_id)
        sender = _bare(row.get("from"))
        if "sent" in [str(label).lower() for label in row.get("labels") or []] or _same(sender, inbox):
            continue
        found = _CODE.search(str(row.get("subject") or ""))
        if not found:
            continue
        current = load(path) if path else load()
        piece = next(
            (item for item in current.get("pieces") or []
             if ((item.get("approval") or {}).get("mail") or {}).get("code") == found.group(1)),
            None,
        )
        if not piece:
            pending = next(
                (item for item in current.get("inbox") or []
                 if item.get("reply_code") == found.group(1) and item.get("reply_state") == "pending"),
                None,
            )
            if not pending:
                continue
            result["read"] += 1
            try:
                body = call("GET", f"{AGENTMAIL}/inboxes/{quote(inbox)}/messages/{quote(message_id)}", key, None)
            except MailError as exc:
                seen.discard(message_id)
                result["ignored"].append({"id": message_id, "why": str(exc)})
                continue
            from inbox_send import take_reply_mail

            text = str(body.get("extracted_text") or body.get("text") or body.get("preview") or "")
            taken = take_reply_mail(current, found.group(1), sender, text, path)
            if taken and taken.get("decision"):
                result["decided"].append(taken)
            else:
                result["ignored"].append({"id": message_id, "why": "That reply email was not counted."})
            continue
        result["read"] += 1
        if piece.get("status") != "pending":
            result["ignored"].append({"id": message_id, "why": "That piece is no longer waiting for review."})
            continue
        steps = _steps(current, piece["brand_id"])
        step = min(int((piece.get("approval") or {}).get("step") or 0), len(steps) - 1)
        name = steps[step]
        expected = approver_email(current, piece["brand_id"], name)
        if not expected or not _same(sender, expected):
            why = f"A reply about {_short(piece.get('idea'), 50)} came from {sender or 'an unknown sender'}, not {name}'s address, so it was not counted."
            save(_notify(current, piece, why), path)
            result["ignored"].append({"id": message_id, "why": why})
            continue
        try:
            body = call("GET", f"{AGENTMAIL}/inboxes/{quote(inbox)}/messages/{quote(message_id)}", key, None)
        except MailError as exc:
            seen.discard(message_id)
            result["ignored"].append({"id": message_id, "why": str(exc)})
            continue
        verdict, note = read_reply(str(body.get("extracted_text") or body.get("text") or body.get("preview") or ""))
        if not verdict:
            why = f"{name}'s reply about {_short(piece.get('idea'), 50)} did not start with APPROVE or CHANGES, so it was not counted."
            save(_notify(current, piece, why), path)
            result["ignored"].append({"id": message_id, "why": why})
            continue
        try:
            decided = decide(current, piece["id"], {"author": name, "decision": verdict, "comment": note}, path)
        except DraftError as exc:
            result["ignored"].append({"id": message_id, "why": str(exc)})
            continue
        fresh = load(path) if path else load()
        said = "approved" if verdict == "approved" else "asked for changes on"
        save(_notify(fresh, piece, f"{name} {said} {_short(piece.get('idea'), 60)} by email."), path)
        result["decided"].append({"piece_id": piece["id"], "decision": verdict, "status": decided.get("status")})
    return _remember_poll(path, moment, seen, "", result)


def read_reply(text: str) -> tuple[str, str]:
    """The first line decides. Quoted history below it is ignored."""
    lines = []
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if _QUOTED.match(line):
            break
        if line:
            lines.append(line)
    if not lines:
        return "", ""
    head = lines[0].lstrip("*_ ")
    for verdict, pattern in (("approved", _APPROVE), ("changes", _CHANGES)):
        if pattern.match(head):
            return verdict, _note(" ".join([pattern.sub("", head, count=1), *lines[1:]]))
    return "", ""


def _note(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" .!:-—*_").strip()[:500]


# ---- Pieces ----------------------------------------------------------------


def _with_mail(state: dict, piece_id: str, record: dict) -> dict:
    updated = _copy(state)
    for item in updated.get("pieces") or []:
        if item.get("id") == piece_id:
            approval = dict(item.get("approval") or {})
            approval["mail"] = record
            item["approval"] = approval
    return updated


def _code(approval: dict) -> str:
    mail = approval.get("mail") or {}
    if mail.get("code"):
        return str(mail["code"])
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(6))


def _body(state: dict, piece: dict, brand_name: str, step_name: str, code: str, book: dict) -> str:
    # All three versions unless the brand asked for the short mail.
    short = (((state.get("mail_prefs") or {}).get(piece["brand_id"]) or {}).get("body")) == "short"
    variants = piece.get("variants") or {}
    when = _local(piece.get("scheduled_for"))
    lines = [
        f"{brand_name} has a post waiting for {step_name}.",
        "",
        f"When: {when}" if when else "When: no time yet. Approving it does not schedule it.",
        "",
    ]
    for platform in PLATFORMS:
        variant = variants.get(platform) or {}
        words = str(variant.get("body") or "").strip()
        if not words:
            continue
        if short and platform != "facebook":
            continue
        tags = " ".join("#" + str(tag).lstrip("#") for tag in variant.get("hashtags") or [] if str(tag).strip())
        lines += [f"{NAMES[platform]}:", words + (f"\n\n{tags}" if tags and platform == "instagram" else ""), ""]
    if short:
        lines += ["Instagram and Threads are on the desk.", ""]
    if piece.get("asset_ids"):
        lines += ["It carries an image from the library. See it on the desk.", ""]
    lines += [
        "Reply with APPROVE on the first line to approve it.",
        "Reply with CHANGES on the first line, then what to change, to send it back.",
        f"Keep HS-{code} in the subject.",
    ]
    link = _link(book, piece)
    if link:
        lines += ["", f"Open it on the desk: {link}"]
    lines += ["", "House Social"]
    return "\n".join(lines)


def _html(text: str) -> str:
    escaped = html.escape(text)
    linked = re.sub(r"(https?://[^\s<]+)", r'<a href="\1">\1</a>', escaped)
    return (
        '<div style="font-family: -apple-system, Segoe UI, Roboto, sans-serif; font-size: 15px; line-height: 1.5; white-space: pre-wrap;">'
        + linked
        + "</div>"
    )


def _link(book: dict, piece: dict) -> str:
    base = book.get("dashboard_url") or ""
    if not base:
        return ""
    return base + "?" + urlencode({"hs_brand": piece["brand_id"], "hs_review": piece["id"]})


def _local(value) -> str:
    try:
        moment = datetime.fromisoformat(str(value or ""))
    except ValueError:
        return ""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    local = moment.astimezone(ZoneInfo("America/New_York"))
    hour = local.hour % 12 or 12
    return f"{local:%a %b} {local.day}, {hour}:{local:%M} {'AM' if local.hour < 12 else 'PM'} Eastern"


def _quiet(state: dict, brand_id: str, moment: datetime) -> bool:
    from support import _mail

    prefs = _mail(state, brand_id)
    start, end = int(prefs.get("quiet_start") or 0), int(prefs.get("quiet_end") or 0)
    if start == end:
        return False
    hour = moment.astimezone(ZoneInfo("America/New_York")).hour
    return start <= hour < end if start < end else hour >= start or hour < end


# ---- Providers -------------------------------------------------------------


def _send(book: dict, to: str, subject: str, text: str, body_html: str, *, reader=None, http=None) -> dict:
    provider = book.get("provider")
    key = (reader or _read_vault)(KEYS.get(provider, ""))
    if not key:
        raise MailError(f"No {provider} API key in the vault. Save it again under House settings.")
    call = http or _call
    if provider == "agentmail":
        inbox = (book.get("agentmail") or {}).get("inbox")
        _require_inbox(call, key, inbox)
        body = call("POST", f"{AGENTMAIL}/inboxes/{quote(inbox)}/messages/send", key, {
            "to": [to], "subject": subject, "text": text, "html": body_html, "labels": ["house-social"],
        })
        return {"message_id": str(body.get("message_id") or ""), "thread_id": str(body.get("thread_id") or "")}
    resend = book.get("resend") or {}
    payload = {"from": resend["from"], "to": [to], "subject": subject, "text": text, "html": body_html}
    if resend.get("reply_to"):
        payload["reply_to"] = resend["reply_to"]
    body = call("POST", RESEND, key, payload)
    return {"message_id": str(body.get("id") or "")}


def _call(method: str, url: str, key: str, payload: dict | None) -> dict:
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    data = None
    target = url
    if method == "GET" and payload:
        target = f"{url}?{urlencode(payload)}"
    elif payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(target, data=data, method=method, headers=headers)
    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise MailError(f"The mail service said ({exc.code}): {_said(detail, key)}") from None
    except (URLError, TimeoutError) as exc:
        raise MailError(f"The mail service could not be reached. {str(exc)[:160]}") from None
    try:
        body = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        raise MailError("The mail service answered with something that is not JSON.") from None
    return body if isinstance(body, dict) else {}


def _require_inbox(call, key: str, inbox: str) -> None:
    names = _known_inboxes(call, key)
    if names and inbox not in names:
        raise MailError(f"No inbox named {inbox}. This key can see {', '.join(names)}.")


def _known_inboxes(call, key: str) -> list[str]:
    try:
        body = call("GET", f"{AGENTMAIL}/inboxes", key, {"limit": "20"})
    except MailError:
        return []
    names = []
    for row in body.get("inboxes") or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("inboxId") or row.get("inbox_id") or row.get("email") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _said(detail: str, key: str) -> str:
    text = detail
    try:
        body = json.loads(detail)
        text = body.get("message") or body.get("error") or body.get("name") or detail
    except (json.JSONDecodeError, AttributeError):
        found = re.search(r'"message"\s*:\s*"([^"]*)"', detail)
        if found:
            text = found.group(1)
    return str(text).replace(key, "REDACTED")[:240]


# ---- Small helpers ---------------------------------------------------------


def _remember_poll(path: Path | None, moment: datetime, seen: set, error: str, result: dict) -> dict:
    current = load(path) if path else load()
    book = _book(current)
    if not error:
        book["last_poll"] = moment.isoformat(timespec="seconds")
    book["poll_error"] = error[:300]
    book["seen"] = sorted(seen)[-300:]
    current["mail"] = book
    save(current, path)
    if error:
        result["error"] = error
    return result


def _book(state: dict) -> dict:
    raw = state.get("mail")
    return dict(raw) if isinstance(raw, dict) else {}


def _ready(book: dict) -> bool:
    provider = book.get("provider")
    if provider == "agentmail":
        row = book.get("agentmail") or {}
        return bool(row.get("inbox") and row.get("key_vault"))
    if provider == "resend":
        row = book.get("resend") or {}
        return bool(row.get("from") and row.get("key_vault"))
    return False


def _missing(book: dict) -> str:
    if book.get("provider") == "agentmail":
        return "AgentMail needs the inbox address and the API key."
    return "Resend needs the from address and the API key."


def _address(value, message: str, allow_empty: bool = False) -> str:
    text = str(value or "").strip()
    if not text and allow_empty:
        return ""
    if len(text) > 200 or not _ADDRESS.fullmatch(text):
        raise DraftError(message)
    return text.lower()


def _sender(value) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) > 200 or not _ADDRESS.search(text) or "\n" in text:
        raise DraftError("The from address is an email, or a name and <email>.")
    return text


def _dashboard(value) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or len(text) > 300:
        raise DraftError("The dashboard address starts with http:// or https://.")
    return text.split("#", 1)[0].split("?", 1)[0]


def _bare(value) -> str:
    found = _ADDRESS.search(str(value or ""))
    return found.group(0).lower() if found else ""


def _same(left, right) -> bool:
    return bool(left) and bool(right) and _bare(left) == _bare(right)


def _short(value, size: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "A piece")).strip()
    return text if len(text) <= size else text[: size - 1].rstrip() + "…"


def _minus(stamp: str, minutes: int) -> str:
    try:
        moment = datetime.fromisoformat(stamp)
    except ValueError:
        return stamp
    return (moment - timedelta(minutes=minutes)).isoformat(timespec="seconds")
