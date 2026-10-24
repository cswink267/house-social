"""How far a brand lets the desk act.

Callers: studio, the mode routes, and the Brief desk. Manual is the
default. Approval can draft and must not schedule. Auto can schedule
only after an explicit confirm. A piece the desk drafts here is a
placeholder until someone writes it, and a placeholder never posts.
"""

from __future__ import annotations

import copy
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from adapt import DraftError
from learn import suggest_hour


_MODES = {"manual": "Manual", "approval": "Autonomous with approval", "auto": "Fully autonomous"}


def mode_view(state: dict, brand_id: str, posts: list[dict] | None = None) -> dict:
    from store import brand_history, resolve_brand

    brand = resolve_brand(state, brand_id)
    history = list(posts) if posts is not None else brand_history(state, brand.id)[0]
    mode = _mode(state, brand.id)
    rate = _rate(state, brand.id)
    batch = _latest(state, brand.id)
    return {
        "mode": mode,
        "label": _MODES[mode],
        "rate": rate,
        "notice": (batch or {}).get("notice") or "",
        "batch": _public_batch(state, batch),
        "log": [_public_log(item) for item in (state.get("mode_log") or []) if item.get("brand_id") == brand.id][:40],
        "limits": _limits(state, brand.id),
        "can_prepare": mode == "approval" and not _open(batch),
        "can_run": mode == "auto",
        "hour_clear": bool(suggest_hour(history).get("clear")),
    }


def set_mode(state: dict, brand_id: str, mode: str, confirm: bool = False, path: Path | None = None) -> dict:
    from store import resolve_brand, save

    brand = resolve_brand(state, brand_id)
    name = str(mode or "").strip().lower()
    if name not in _MODES:
        raise DraftError("Modes are manual, approval, and auto.")
    rate = _rate(state, brand.id)
    if name == "auto" and not confirm:
        raise DraftError(rate + " Confirm the switch.")
    updated = copy.deepcopy(state)
    modes = dict(updated.get("modes") or {})
    modes[brand.id] = name
    updated["modes"] = modes
    updated = _log(updated, brand.id, name, "mode", "", name, rate if name == "auto" else "user")
    from support import stale_previews

    updated = stale_previews(updated, brand.id)
    save(updated, path)
    return mode_view(updated, brand.id)


def set_limits(state: dict, brand_id: str, spec: dict, path: Path | None = None) -> dict:
    from store import resolve_brand, save

    brand = resolve_brand(state, brand_id)
    if not isinstance(spec, dict):
        raise DraftError("Limits are whole numbers.")
    limits = {"per_day": _cap(spec.get("per_day")), "per_week": _cap(spec.get("per_week")), "hold_hours": _cap(spec.get("hold_hours"), 48)}
    updated = copy.deepcopy(state)
    book = dict(updated.get("mode_limits") or {})
    book[brand.id] = limits
    updated["mode_limits"] = book
    save(updated, path)
    return mode_view(updated, brand.id)


def prepare_batch(state: dict, brand_id: str, path: Path | None = None) -> dict:
    from store import brand_history, create_piece, resolve_brand, save

    brand = resolve_brand(state, brand_id)
    from support import assert_running

    assert_running(state, brand.id)
    if _mode(state, brand.id) != "approval":
        raise DraftError("Manual does not start a batch.")
    if _open(_latest(state, brand.id)):
        raise DraftError("A batch is still open.")
    history = brand_history(state, brand.id)[0]
    hour = suggest_hour(history)
    if not hour.get("clear"):
        raise DraftError("Nothing learned is clear enough to draft.")
    idea = ("Proposed from the hour that is ahead. " + str(hour.get("detail") or ""))[:500]
    piece = create_piece(state, brand.id, idea, path, status="planned")
    current = _placeholder(_load(path, state), piece["id"], path)
    from support import mail_notice

    notice = mail_notice(state, brand.id)
    batch = {
        "id": str(uuid.uuid4()),
        "brand_id": brand.id,
        "at": _now(),
        "notice": notice,
        "pieces": [{"piece_id": piece["id"], "idea": piece["idea"], "hour": hour.get("hour"), "decision": ""}],
    }
    updated = copy.deepcopy(current)
    updated["mode_batches"] = [batch, *(updated.get("mode_batches") or [])][:40]
    updated = _log(updated, brand.id, "approval", "prepare", piece["id"], "hour", notice)
    save(updated, path)
    return mode_view(updated, brand.id)


