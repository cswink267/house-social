"""The publishing queue. It does not send anything.

A piece moves from draft to review, then scheduled. On the record
means a real post is already tied to that draft. A slot is called
weak only when that format already has a real gap between hours.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from adapt import DraftError, issues
from brands import Brand
from learn import suggest_hour
from store import _find, _local_date_time, load, resolve_brand, update_piece


_OUT = {"pending", "approved", "scheduled", "failed"}
_ACTIONS = {"pending", "schedule", "draft", "retry"}
_STAGES = (
    ("draft", "Draft"),
    ("review", "Needs approval"),
    ("approved", "Approved"),
    ("scheduled", "Scheduled"),
    ("recorded", "On the record"),
    ("failed", "Failed"),
)
_STAGE = {
    "draft": "draft",
    "planned": "draft",
    "ready": "draft",
    "pending": "review",
    "approved": "approved",
    "scheduled": "scheduled",
    "failed": "failed",
}
_LABELS = {
    "draft": "Draft",
    "planned": "Draft",
    "ready": "Ready",
    "pending": "Needs review",
    "approved": "Approved",
    "scheduled": "Scheduled",
    "failed": "Failed",
}


def queue_for(state: dict, brand_id: str, posts: list[dict] | None = None) -> dict:
    brand = resolve_brand(state, brand_id)
    history = list(posts or [])
    items = [
        _item(brand, piece, history)
        for piece in state.get("pieces") or []
        if piece.get("brand_id") == brand.id
    ]
    items.sort(key=lambda item: (item.get("date") or "9999", item.get("time") or "", item.get("idea") or ""))
    from memory import marks_for, mute_lesson

    marks = marks_for(state, brand.id)
    formats = [
        row
        for row in format_hours(history)
        if marks.get("format") not in {"deleted", "demoted"} and marks.get("type:" + row["format"]) not in {"deleted", "demoted"}
    ]
    return {
        "items": items,
        "suggestion": mute_lesson(suggest_hour(history), marks, "hour", "hour"),
        "formats": formats,
        "pace": pace_line([piece for piece in state.get("pieces") or [] if piece.get("brand_id") == brand.id]),
        "stages": [{"id": stage_id, "label": label} for stage_id, label in _STAGES],
        "rules": rules_for(brand),
    }


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
    when = str(scheduled_for or "").strip()
    history = list(posts or [])
    current = state
    results = []
    for piece_id in chosen:
        current, result = _one(current, brand_id, piece_id, name, when, path, history)
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
        "Meta's rate limit is not applied here, because nothing is sent.",
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


def format_hours(posts: list[dict]) -> list[dict]:
    names = sorted({str(post.get("format") or "") for post in posts if post.get("format") not in (None, "", "unknown")})
    found = []
    for name in names:
        lesson = suggest_hour([post for post in posts if str(post.get("format") or "") == name])
        if not lesson.get("clear"):
            continue
        found.append({"format": name, "hour": lesson["hour"], "label": lesson["label"], "detail": lesson["detail"]})
    return found


def best_time(posts: list[dict], format_name: str, marks: dict | None = None) -> dict:
    from memory import mute_lesson

    held = marks or {}
    named = str(format_name or "")
    if named and named != "unknown" and held.get("format") not in {"deleted", "demoted"} and held.get("type:" + named) not in {"deleted", "demoted"}:
        lesson = suggest_hour([post for post in posts if str(post.get("format") or "") == named])
        if lesson.get("clear"):
            return {**lesson, "scope": "format"}
    brand = mute_lesson(suggest_hour(posts), held, "hour", "hour")
    if brand.get("clear"):
        return {**brand, "scope": "brand"}
    detail = brand.get("detail") or "Not enough hours to suggest a time."
    if named and named != "unknown":
        detail = f"Not enough {named} posts to name an hour. {detail}"
    return {"clear": False, "hour": None, "label": "", "detail": detail, "scope": ""}


def slot_warning(posts: list[dict], format_name: str, hour: int | None) -> str:
    if hour is None:
        return ""
    name = str(format_name or "")
    label = f"{hour:02d}:00"
    if not name or name == "unknown":
        return "This format is not named, so this slot cannot be compared."
    rows = [
        row for row in hour_rows([post for post in posts if str(post.get("format") or "") == name])
        if row["n"] >= 3
    ]
    here = next((row for row in rows if row["hour"] == hour), None)
    others = [row for row in rows if row["hour"] != hour]
    if here is None or not others:
        return f"Not enough {name} posts to compare {label}."
    best = max(others, key=lambda row: row["mean"])
    gap = best["mean"] - here["mean"]
    if best["mean"] > here["mean"] and best["mean"] >= here["mean"] * 1.5 and gap >= 3:
        return (
            f"{label} has underperformed for {name}. "
            f"Mean {here['mean']} (n={here['n']}) against {best['mean']} at {best['label']} (n={best['n']})."
        )
    return ""


def pace_line(pieces: list[dict]) -> str:
    counts: dict[tuple[str, str], int] = {}
    for piece in pieces:
        if piece.get("status") != "scheduled":
            continue
        day, _clock = _local_date_time(str(piece.get("scheduled_for") or ""))
        if not day:
            continue
        variants = piece.get("variants") or {}
        for platform in ("facebook", "instagram", "threads"):
            body = str((variants.get(platform) or {}).get("body") or "").strip()
            if body:
                counts[(day, platform)] = counts.get((day, platform), 0) + 1
    if not counts:
        return "Nothing is scheduled, so there is no rate to watch. This queue does not send."
    parts = [f"{platform} {count} on {day}" for (day, platform), count in sorted(counts.items())]
    return "Scheduled, not sent: " + ", ".join(parts) + ". Meta's rate limit is not applied here."


def _one(
    state: dict,
    brand_id: str,
    piece_id: str,
    action: str,
    when: str,
    path: Path | None,
    posts: list[dict],
) -> tuple[dict, dict]:
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
            from approval import submit_review

            saved = submit_review(state, piece_id, path=path)
        elif action == "retry" and piece.get("status") != "failed":
            raise DraftError("Retry is for a failed piece.")
        else:
            use = when
            if not use and not piece.get("scheduled_for"):
                from memory import marks_for

                chosen = best_time(posts, str(piece.get("format") or ""), marks_for(state, brand_id))
                if not chosen.get("clear"):
                    raise DraftError("A scheduled piece needs a time, and no hour is clearly ahead.")
                use = next_local_hour(int(chosen["hour"]))
            saved = update_piece(state, piece_id, status="scheduled", scheduled_for=use or None, path=path)
    except DraftError as exc:
        if action == "retry" and piece.get("status") != "failed":
            return state, {"id": piece_id, "ok": False, "status": piece.get("status") or "", "error": str(exc)}
        failed = update_piece(state, piece_id, status="failed", failure=str(exc), path=path)
        return state, {"id": piece_id, "ok": False, "status": failed.get("status"), "error": str(exc)}
    return state, {"id": piece_id, "ok": True, "status": saved.get("status"), "error": ""}


def _item(brand: Brand, piece: dict, posts: list[dict] | None = None) -> dict:
    status = piece.get("status") or "draft"
    day, clock = _local_date_time(str(piece.get("scheduled_for") or ""))
    history = list(posts or [])
    record = _record(str(piece.get("id") or ""), history)
    stage = "recorded" if record["linked"] else _STAGE.get(status, "draft")
    return {
        "id": piece.get("id"),
        "status": status,
        "label": _LABELS.get(status, "Draft"),
        "stage": stage,
        "lane": "out" if status in _OUT or record["linked"] else "making",
        "idea": str(piece.get("idea") or "")[:120],
        "format": piece.get("format") or "",
        "campaign": piece.get("campaign") or "",
        "date": day,
        "time": clock,
        "failure": piece.get("failure") or "",
        "problems": issues(brand, piece.get("variants") or {}),
        "slot": slot_warning(history, str(piece.get("format") or ""), _clock_hour(clock)),
        "record": record,
        "posted": False,
    }


def hour_rows(posts: list[dict]) -> list[dict]:
    from learn import hour_table

    return hour_table(posts)


def _clock_hour(clock: str) -> int | None:
    if not clock or ":" not in clock:
        return None
    hour = int(clock.split(":", 1)[0])
    return hour if 0 <= hour <= 23 else None


def _record(piece_id: str, posts: list[dict]) -> dict:
    matched = [post for post in posts if str(post.get("piece_id") or "") == piece_id and piece_id]
    if not matched:
        return {
            "linked": False,
            "post_id": "",
            "engagements": None,
            "impressions": None,
            "detail": "No post is tied to this draft yet.",
            "permalink": "",
        }
    post = max(matched, key=lambda item: int(item.get("engagements") or 0))
    engagements = int(post.get("engagements") or 0)
    impressions = post.get("impressions")
    shown = impressions if isinstance(impressions, int) and not isinstance(impressions, bool) and impressions > 0 else None
    detail = f"{engagements} engagements on the post tied to this draft."
    if shown is not None:
        detail = f"{engagements} engagements from {shown} impressions on the post tied to this draft."
    return {
        "linked": True,
        "post_id": str(post.get("id") or ""),
        "engagements": engagements,
        "impressions": shown,
        "detail": detail,
        "permalink": str(post.get("permalink") or ""),
    }
