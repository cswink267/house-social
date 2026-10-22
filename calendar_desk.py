"""Calendar advice for House Social.

A gap is a pillar with nothing in the next 7 days. A slot is an hour or a
weekday only when that pattern is already clear. Called by studio and the
recurrence routes. The user asked the calendar to plan from what worked.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from analytics_desk import _weekday_pattern
from learn import MIN_SAMPLE, format_table, suggest_hour


def advise(entries: list[dict], pillars: list[dict], posts: list[dict], today: date) -> dict:
    window = [(today + timedelta(days=offset)).isoformat() for offset in range(1, 8)]
    held = [item for item in entries if item.get("kind") == "piece" and item.get("date") in set(window)]
    gaps = []
    mix = []
    for pillar in pillars or []:
        count = sum(1 for item in held if item.get("pillar") == pillar.get("id"))
        mix.append({"id": pillar.get("id") or "", "name": pillar.get("name") or pillar.get("id") or "", "n": count})
        if count == 0 and pillar.get("name"):
            gaps.append(f"The next 7 days have no {pillar['name']}.")
    if not pillars:
        gaps.append("This brand has no pillars to check.")
    elif not gaps:
        gaps.append("Every pillar on this brand has something in the next 7 days.")
    hour = suggest_hour(posts)
    day = _weekday_pattern(posts)
    return {
        "gaps": gaps,
        "mix": mix,
        "warnings": _warnings(held, posts),
        "slot": _slot(today, entries, hour, day),
    }


def next_dates(today: date, weekday: int, weeks: int) -> list[date]:
    found = []
    day = today + timedelta(days=1)
    while len(found) < weeks and (day - today).days <= 70:
        if day.weekday() == weekday:
            found.append(day)
        day += timedelta(days=1)
    return found


def slot_when(day: date, hour: int | None) -> str:
    if hour is None:
        return day.isoformat()
    return datetime(day.year, day.month, day.day, hour, 0, tzinfo=ZoneInfo("America/New_York")).isoformat()


def _slot(today: date, entries: list[dict], hour: dict, day: dict) -> dict:
    hour_clear = bool(hour.get("clear")) and isinstance(hour.get("hour"), int)
    day_clear = bool(day.get("clear")) and isinstance(day.get("weekday"), int)
    if not hour_clear and not day_clear:
        detail = hour.get("detail") or day.get("detail") or "No hour or day is clearly ahead."
        return {"clear": False, "date": "", "hour": None, "label": "", "detail": detail}
    weekday = day.get("weekday") if day_clear else None
    chosen = _open_day(today, entries, weekday)
    if day_clear and hour_clear:
        label = f"{_weekday_name(weekday)} at {hour.get('label') or ''}"
    elif day_clear:
        label = _weekday_name(weekday)
    else:
        label = hour.get("label") or ""
    parts = []
    if hour_clear:
        parts.append(hour.get("detail") or "")
    if day_clear:
        parts.append(day.get("detail") or "")
    return {
        "clear": True,
        "date": chosen.isoformat() if chosen else "",
        "hour": hour.get("hour") if hour_clear else None,
        "label": label.strip(),
        "detail": " ".join(part for part in parts if part).strip(),
    }


def _open_day(today: date, entries: list[dict], weekday: int | None) -> date | None:
    occupied = {item.get("date") for item in entries if item.get("kind") == "piece" and item.get("date")}
    span = 14 if weekday is not None else 7
    empty = None
    fallback = None
    for offset in range(1, span + 1):
        day = today + timedelta(days=offset)
        if weekday is not None and day.weekday() != weekday:
            continue
        if fallback is None:
            fallback = day
        if day.isoformat() not in occupied and empty is None:
            empty = day
    return empty or fallback


def _warnings(held: list[dict], posts: list[dict]) -> list[str]:
    ready = [row for row in format_table([post for post in posts if post.get("format") not in (None, "", "unknown")]) if row["n"] >= MIN_SAMPLE]
    if len(ready) < 2:
        return []
    best, second = ready[0], ready[1]
    if not (best["mean"] >= second["mean"] * 1.5 and (best["mean"] - second["mean"]) >= 3):
        return []
    ahead = sum(1 for item in held if item.get("format") == best["format"])
    behind = sum(1 for item in held if item.get("format") == second["format"])
    if behind <= ahead:
        return []
    return [
        (
            f"The next 7 days hold {behind} {second['label']} and {ahead} {best['label']}. "
            f"{best['label']} averaged {best['mean']} engagements (n={best['n']}). "
            f"{second['label']} averaged {second['mean']} (n={second['n']})."
        )
    ]


def _weekday_name(weekday: int | None) -> str:
    names = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
    if weekday is None or not 0 <= int(weekday) <= 6:
        return ""
    return names[int(weekday)]
