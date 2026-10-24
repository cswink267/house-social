"""Supports around the three modes.

Callers: modes.prepare_batch, modes.run_auto, modes.set_mode, and the
support route. Nothing here sends mail or a post. A hold names a count.
The user said continue, and this is the supporting-features item.
"""

from __future__ import annotations

import copy
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from adapt import DraftError
from memory import redact_memory


def support_view(state: dict, brand_id: str, posts: list[dict] | None = None) -> dict:
    from store import brand_history, resolve_brand

    brand = resolve_brand(state, brand_id)
    history = list(posts) if posts is not None else brand_history(state, brand.id)[0]
    return {
        "health": health(state, brand.id, history),
        "mail": _mail(state, brand.id),
        "mix": list((state.get("mix_targets") or {}).get(brand.id) or []),
        "pause": (state.get("pauses") or {}).get(brand.id) or {"start": "", "end": ""},
        "adapt": _adapt(state, brand.id),
        "previews": [item for item in state.get("previews") or [] if item.get("brand_id") == brand.id],
        "log_count": len([item for item in state.get("mode_log") or [] if item.get("brand_id") == brand.id]),
    }


def health(state: dict, brand_id: str, posts: list[dict]) -> dict:
    from modes import _mode, _rate
    from store import resolve_brand

    brand = resolve_brand(state, brand_id)
    dated = [post for post in posts if post.get("published_at") and post.get("engagements") is not None]
    ingests = [item for item in state.get("ingest_log") or [] if item.get("brand_id") == brand_id]
    last = str(ingests[0].get("at") or "")[:10] if ingests else "none"
    return {
        "mode": _mode(state, brand_id),
        "ingest": last,
        "posts": len(dated),
        "rate": _rate(state, brand_id),
        "guards": [str(item) for item in brand.guards][:6],
        "hint": "No history yet. Open Ingest." if not dated else "",
    }


def assert_running(state: dict, brand_id: str) -> None:
    pause = (state.get("pauses") or {}).get(brand_id) or {}
    start, end = str(pause.get("start") or ""), str(pause.get("end") or "")
    if not start or not end:
        return
    today = datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    if start <= today <= end:
        raise DraftError(f"This brand is paused until {end}. Already scheduled pieces stay.")


def mail_notice(state: dict, brand_id: str) -> str:
    prefs = _mail(state, brand_id)
    base = "The mail path is not configured. These pieces stay unscheduled."
    if _quiet(prefs):
        return f"Quiet hours. Mail would wait. {base}"
    if prefs.get("cadence") == "digest":
        return f"Digest is set. {base}"
    return base


def clear_log(state: dict, brand_id: str, path: Path | None = None) -> dict:
    from modes import _log, _mode
    from store import resolve_brand, save

    brand = resolve_brand(state, brand_id)
    updated = copy.deepcopy(state)
    updated["mode_log"] = [item for item in updated.get("mode_log") or [] if item.get("brand_id") != brand.id]
    updated = _log(updated, brand.id, _mode(updated, brand.id), "clear", "", "user", "The log was cleared.")
    save(updated, path)
    return support_view(updated, brand.id)


def save_mail(state: dict, brand_id: str, spec: dict, path: Path | None = None) -> dict:
    from store import resolve_brand, save

    brand = resolve_brand(state, brand_id)
    if not isinstance(spec, dict):
        raise DraftError("Mail settings need a cadence.")
    cadence = str(spec.get("cadence") or "immediate").strip().lower()
    if cadence not in {"immediate", "digest"}:
        raise DraftError("Cadence is immediate or digest.")
    body = str(spec.get("body") or "short").strip().lower()
    if body not in {"short", "full"}:
        raise DraftError("The mail body is short or full.")
    prefs = {"cadence": cadence, "body": body, "quiet_start": _hour(spec.get("quiet_start")), "quiet_end": _hour(spec.get("quiet_end"))}
    updated = copy.deepcopy(state)
    book = dict(updated.get("mail_prefs") or {})
    book[brand.id] = prefs
    updated["mail_prefs"] = book
    save(updated, path)
    return support_view(updated, brand.id)


