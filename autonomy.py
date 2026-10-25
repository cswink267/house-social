"""One post a day for every brand that is not manual.

Fully autonomous writes the three versions and schedules them. Approval
writes them and sends them for review. Manual is left alone. The
dashboard worker calls this once a minute; a brand acts once each
New York day. Posting still waits for the piece's time and both switches.

Callers: publish.tick. State key mode_runs is brand id to YYYY-MM-DD.
The user asked for the desk to run on its own.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from adapt import DraftError, issues
from brands import PILLARS
from learn import suggest_hour
from modes import _log, _mode
from queue_desk import next_local_hour
from store import _copy, brand_history, create_piece, load, resolve_brand, roster, save

_ZONE = ZoneInfo("America/New_York")
_STANDING_HOUR = 10


def run_daily(state: dict, path: Path | None = None, now: datetime | None = None) -> list[dict]:
    """Make today's post for each brand that is not manual. A second pass the same day does nothing."""
    moment = _moment(now)
    today = moment.date().isoformat()
    results = []
    for row in roster(state):
        brand_id = row["id"]
        if _mode(state, brand_id) == "manual":
            continue
        current = load(path) if path else load()
        if str((current.get("mode_runs") or {}).get(brand_id) or "") == today:
            continue
        try:
            outcome = _once(current, brand_id, path, moment)
        except DraftError as exc:
            outcome = {"brand_id": brand_id, "status": "held", "detail": str(exc)}
            _remember(load(path) if path else load(), brand_id, str(exc), path)
        _mark_day(load(path) if path else load(), brand_id, today, path)
        results.append(outcome)
    return results


def _once(state: dict, brand_id: str, path: Path | None, moment: datetime) -> dict:
    from support import assert_running

    brand = resolve_brand(state, brand_id)
    assert_running(state, brand.id)
    mode = _mode(state, brand.id)
    idea = _idea(brand, moment.date())
    piece = create_piece(state, brand.id, idea, path, pillar=_pillar_id(brand.id, moment.date()))
    fresh = load(path) if path else load()
    saved = next(row for row in fresh["pieces"] if row["id"] == piece["id"])
    problems = issues(brand, saved.get("variants") or {})
    if problems:
        raise DraftError(" ".join(problems))
    when = next_local_hour(_hour(fresh, brand.id), moment)
    if mode == "auto":
        from modes import agent_schedule

        scheduled = agent_schedule(fresh, piece["id"], when, path)
        _remember(load(path) if path else load(), brand.id, scheduled["detail"], path)
        return {"brand_id": brand.id, "piece_id": piece["id"], "status": scheduled["status"], "detail": scheduled["detail"]}
    from store import update_piece

    update_piece(fresh, piece["id"], scheduled_for=when, path=path)
    from approval import submit_review

    reviewed = submit_review(load(path) if path else load(), piece["id"], path)
    detail = "Sent for review. It is scheduled once it is approved."
    _remember(load(path) if path else load(), brand.id, detail, path)
    return {"brand_id": brand.id, "piece_id": piece["id"], "status": reviewed.get("status") or "pending", "detail": detail}


def _idea(brand, day) -> str:
    pillars = PILLARS.get(brand.id) or ()
    if pillars:
        pillar = pillars[day.toordinal() % len(pillars)]
        opening = f"{pillar.name}. {pillar.note}".strip()
    else:
        opening = (brand.voice or brand.name).strip()
    if brand.id == "jamhaul":
        if "jamhaul.com" not in opening.lower():
            opening = opening.rstrip(".") + ". jamhaul.com"
        if "?" not in opening:
            opening = opening.rstrip(".") + "?"
    if opening[-1:] not in ".?":
        opening += "."
    return f"{opening} That is today's post."


def _pillar_id(brand_id: str, day) -> str:
    pillars = PILLARS.get(brand_id) or ()
    if not pillars:
        return ""
    return pillars[day.toordinal() % len(pillars)].id


def _hour(state: dict, brand_id: str) -> int:
    history = brand_history(state, brand_id)[0]
    lesson = suggest_hour(history)
    hour = lesson.get("hour")
    if lesson.get("clear") and isinstance(hour, int) and 0 <= hour <= 23:
        return hour
    return _STANDING_HOUR


def _moment(now: datetime | None) -> datetime:
    moment = now or datetime.now(_ZONE)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=_ZONE)
    return moment.astimezone(_ZONE)


def _mark_day(state: dict, brand_id: str, today: str, path: Path | None) -> None:
    updated = _copy(state)
    runs = dict(updated.get("mode_runs") or {})
    runs[brand_id] = today
    updated["mode_runs"] = runs
    save(updated, path)


def _remember(state: dict, brand_id: str, detail: str, path: Path | None) -> None:
    updated = _log(state, brand_id, _mode(state, brand_id), "daily", "", "day", detail[:240])
    save(updated, path)