def decide_batch(state: dict, brand_id: str, piece_id: str, action: str, path: Path | None = None, teach: str = "", phrase: str = "") -> dict:
    from store import resolve_brand, save

    brand = resolve_brand(state, brand_id)
    verb = str(action or "").strip().lower()
    if verb not in {"approve", "reject"}:
        raise DraftError("Batch actions are approve and reject.")
    current = _load(path, state)
    batch, item = _find_item(current, brand.id, piece_id)
    if item.get("decision"):
        raise DraftError("That piece was already decided.")
    if _expired(batch):
        raise DraftError("That approval expired.")
    piece = next((row for row in current.get("pieces") or [] if row.get("id") == piece_id), None)
    if piece is None or piece.get("idea") != item.get("idea"):
        _invalidate(current, brand.id, item, path)
        raise DraftError("The piece changed. The approval is no longer valid.")
    if verb == "approve":
        _approve(current, piece, item, path)
        outcome = "scheduled"
    else:
        _reject(current, brand.id, piece, path)
        if teach and teach != "discard":
            from support import teach_rejection

            teach_rejection(_load(path, current), brand.id, teach, phrase, str(piece.get("format") or ""), path)
        outcome = "rejected"
    saved = _mark(_load(path, current), brand.id, piece_id, verb)
    saved = _log(saved, brand.id, _mode(saved, brand.id), verb, piece_id, "hour", outcome)
    save(saved, path)
    fresh = _load(path, saved)
    piece_now = next((row for row in fresh.get("pieces") or [] if row.get("id") == piece_id), None)
    if piece_now is not None and piece_now.get("posted"):
        raise DraftError("A batch must not send a post.")
    return mode_view(fresh, brand.id)


def run_auto(state: dict, brand_id: str, path: Path | None = None) -> dict:
    from store import brand_history, create_piece, resolve_brand, save

    brand = resolve_brand(state, brand_id)
    from support import assert_running, mix_hold

    assert_running(state, brand.id)
    if _mode(state, brand.id) != "auto":
        raise DraftError("Fully autonomous is not on for this brand.")
    history = brand_history(state, brand.id)[0]
    hour = suggest_hour(history)
    if not hour.get("clear"):
        raise DraftError("Nothing learned is clear enough to draft.")
    limits = _limits(state, brand.id)
    _within_limit(state, brand.id, limits)
    idea = ("Scheduled from the hour that is ahead. " + str(hour.get("detail") or ""))[:500]
    piece = create_piece(state, brand.id, idea, path, status="planned")
    current = _placeholder(_load(path, state), piece["id"], path)
    held = mix_hold(current, brand.id, str(piece.get("format") or "feed"), str(piece.get("pillar") or ""))
    if held:
        current = _log(current, brand.id, "auto", "hold", piece["id"], "mix", held)
        save(current, path)
        return mode_view(current, brand.id)
    hold = int(limits.get("hold_hours") or 0)
    if hold:
        _hold(current, piece["id"], hold, path)
        outcome = f"Held for {hold} hours. It was not sent; write the post before it can go out."
    else:
        try:
            _approve(current, piece, {"hour": hour.get("hour"), "idea": piece["idea"]}, path)
            outcome = "Scheduled the slot. It was not sent; write the post before it can go out."
        except DraftError as exc:
            current = _log(_load(path, current), brand.id, "auto", "run", piece["id"], "guards", str(exc))
            save(current, path)
            return mode_view(current, brand.id)
    saved = _log(_load(path, current), brand.id, "auto", "run", piece["id"], "hour", outcome)
    save(saved, path)
    fresh = _load(path, saved)
    made = next(row for row in fresh["pieces"] if row["id"] == piece["id"])
    if made.get("posted"):
        raise DraftError("A batch must not send a post.")
    return mode_view(fresh, brand.id)