def save_mix(state: dict, brand_id: str, spec: dict, path: Path | None = None) -> dict:
    from store import resolve_brand, save

    brand = resolve_brand(state, brand_id)
    row = _mix_row(spec)
    updated = copy.deepcopy(state)
    book = dict(updated.get("mix_targets") or {})
    current = [item for item in book.get(brand.id) or [] if not (item.get("kind") == row["kind"] and item.get("name") == row["name"] and item.get("bound") == row["bound"])]
    book[brand.id] = current[:12] if spec.get("remove") else (current + [row])[:12]
    updated["mix_targets"] = book
    save(updated, path)
    return support_view(updated, brand.id)


def save_pause(state: dict, brand_id: str, spec: dict, path: Path | None = None) -> dict:
    from modes import _log, _mode
    from store import resolve_brand, save

    brand = resolve_brand(state, brand_id)
    start, end = _dates(spec)
    updated = copy.deepcopy(state)
    book = dict(updated.get("pauses") or {})
    if start:
        book[brand.id] = {"start": start, "end": end}
        outcome = f"Paused {start} to {end}."
    else:
        book.pop(brand.id, None)
        outcome = "Pause cleared."
    updated["pauses"] = book
    updated = _log(updated, brand.id, _mode(updated, brand.id), "pause", "", "user", outcome)
    save(updated, path)
    return support_view(updated, brand.id)


def save_adapt(state: dict, brand_id: str, spec: dict, path: Path | None = None) -> dict:
    from store import resolve_brand, save

    brand = resolve_brand(state, brand_id)
    if not isinstance(spec, dict):
        raise DraftError("Adaptation rules need fields.")
    quote = spec.get("quote_image")
    site = spec.get("require_site")
    if brand.id == "josie-blackthorn" and quote is False:
        raise DraftError("Josie Facebook stays a quote image.")
    if brand.id == "jamhaul" and site is False:
        raise DraftError("JamHaul keeps the site and the question.")
    rules = {
        "max_length": _cap(spec.get("max_length"), 5000),
        "first_comment": bool(spec.get("first_comment")),
        "quote_image": True if brand.id == "josie-blackthorn" else bool(quote),
        "require_site": True if brand.id == "jamhaul" else bool(site),
    }
    updated = copy.deepcopy(state)
    book = dict(updated.get("adapt_rules") or {})
    book[brand.id] = rules
    updated["adapt_rules"] = book
    save(updated, path)
    return support_view(updated, brand.id)


def teach_rejection(state: dict, brand_id: str, choice: str, phrase: str, fmt: str, path: Path | None = None) -> dict:
    from modes import _log, _mode
    from store import resolve_brand, save, save_voice
    from voice import guide_for

    brand = resolve_brand(state, brand_id)
    name = str(choice or "discard").strip().lower()
    text = str(phrase or "").strip()[:120]
    updated = copy.deepcopy(state)
    if name == "discard":
        pass
    elif name == "banned":
        if not text:
            raise DraftError("Write the phrase before it can be banned.")
        guide = guide_for(brand.id, (updated.get("voices") or {}).get(brand.id))
        guide["banned"] = list(guide.get("banned") or []) + [text]
        save_voice(updated, brand.id, guide, path, note="rejection")
        updated = _load(path, updated)
    elif name == "voice":
        if not text:
            raise DraftError("Write the voice note first.")
        guide = guide_for(brand.id, (updated.get("voices") or {}).get(brand.id))
        guide["donts"] = list(guide.get("donts") or []) + [text]
        save_voice(updated, brand.id, guide, path, note="rejection")
        updated = _load(path, updated)
    elif name == "demote":
        from memory import correct_memory

        target = "type:" + fmt if fmt and fmt != "unknown" else "format"
        correct_memory(updated, brand.id, target, "demote", path)
        updated = _load(path, updated)
    else:
        raise DraftError("Teach choices are discard, banned, demote, and voice.")
    updated = _log(updated, brand.id, _mode(updated, brand.id), "teach", "", name, text or name)
    save(updated, path)
    return support_view(updated, brand.id)


def mix_hold(state: dict, brand_id: str, fmt: str, pillar: str) -> str:
    for row in (state.get("mix_targets") or {}).get(brand_id) or []:
        if row.get("bound") != "most" or not row.get("hard"):
            continue
        name = row.get("name") or ""
        if row.get("kind") == "format" and name != fmt:
            continue
        if row.get("kind") == "pillar" and name != pillar:
            continue
        count = _week_count(state, brand_id, row.get("kind") or "", name)
        if count + 1 > int(row.get("count") or 0):
            return f"Held. {name} is at {count} this week. The hard target is no more than {int(row.get('count') or 0)}."
    return ""


