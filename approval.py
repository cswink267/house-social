"""Approval for one brand. Notices stay on this desk.

Draft, then needs review, then approved, then scheduled.
One step is the default. More names make it a sequence.
The desk does not send mail or a post.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from adapt import DraftError
from brands import PLATFORMS
from meta import redact
from store import _find, _label, load, resolve_brand, save, update_piece


def approval_for(state: dict, brand_id: str) -> dict:
    brand = resolve_brand(state, brand_id)
    steps = _steps(state, brand.id)
    pieces = []
    for piece in state.get("pieces") or []:
        if piece.get("brand_id") != brand.id:
            continue
        if (piece.get("status") or "draft") not in {"draft", "planned", "ready", "pending", "approved", "scheduled", "failed"}:
            continue
        pieces.append(_piece(piece, steps))
    notices = [
        _notice(item) for item in state.get("notices") or []
        if item.get("brand_id") == brand.id and not item.get("read")
    ]
    return {"steps": steps, "pieces": pieces, "notices": notices}


def save_steps(state: dict, brand_id: str, steps: list, path: Path | None = None) -> dict:
    brand = resolve_brand(state, brand_id)
    names = _names(steps)
    updated = {**state, "approval_steps": {**(state.get("approval_steps") or {}), brand.id: names}}
    save(updated, path)
    return approval_for(updated, brand.id)


def submit_review(state: dict, piece_id: str, path: Path | None = None) -> dict:
    _find(state, piece_id)
    update_piece(state, piece_id, status="pending", path=path)
    current = load(path) if path else load()
    current = _with_piece(current, piece_id, _submit)
    current = _notify(current, _piece_row(current, piece_id), f"{_title(_piece_row(current, piece_id))} needs review.")
    save(current, path)
    return _piece_row(current, piece_id)


def add_comment(state: dict, piece_id: str, spec: dict, path: Path | None = None) -> dict:
    if not isinstance(spec, dict):
        raise DraftError("A comment needs words.")
    text = _label(spec.get("text") or "", 500)
    if not text:
        raise DraftError("A comment needs words.")
    author = _person(spec.get("author") or "")
    _index, piece = _find(state, piece_id)
    comment = {"id": str(uuid.uuid4()), "at": _now(), "author": author, "text": text}
    approval = _approval(piece)
    approval["comments"] = [*(approval.get("comments") or []), {**comment, "text": redact(text)}][-40:]
    _remember(approval, author, "comment", redact(text))
    updated = _with_piece(state, piece_id, lambda item: {**item, "approval": approval})
    updated = _notify(updated, piece, f"{author} commented on {_title(piece)}.")
    save(updated, path)
    return _piece(next(item for item in updated["pieces"] if item.get("id") == piece_id), _steps(updated, piece["brand_id"]))


def decide(state: dict, piece_id: str, spec: dict, path: Path | None = None) -> dict:
    if not isinstance(spec, dict):
        raise DraftError("The decision needs a name.")
    author = _person(spec.get("author") or "")
    choice = str(spec.get("decision") or "").strip().lower()
    if choice not in {"approved", "changes"}:
        raise DraftError("Decide approved or changes.")
    note = _label(spec.get("comment") or "", 500)
    _index, piece = _find(state, piece_id)
    if piece.get("status") != "pending":
        raise DraftError("Only a piece in review can be decided.")
    steps = _steps(state, piece["brand_id"])
    approval = _approval(piece)
    step = int(approval.get("step") or 0)
    if step >= len(steps):
        step = len(steps) - 1
    if author.lower() != steps[step].lower():
        raise DraftError(f"This step is {steps[step]}.")
    approval["decisions"] = [
        *(approval.get("decisions") or []),
        {"id": str(uuid.uuid4()), "at": _now(), "step": step, "name": steps[step], "decision": choice, "comment": note},
    ][-20:]
    if note:
        approval["comments"] = [*(approval.get("comments") or []), {"id": str(uuid.uuid4()), "at": _now(), "author": author, "text": redact(note)}][-40:]
    _remember(approval, author, choice, redact(note) or ("Approved." if choice == "approved" else "Asked for changes."))
    if choice == "changes":
        approval["complete"] = False
        approval["step"] = 0
        updated = _with_piece(state, piece_id, lambda item: {**item, "approval": approval})
        save(updated, path)
        current = load(path) if path else load()
        update_piece(current, piece_id, status="draft", clear_schedule=True, path=path)
        current = load(path) if path else load()
        current = _notify(current, piece, f"{author} asked for changes on {_title(piece)}.")
        save(current, path)
        return {"status": "draft", "piece_id": piece_id}
    if step + 1 < len(steps):
        approval["complete"] = False
        approval["step"] = step + 1
        updated = _with_piece(state, piece_id, lambda item: {**item, "approval": approval, "status": "pending"})
        updated = _notify(updated, piece, f"{_title(piece)} needs review from {steps[step + 1]}.")
        save(updated, path)
        return {"status": "pending", "piece_id": piece_id, "waiting": steps[step + 1]}
    approval["complete"] = True
    approval["step"] = step
    updated = _with_piece(state, piece_id, lambda item: {**item, "approval": approval})
    save(updated, path)
    current = load(path) if path else load()
    update_piece(current, piece_id, status="approved", path=path)
    current = load(path) if path else load()
    current = _notify(current, piece, f"{_title(piece)} is approved.")
    save(current, path)
    return {"status": "approved", "piece_id": piece_id}


def mark_notice(state: dict, notice_id: str, path: Path | None = None) -> dict:
    found = False
    notices = []
    brand_id = ""
    for notice in state.get("notices") or []:
        if notice.get("id") == notice_id:
            notices.append({**notice, "read": True})
            found = True
            brand_id = notice.get("brand_id") or ""
        else:
            notices.append(notice)
    if not found:
        raise DraftError("That notice is not on the desk.")
    updated = {**state, "notices": notices}
    save(updated, path)
    return approval_for(updated, brand_id)


def compare_piece(piece: dict, earlier: int | None = None, later: int | None = None) -> dict:
    versions = _approval(piece).get("versions") or []
    pair = _pair(versions, earlier, later)
    if pair is None:
        return {"ready": False, "detail": "Nothing earlier to compare.", "platforms": []}
    before, after = versions[pair[0]], versions[pair[1]]
    platforms = []
    for platform in PLATFORMS:
        left = str((before.get("bodies") or {}).get(platform) or "")
        right = str((after.get("bodies") or {}).get(platform) or "")
        removed, added = _changed_lines(left, right)
        platforms.append({
            "platform": platform,
            "before": left,
            "after": right,
            "same": left == right,
            "removed": removed,
            "added": added,
        })
    return {
        "ready": True,
        "earlier": pair[0],
        "later": pair[1],
        "detail": "Lines only in the earlier version are removed. Lines only in the later version are added.",
        "platforms": platforms,
    }


def _submit(piece: dict) -> dict:
    approval = _approval(piece)
    versions = list(approval.get("versions") or [])
    versions.append({"id": str(uuid.uuid4()), "at": _now(), "bodies": _bodies(piece)})
    approval["versions"] = versions[-8:]
    approval["complete"] = False
    approval["step"] = 0
    approval["decisions"] = []
    _remember(approval, "Desk", "submitted", "Sent for review.")
    return {**piece, "approval": approval, "status": "pending"}


def _piece(piece: dict, steps: list[str]) -> dict:
    approval = _approval(piece)
    step = int(approval.get("step") or 0)
    waiting = steps[step] if piece.get("status") == "pending" and step < len(steps) else ""
    return {
        "id": piece.get("id"),
        "idea": str(piece.get("idea") or "")[:120],
        "status": piece.get("status") or "draft",
        "waiting": waiting,
        "complete": bool(approval.get("complete")),
        "comments": list(approval.get("comments") or []),
        "signed": [item.get("name") or "" for item in approval.get("decisions") or [] if item.get("decision") == "approved"],
        "trail": list(approval.get("trail") or []),
        "versions": [
            {"index": index, "at": item.get("at") or ""}
            for index, item in enumerate(approval.get("versions") or [])
        ],
        "compare": compare_piece(piece),
    }


def _approval(piece: dict) -> dict:
    raw = piece.get("approval") if isinstance(piece.get("approval"), dict) else {}
    return {
        "complete": bool(raw.get("complete")),
        "step": int(raw.get("step") or 0),
        "decisions": list(raw.get("decisions") or []),
        "versions": list(raw.get("versions") or []),
        "comments": list(raw.get("comments") or []),
        "trail": list(raw.get("trail") or []),
    }


def _remember(approval: dict, author: str, action: str, text: str) -> None:
    approval["trail"] = [
        *(approval.get("trail") or []),
        {
            "id": str(uuid.uuid4()),
            "at": _now(),
            "author": author,
            "action": action,
            "text": redact(text)[:240],
        },
    ][-40:]


def _pair(versions: list, earlier: int | None, later: int | None) -> tuple[int, int] | None:
    if earlier is None and later is None:
        if len(versions) < 2:
            return None
        return len(versions) - 2, len(versions) - 1
    if earlier is None or later is None or isinstance(earlier, bool) or isinstance(later, bool):
        raise DraftError("Pick two versions.")
    if not isinstance(earlier, int) or not isinstance(later, int) or earlier == later:
        raise DraftError("Pick two different versions.")
    if min(earlier, later) < 0 or max(earlier, later) >= len(versions):
        raise DraftError("That version is not on this piece.")
    return min(earlier, later), max(earlier, later)


def _changed_lines(before: str, after: str) -> tuple[list[str], list[str]]:
    left = before.splitlines()
    right = after.splitlines()
    removed = [line for line in left if line and line not in right][:8]
    added = [line for line in right if line and line not in left][:8]
    return removed, added


def _bodies(piece: dict) -> dict:
    variants = piece.get("variants") or {}
    return {platform: str((variants.get(platform) or {}).get("body") or "") for platform in PLATFORMS}


def _steps(state: dict, brand_id: str) -> list[str]:
    saved = (state.get("approval_steps") or {}).get(brand_id)
    if isinstance(saved, list) and saved:
        return [str(item) for item in saved]
    return ["Approver"]


def _names(steps: list) -> list[str]:
    if isinstance(steps, str):
        steps = [part.strip() for part in steps.split(",")]
    names = []
    for value in steps or []:
        text = _person(value)
        if text.lower() not in {item.lower() for item in names}:
            names.append(text)
    if not names or len(names) > 4:
        raise DraftError("Use one to four approver names.")
    return names


def _person(value) -> str:
    text = _label(value, 40)
    if not text:
        raise DraftError("The decision needs a name.")
    return text


def _with_piece(state: dict, piece_id: str, change) -> dict:
    pieces = []
    found = False
    for piece in state.get("pieces") or []:
        if piece.get("id") == piece_id:
            pieces.append(change(piece))
            found = True
        else:
            pieces.append(piece)
    if not found:
        raise DraftError("That piece is not in the queue.")
    return {**state, "pieces": pieces}


def _piece_row(state: dict, piece_id: str) -> dict:
    return next(item for item in state.get("pieces") or [] if item.get("id") == piece_id)


def _notify(state: dict, piece: dict, text: str) -> dict:
    notice = {
        "id": str(uuid.uuid4()),
        "brand_id": piece.get("brand_id"),
        "piece_id": piece.get("id"),
        "text": text,
        "at": _now(),
        "read": False,
    }
    return {**state, "notices": [notice, *(state.get("notices") or [])][:50]}


def _notice(notice: dict) -> dict:
    return {
        "id": notice.get("id"),
        "piece_id": notice.get("piece_id") or "",
        "text": notice.get("text") or "",
        "at": notice.get("at") or "",
    }


def _title(piece: dict) -> str:
    text = str(piece.get("idea") or "A piece").strip()
    return text[:80]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