def agent_schedule(state: dict, piece_id: str, when: str, path: Path | None = None) -> dict:
    """The agent picks a time for a piece it wrote.

    Fully autonomous approves it and schedules it within the brand's limits.
    The other modes send it for review; approval then schedules it.
    """
    from approval import submit_review
    from store import _find, save, update_piece
    from support import assert_running

    _index, piece = _find(state, piece_id)
    brand_id = str(piece.get("brand_id") or "")
    if piece.get("placeholder"):
        raise DraftError("Write the post first. A placeholder is never scheduled to post.")
    if not str(when or "").strip():
        raise DraftError("Pick a time.")
    update_piece(state, piece_id, scheduled_for=when, path=path)
    current = _load(path, state)
    mode = _mode(current, brand_id)
    if mode != "auto":
        submit_review(current, piece_id, path)
        logged = _log(_load(path, current), brand_id, mode, "submit", piece_id, "agent", "Sent for review. It is scheduled once approved.")
        save(logged, path)
        return {"piece_id": piece_id, "status": "pending", "detail": "Sent for review. It is scheduled once it is approved."}
    assert_running(current, brand_id)
    _within_limit(current, brand_id, _limits(current, brand_id))
    updated = copy.deepcopy(current)
    target = next(row for row in updated["pieces"] if row.get("id") == piece_id)
    target["approval"] = {
        **(target.get("approval") or {}),
        "complete": True,
        "step": 0,
        "by": "auto",
        "trail": [
            *((target.get("approval") or {}).get("trail") or []),
            {"id": str(uuid.uuid4()), "at": _now(), "author": "Fully autonomous", "action": "approved", "text": "Approved by the brand's mode."},
        ][-40:],
    }
    save(updated, path)
    scheduled = update_piece(_load(path, updated), piece_id, status="scheduled", path=path)
    logged = _log(_load(path, updated), brand_id, "auto", "schedule", piece_id, "agent", f"Scheduled for {scheduled['scheduled_for']}.")
    save(logged, path)
    return {"piece_id": piece_id, "status": "scheduled", "detail": f"Scheduled for {scheduled['scheduled_for']}."}


def _approve(state: dict, piece: dict, item: dict, path: Path | None) -> None:
    from queue_desk import next_local_hour
    from store import save, update_piece

    when = next_local_hour(int(item.get("hour")))
    updated = copy.deepcopy(state)
    target = next(row for row in updated["pieces"] if row.get("id") == piece["id"])
    target["scheduled_for"] = when
    target["approval"] = {
        "complete": True,
        "step": 0,
        "decisions": [],
        "versions": [],
        "comments": [],
        "trail": [{"id": str(uuid.uuid4()), "at": _now(), "author": "chris", "action": "approved", "text": "Approved for this mode."}],
    }
    target["posted"] = False
    save(updated, path)
    scheduled = update_piece(_load(path, updated), piece["id"], status="scheduled", path=path)
    if scheduled.get("posted"):
        raise DraftError("A batch must not send a post.")


def _placeholder(state: dict, piece_id: str, path: Path | None) -> dict:
    from store import save

    updated = copy.deepcopy(state)
    target = next(row for row in updated["pieces"] if row.get("id") == piece_id)
    target["placeholder"] = True
    save(updated, path)
    return updated


def _hold(state: dict, piece_id: str, hours: int, path: Path | None) -> None:
    from store import save

    updated = copy.deepcopy(state)
    target = next(row for row in updated["pieces"] if row.get("id") == piece_id)
    target["hold_until"] = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
    target["posted"] = False
    save(updated, path)


def _reject(state: dict, brand_id: str, piece: dict, path: Path | None) -> None:
    from feedback import save_feedback
    from store import delete_piece

    save_feedback(state, brand_id, {"kind": "ideas", "target": str(piece.get("idea") or "")[:180], "verdict": "off-brand", "note": "Rejected from the batch."}, path)
    delete_piece(_load(path, state), piece["id"], path)


def _invalidate(state: dict, brand_id: str, item: dict, path: Path | None) -> None:
    from store import save

    updated = _mark(copy.deepcopy(state), brand_id, item["piece_id"], "invalidated")
    updated = _log(updated, brand_id, _mode(updated, brand_id), "invalidate", item["piece_id"], "edit", "The piece changed.")
    save(updated, path)


def _mark(state: dict, brand_id: str, piece_id: str, decision: str) -> dict:
    updated = copy.deepcopy(state)
    for batch in updated.get("mode_batches") or []:
        if batch.get("brand_id") != brand_id:
            continue
        for item in batch.get("pieces") or []:
            if item.get("piece_id") == piece_id and not item.get("decision"):
                item["decision"] = decision
    return updated


def _find_item(state: dict, brand_id: str, piece_id: str) -> tuple[dict, dict]:
    for batch in state.get("mode_batches") or []:
        if batch.get("brand_id") != brand_id:
            continue
        for item in batch.get("pieces") or []:
            if item.get("piece_id") == piece_id:
                return batch, item
    raise DraftError("That piece is not in an open batch.")