def preview_week(state: dict, brand_id: str, path: Path | None = None) -> dict:
    from learn import suggest_hour
    from store import brand_history, resolve_brand, save

    brand = resolve_brand(state, brand_id)
    assert_running(state, brand.id)
    history = brand_history(state, brand.id)[0]
    hour = suggest_hour(history)
    if not hour.get("clear"):
        raise DraftError("Nothing learned is clear enough to preview.")
    idea = ("Preview only. " + str(hour.get("detail") or ""))[:500]
    today = datetime.now(ZoneInfo("America/New_York")).date()
    rows = []
    for offset in range(1, 8):
        rows.append({"id": str(uuid.uuid4()), "brand_id": brand.id, "idea": idea, "date": (today + timedelta(days=offset)).isoformat(), "stale": False, "preview": True})
    updated = copy.deepcopy(state)
    others = [item for item in updated.get("previews") or [] if item.get("brand_id") != brand.id]
    updated["previews"] = others + rows
    save(updated, path)
    return support_view(updated, brand.id)


def promote_preview(state: dict, brand_id: str, preview_id: str, path: Path | None = None) -> dict:
    from store import create_piece, resolve_brand, save

    brand = resolve_brand(state, brand_id)
    found = _preview(state, brand.id, preview_id)
    if found.get("stale"):
        raise DraftError("That preview is stale. Run it again.")
    piece = create_piece(state, brand.id, str(found.get("idea") or "")[:500], path, status="planned")
    current = _load(path, state)
    updated = copy.deepcopy(current)
    updated["previews"] = [item for item in updated.get("previews") or [] if item.get("id") != preview_id]
    save(updated, path)
    made = next(item for item in updated["pieces"] if item.get("id") == piece["id"])
    if made.get("status") == "scheduled" or made.get("posted"):
        raise DraftError("A preview cannot be scheduled from here.")
    return support_view(updated, brand.id)


def discard_previews(state: dict, brand_id: str, preview_id: str = "", path: Path | None = None) -> dict:
    from store import resolve_brand, save

    brand = resolve_brand(state, brand_id)
    updated = copy.deepcopy(state)
    if preview_id:
        updated["previews"] = [item for item in updated.get("previews") or [] if item.get("id") != preview_id]
    else:
        updated["previews"] = [item for item in updated.get("previews") or [] if item.get("brand_id") != brand.id]
    save(updated, path)
    return support_view(updated, brand.id)


def stale_previews(state: dict, brand_id: str) -> dict:
    rows = []
    for item in state.get("previews") or []:
        if item.get("brand_id") == brand_id:
            rows.append({**item, "stale": True})
        else:
            rows.append(item)
    return {**state, "previews": rows}


def export_decisions(state: dict, brand_id: str, kind: str) -> dict:
    from store import resolve_brand

    brand = resolve_brand(state, brand_id)
    rows = [item for item in state.get("mode_log") or [] if item.get("brand_id") == brand.id]
    name = str(kind or "markdown").strip().lower()
    if name == "json":
        import json

        body = json.dumps([{key: item.get(key) or "" for key in ("at", "mode", "action", "piece_id", "reason", "outcome")} for item in rows[:200]], indent=2)
    elif name == "markdown":
        lines = ["# Decisions", ""]
        lines.extend(f"- {item.get('at') or ''} {item.get('mode') or ''} {item.get('action') or ''} {item.get('outcome') or ''}" for item in rows[:200])
        body = "\n".join(lines) + "\n"
    else:
        raise DraftError("Export is markdown or json.")
    return {"format": name, "body": redact_memory(body)}


def set_series_pause(state: dict, brand_id: str, series_id: str, paused: bool, path: Path | None = None) -> dict:
    from store import resolve_brand, save

    brand = resolve_brand(state, brand_id)
    found = next((item for item in state.get("series") or [] if item.get("id") == series_id), None)
    if found is None or found.get("brand_id") != brand.id:
        raise DraftError("That series is not on this brand.")
    updated = copy.deepcopy(state)
    flags = dict(updated.get("series_paused") or {})
    if paused:
        flags[series_id] = True
    else:
        flags.pop(series_id, None)
    updated["series_paused"] = flags
    save(updated, path)
    return {"id": series_id, "paused": bool(paused)}


