"""The publishing queue. It does not send anything.

Drafts stay on the making side. Pending, scheduled, and failed are
what is going out. A suggested hour is used only when the performance
gap is already clear.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from adapt import DraftError, issues
from brands import Brand
from learn import suggest_hour
from store import _find, _local_date_time, load, resolve_brand, update_piece


_OUT = {"pending", "scheduled", "failed"}
_ACTIONS = {"pending", "schedule", "draft", "retry"}
_LABELS = {
    "draft": "Draft",
    "planned": "Draft",
    "ready": "Ready",
    "pending": "Pending approval",
    "scheduled": "Scheduled",
    "failed": "Failed",
}


def queue_for(state: dict, brand_id: str, posts: list[dict] | None = None) -> dict:
    brand = resolve_brand(state, brand_id)
    items = [_item(brand, piece) for piece in state.get("pieces") or [] if piece.get("brand_id") == brand.id]
    items.sort(key=lambda item: (item.get("date") or "9999", item.get("time") or "", item.get("idea") or ""))
    return {"items": items, "suggestion": suggest_hour(posts or []), "rules": rules_for(brand)}


def bulk_queue(
    state: dict,
    brand_id: str,
    ids: list,
    action: str,
    scheduled_for: str = "",
    path: Path | None = None,
    posts: list[dict] | None = None,
) -> dict:
    resolve_brand(state, brand_id)
    name = (action or "").strip().lower()
    if name not in _ACTIONS:
        raise DraftError("Queue actions are pending, schedule, draft, and retry.")
    chosen = [str(item).strip() for item in ids or [] if str(item).strip()]
    if not chosen:
        raise DraftError("Choose at least one piece.")
    suggestion = suggest_hour(posts or [])
    when = str(scheduled_for or "").strip()
    if name in {"schedule", "retry"} and not when and suggestion.get("clear"):
        when = next_local_hour(int(suggestion["hour"]))
    current = state
    results = []
    for piece_id in chosen:
        current, result = _one(current, brand_id, piece_id, name, when, path)
        results.append(result)
        current = load(path) if path else load()
    view = queue_for(current, brand_id, posts)
    view["results"] = results
    return view


def rules_for(brand: Brand) -> list[str]:
    rules = [
        "Nothing in this queue is sent.",
        "Facebook holds 5000 characters, Instagram 2200, and Threads 500.",
        "Facebook, Instagram, and Threads cannot share the same words.",
        "Instagram hashtags stay out of the caption.",
    ]
    if brand.id == "josie-blackthorn":
        rules.append("Josie Facebook needs the quote image before it can be scheduled.")
    if brand.id == "jamhaul":
        rules.append("JamHaul needs jamhaul.com and a question before it can be scheduled.")
    else:
        rules.append("JamHaul does not ride on this brand.")
    return rules


def next_local_hour(hour: int, now: datetime | None = None) -> str:
    zone = ZoneInfo("America/New_York")
    moment = now.astimezone(zone) if now is not None else datetime.now(zone)
    if not 0 <= hour <= 23:
        raise DraftError("A suggested hour is 0 through 23.")
    candidate = moment.replace(hour=hour, minute=0, second=0, microsecond=0)
    if candidate <= moment:
        candidate = candidate + timedelta(days=1)
    return candidate.isoformat()


def _one(state: dict, brand_id: str, piece_id: str, action: str, when: str, path: Path | None) -> tuple[dict, dict]:
    try:
        _index, piece = _find(state, piece_id)
    except DraftError as exc:
        return state, {"id": piece_id, "ok": False, "status": "", "error": str(exc)}
    if piece.get("brand_id") != brand_id:
        return state, {"id": piece_id, "ok": False, "status": piece.get("status") or "", "error": "That piece belongs to another brand."}
    try:
        if action == "draft":
            saved = update_piece(state, piece_id, status="draft", clear_schedule=True, path=path)
        elif action == "pending":
            saved = update_piece(state, piece_id, status="pending", path=path)
        elif action == "retry" and piece.get("status") != "failed":
            raise DraftError("Retry is for a failed piece.")
        else:
            if not when and not piece.get("scheduled_for"):
                raise DraftError("A scheduled piece needs a time, and no hour is clearly ahead.")
            saved = update_piece(state, piece_id, status="scheduled", scheduled_for=when or None, path=path)
    except DraftError as exc:
        if action == "retry" and piece.get("status") != "failed":
            return state, {"id": piece_id, "ok": False, "status": piece.get("status") or "", "error": str(exc)}
        failed = update_piece(state, piece_id, status="failed", failure=str(exc), path=path)
        return state, {"id": piece_id, "ok": False, "status": failed.get("status"), "error": str(exc)}
    return state, {"id": piece_id, "ok": True, "status": saved.get("status"), "error": ""}


def _item(brand: Brand, piece: dict) -> dict:
    status = piece.get("status") or "draft"
    day, clock = _local_date_time(str(piece.get("scheduled_for") or ""))
    return {
        "id": piece.get("id"),
        "status": status,
        "label": _LABELS.get(status, "Draft"),
        "lane": "out" if status in _OUT else "making",
        "idea": str(piece.get("idea") or "")[:120],
        "format": piece.get("format") or "",
        "campaign": piece.get("campaign") or "",
        "date": day,
        "time": clock,
        "failure": piece.get("failure") or "",
        "problems": issues(brand, piece.get("variants") or {}),
        "posted": False,
    }