def _open(batch: dict | None) -> bool:
    if not batch or _expired(batch):
        return False
    return any(not item.get("decision") for item in batch.get("pieces") or [])


def _expired(batch: dict) -> bool:
    try:
        opened = datetime.fromisoformat(str(batch.get("at") or ""))
    except ValueError:
        return True
    if opened.tzinfo is None:
        opened = opened.replace(tzinfo=timezone.utc)
    return opened + timedelta(days=7) < datetime.now(timezone.utc)


def _latest(state: dict, brand_id: str) -> dict | None:
    return next((item for item in state.get("mode_batches") or [] if item.get("brand_id") == brand_id), None)


def _rate(state: dict, brand_id: str) -> str:
    decided = []
    for batch in state.get("mode_batches") or []:
        if batch.get("brand_id") != brand_id:
            continue
        for item in batch.get("pieces") or []:
            if item.get("decision") in {"approve", "reject"}:
                decided.append(item["decision"])
    if len(decided) < 3:
        return f"The history is thin. Based on {len(decided)} resolved pieces."
    return f"{decided.count('approve')} of {len(decided)} resolved pieces were approved."


def _within_limit(state: dict, brand_id: str, limits: dict) -> None:
    from zoneinfo import ZoneInfo

    zone = ZoneInfo("America/New_York")
    today = datetime.now(zone).date()
    week = today - timedelta(days=today.weekday())
    day_count = 0
    week_count = 0
    for piece in state.get("pieces") or []:
        if piece.get("brand_id") != brand_id or piece.get("status") != "scheduled" or not piece.get("scheduled_for"):
            continue
        try:
            when = datetime.fromisoformat(str(piece["scheduled_for"]))
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        local = when.astimezone(zone).date()
        if local == today:
            day_count += 1
        if local >= week:
            week_count += 1
    if limits.get("per_day") and day_count >= limits["per_day"]:
        raise DraftError(f"The daily limit is {limits['per_day']}. Nothing else was scheduled.")
    if limits.get("per_week") and week_count >= limits["per_week"]:
        raise DraftError(f"The weekly limit is {limits['per_week']}. Nothing else was scheduled.")


def _public_batch(state: dict, batch: dict | None) -> dict | None:
    if not batch:
        return None
    rows = []
    for item in batch.get("pieces") or []:
        piece = next((row for row in state.get("pieces") or [] if row.get("id") == item.get("piece_id")), None)
        rows.append(
            {
                "piece_id": item.get("piece_id") or "",
                "idea": str(item.get("idea") or "")[:180],
                "decision": item.get("decision") or "",
                "status": (piece or {}).get("status") or "",
                "posted": bool((piece or {}).get("posted")),
            }
        )
    return {"id": batch.get("id") or "", "notice": batch.get("notice") or "", "open": _open(batch), "pieces": rows}


def _public_log(item: dict) -> dict:
    return {"at": item.get("at") or "", "mode": item.get("mode") or "", "action": item.get("action") or "", "piece_id": item.get("piece_id") or "", "reason": item.get("reason") or "", "outcome": item.get("outcome") or ""}


def _limits(state: dict, brand_id: str) -> dict:
    raw = (state.get("mode_limits") or {}).get(brand_id) or {}
    return {"per_day": int(raw.get("per_day") or 0), "per_week": int(raw.get("per_week") or 0), "hold_hours": int(raw.get("hold_hours") or 0)}


def _cap(value, limit: int = 30) -> int:
    if value in (None, "", False):
        return 0
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > limit:
        raise DraftError("Limits are whole numbers.")
    return value


def _mode(state: dict, brand_id: str) -> str:
    name = str((state.get("modes") or {}).get(brand_id) or "manual")
    return name if name in _MODES else "manual"


def _log(state: dict, brand_id: str, mode: str, action: str, piece_id: str, reason: str, outcome: str) -> dict:
    from memory import redact_memory

    row = {"at": _now(), "brand_id": brand_id, "mode": mode, "action": action, "piece_id": piece_id, "reason": reason, "outcome": redact_memory(str(outcome))[:240]}
    return {**state, "mode_log": [row, *(state.get("mode_log") or [])][:1000]}


def _load(path: Path | None, state: dict) -> dict:
    from store import load

    # Saves without a path land in the default file, so read that back too.
    return load(path) if path else load()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