def fill_series(state: dict, brand_id: str, series_id: str) -> dict:
    from brands import pillars_for
    from store import resolve_brand

    brand = resolve_brand(state, brand_id)
    found = next((item for item in state.get("series") or [] if item.get("id") == series_id and item.get("brand_id") == brand.id), None)
    if found is None:
        raise DraftError("No series is saved.")
    if (state.get("series_paused") or {}).get(series_id):
        raise DraftError("That series is paused.")
    pillars = pillars_for(brand.id)
    if not pillars:
        raise DraftError("This brand has no pillar to fill.")
    topic = str(pillars[0].get("name") or pillars[0].get("id") or "")
    return {"topic": topic, "lines": [str(line).replace("{topic}", topic) for line in found.get("structure") or []], "paused": False}


def _mail(state: dict, brand_id: str) -> dict:
    raw = (state.get("mail_prefs") or {}).get(brand_id) or {}
    return {"cadence": raw.get("cadence") or "immediate", "body": raw.get("body") or "short", "quiet_start": int(raw.get("quiet_start") or 0), "quiet_end": int(raw.get("quiet_end") or 0)}


def _adapt(state: dict, brand_id: str) -> dict:
    raw = (state.get("adapt_rules") or {}).get(brand_id) or {}
    return {
        "max_length": int(raw.get("max_length") or 0),
        "first_comment": bool(raw.get("first_comment")),
        "quote_image": True if brand_id == "josie-blackthorn" else bool(raw.get("quote_image")),
        "require_site": True if brand_id == "jamhaul" else bool(raw.get("require_site")),
    }


def _quiet(prefs: dict) -> bool:
    start, end = int(prefs.get("quiet_start") or 0), int(prefs.get("quiet_end") or 0)
    if start == end:
        return False
    hour = datetime.now(ZoneInfo("America/New_York")).hour
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def _mix_row(spec: dict) -> dict:
    if not isinstance(spec, dict):
        raise DraftError("A mix target needs a name and a count.")
    kind = str(spec.get("kind") or "").strip().lower()
    bound = str(spec.get("bound") or "").strip().lower()
    name = str(spec.get("name") or "").strip()[:40]
    if kind not in {"format", "pillar"} or bound not in {"most", "least"} or not name:
        raise DraftError("A mix target needs a format or pillar, and most or least.")
    return {"kind": kind, "name": name, "bound": bound, "count": _cap(spec.get("count"), 30), "hard": bool(spec.get("hard"))}


def _week_count(state: dict, brand_id: str, kind: str, name: str) -> int:
    zone = ZoneInfo("America/New_York")
    today = datetime.now(zone).date()
    start = today - timedelta(days=today.weekday())
    count = 0
    for piece in state.get("pieces") or []:
        if piece.get("brand_id") != brand_id or piece.get("status") != "scheduled":
            continue
        if kind == "format" and piece.get("format") != name:
            continue
        if kind == "pillar" and piece.get("pillar") != name:
            continue
        try:
            when = datetime.fromisoformat(str(piece.get("scheduled_for") or ""))
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if when.astimezone(zone).date() >= start:
            count += 1
    return count


def _dates(spec: dict) -> tuple[str, str]:
    if not isinstance(spec, dict):
        raise DraftError("A pause needs a start and an end.")
    start, end = str(spec.get("start") or "").strip(), str(spec.get("end") or "").strip()
    if not start and not end:
        return "", ""
    try:
        datetime.fromisoformat(start)
        datetime.fromisoformat(end)
    except ValueError as exc:
        raise DraftError("A pause uses dates.") from exc
    if end < start:
        raise DraftError("The pause end is after the start.")
    return start[:10], end[:10]


def _hour(value) -> int:
    if value in (None, "", False):
        return 0
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 23:
        raise DraftError("Quiet hours are 0 through 23.")
    return value


def _cap(value, limit: int) -> int:
    if value in (None, "", False):
        return 0
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > limit:
        raise DraftError("That number is too large.")
    return value


def _preview(state: dict, brand_id: str, preview_id: str) -> dict:
    found = next((item for item in state.get("previews") or [] if item.get("id") == preview_id), None)
    if found is None or found.get("brand_id") != brand_id:
        raise DraftError("That preview is not on this brand.")
    return found


def _load(path: Path | None, state: dict) -> dict:
    from store import load

    # Saves without a path land in the default file, so read that back too.
    return load(path) if path else load()
