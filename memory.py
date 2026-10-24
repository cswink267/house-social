"""What a brand currently holds, and the corrections on top of it.

Callers: store.studio, dashboard memory routes, ingest.commit_ingest,
calendar_desk.advise, and queue_desk.queue_for. State keys are
memory_marks (brand id to pattern id to pinned, demoted, or deleted)
and memory_log (before, after, kind). The user said continue, one
todo item at a time, and the next item is the Memory panel.
"""

from __future__ import annotations

import copy
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from analytics_desk import _alerts, annotate
from learn import MIN_SAMPLE, format_table
from voice import guide_for, voice_lessons


_ZONE = ZoneInfo("America/New_York")
_ID = re.compile(r"^[a-z0-9:_-]{1,64}$")
_HELD = {"deleted", "demoted"}
_ACTIONS = {"pin": "pinned", "demote": "demoted", "delete": "deleted"}
_GROUPS = (
    ("hooks", "Hooks", ("hook", "length")),
    ("formats", "Formats", ("format",)),
    ("times", "Times", ("hour", "weekday")),
    ("pillars", "Pillars", ("pillar",)),
    ("ctas", "Asks", ("cta", "question")),
    ("voice", "Voice", ("assisted",)),
)
_ORDER = ("hooks", "formats", "times", "pillars", "types", "ctas", "voice")
_WRITTEN = (
    "tone",
    "personality",
    "formality",
    "humor",
    "point_of_view",
    "differentiation",
    "visual",
    "dos",
    "donts",
    "banned",
    "preferred",
    "required",
)


def memory_for(state: dict, brand_id: str, posts: list[dict], pieces: list[dict] | None = None) -> dict:
    from store import resolve_brand

    resolve_brand(state, brand_id)
    marks = _marks(state, brand_id)
    lines = _lines(state, brand_id, posts, pieces or [], marks)
    return {
        "lines": lines,
        "sections": _sections(lines),
        "timeline": _timeline(state, brand_id, posts),
        "marks": marks,
        "accuracy": _accuracy(state, brand_id),
    }


def _accuracy(state: dict, brand_id: str) -> list[dict]:
    from predict import accuracy_for

    return accuracy_for(state, brand_id)


def correct_memory(state: dict, brand_id: str, pattern_id: str, action: str, path: Path | None = None) -> dict:
    from store import resolve_brand, save

    resolve_brand(state, brand_id)
    name = str(pattern_id or "").strip()
    verb = str(action or "").strip().lower()
    if verb not in {*_ACTIONS, "restore"}:
        raise _error("Memory actions are pin, demote, delete, and restore.")
    if not _ID.fullmatch(name):
        raise _error("That pattern is not on this brand.")
    posts, pieces = _brand_posts(state, brand_id)
    current = memory_for(state, brand_id, posts, pieces)
    known = {line["id"] for line in current["lines"]} | set(_marks(state, brand_id))
    if name not in known:
        raise _error("That pattern is not on this brand.")
    before = next((line["detail"] for line in current["lines"] if line["id"] == name), "")
    updated = copy.deepcopy(state)
    marks = dict(_marks(updated, brand_id))
    if verb == "restore":
        marks.pop(name, None)
        after = "restored"
    else:
        marks[name] = _ACTIONS[verb]
        after = _ACTIONS[verb]
    book = dict(updated.get("memory_marks") or {})
    book[brand_id] = marks
    updated["memory_marks"] = book
    updated["memory_log"] = _push(updated, brand_id, verb, name, before, after)
    save(updated, path)
    return memory_for(updated, brand_id, posts, pieces)


def reset_memory(state: dict, brand_id: str, path: Path | None = None) -> dict:
    from store import resolve_brand, save

    resolve_brand(state, brand_id)
    posts, pieces = _brand_posts(state, brand_id)
    current = memory_for(state, brand_id, posts, pieces)
    before = " ".join(line["detail"] for line in current["lines"] if line["standing"] != "deleted")[:500]
    updated = copy.deepcopy(state)
    book = dict(updated.get("memory_marks") or {})
    book[brand_id] = {line["id"]: "deleted" for line in current["lines"]}
    updated["memory_marks"] = book
    updated["memory_log"] = _push(updated, brand_id, "reset", "", before, "Learned patterns cleared. The posts are still here.")
    save(updated, path)
    return memory_for(updated, brand_id, posts, pieces)


def sync_memory(state: dict, brand_id: str, path: Path | None = None) -> dict:
    from store import resolve_brand, save

    resolve_brand(state, brand_id)
    posts, pieces = _brand_posts(state, brand_id)
    fresh = [
        item
        for item in _ahead_events(brand_id, posts)
        if not any(
            saved.get("kind") == "ahead" and saved.get("pattern_id") == item["pattern_id"] and saved.get("brand_id") == brand_id
            for saved in state.get("memory_log") or []
        )
    ]
    if not fresh:
        return memory_for(state, brand_id, posts, pieces)
    updated = copy.deepcopy(state)
    updated["memory_log"] = (fresh + list(updated.get("memory_log") or []))[:80]
    save(updated, path)
    return memory_for(updated, brand_id, posts, pieces)


def export_memory(state: dict, brand_id: str, kind: str) -> dict:
    posts, pieces = _brand_posts(state, brand_id)
    view = memory_for(state, brand_id, posts, pieces)
    name = str(kind or "").strip().lower()
    if name == "json":
        body = json.dumps({"lines": view["lines"], "timeline": view["timeline"]}, indent=2)
    elif name == "markdown":
        body = _markdown(view)
    else:
        raise _error("Export is markdown or json.")
    return {"format": name, "body": redact_memory(body)}


def remember_import(state: dict, brand_id: str, lines: list[str]) -> dict:
    return {**state, "memory_log": _push(state, brand_id, "import", "", "", " ".join(str(line) for line in lines)[:500])}


def marks_for(state: dict, brand_id: str) -> dict:
    return _marks(state, brand_id)


def mute_lesson(lesson: dict, marks: dict | None, pattern_id: str, label: str) -> dict:
    standing = (marks or {}).get(pattern_id)
    if standing not in _HELD:
        return lesson
    word = "deleted" if standing == "deleted" else "lowered"
    detail = str(lesson.get("detail") or "").strip()
    note = f"The {label} pattern was {word}."
    if note not in detail:
        detail = (detail + " " + note).strip()
    muted = {**lesson, "clear": False, "detail": detail}
    if "hour" in lesson:
        muted["hour"] = None
    if "label" in lesson:
        muted["label"] = ""
    return muted


def redact_memory(text: str) -> str:
    from meta import redact

    cleaned = redact(str(text or ""))
    cleaned = re.sub(r"vault:[A-Za-z0-9._:-]+", "vault:redacted", cleaned)
    cleaned = re.sub(r"/(?:home|Users)/\S+", "[path]", cleaned)
    return cleaned


def _lines(state: dict, brand_id: str, posts: list[dict], pieces: list[dict], marks: dict) -> list[dict]:
    window = [post for post in posts if post.get("published_at") and post.get("engagements") is not None]
    _start, _end, span = _span(window)
    count = len(window)
    found = {item["id"]: item for item in annotate(window, pieces)["patterns"]}
    lines = []
    for section, _title, ids in _GROUPS:
        for pattern_id in ids:
            pattern = found.get(pattern_id) or {}
            detail = str(pattern.get("detail") or "Nothing is held for this yet.")
            thin = not pattern.get("clear") and _is_thin(detail)
            lines.append(_row(pattern_id, section, str(pattern.get("title") or pattern_id), detail, count, span, thin, "posts", marks))
    for row in format_table(window):
        counted = int(row["n"])
        detail = f"{row['label']} averaged {row['mean']} engagements (n={counted})."
        lines.append(_row("type:" + row["format"], "types", row["label"], detail, counted, span, counted < MIN_SAMPLE, "posts", marks))
    guide = guide_for(brand_id, (state.get("voices") or {}).get(brand_id))
    lessons = voice_lessons(guide, window)
    if not lessons.get("ready"):
        lines.append(_row("voice:waiting", "voice", "Voice", str(lessons.get("detail") or ""), count, span, True, "posts", marks))
    for item in lessons.get("suggestions") or []:
        lines.append(
            _row(
                "voice:" + str(item.get("id") or "note"),
                "voice",
                str(item.get("line") or "Voice"),
                str(item.get("detail") or ""),
                count,
                span,
                not item.get("clear"),
                "posts",
                marks,
            )
        )
    for key in _WRITTEN:
        text = _written(guide.get(key))
        if not text:
            continue
        lines.append(
            _row(
                "written:" + key,
                "voice",
                key,
                "Written in the voice guide. Not counted from posts. " + text,
                None,
                "",
                False,
                "written",
                marks,
            )
        )
    return lines


def _row(pattern_id, section, title, detail, count, span, thin, source, marks) -> dict:
    body = str(detail or "").strip()
    if thin and "thin" not in body.lower():
        body = "This is thin. " + body
    if source == "posts":
        body = f"{body} Based on {count} posts. {span}".strip()
    return {
        "id": pattern_id,
        "section": section,
        "title": title,
        "detail": body,
        "n": count,
        "thin": bool(thin),
        "standing": marks.get(pattern_id) or "open",
        "source": source,
    }


def _sections(lines: list[dict]) -> list[dict]:
    labels = {key: label for key, label, _ids in _GROUPS}
    labels["types"] = "Engagement by type"
    grouped = []
    for key in _ORDER:
        rows = [line for line in lines if line["section"] == key]
        if rows:
            grouped.append({"id": key, "label": labels[key], "lines": rows})
    return grouped


def _timeline(state: dict, brand_id: str, posts: list[dict]) -> list[dict]:
    stored = [item for item in state.get("memory_log") or [] if item.get("brand_id") == brand_id]
    seen = {(item.get("kind"), item.get("pattern_id")) for item in stored}
    extra = [item for item in _ahead_events(brand_id, posts) if (item["kind"], item["pattern_id"]) not in seen]
    return [_public_event(item) for item in (extra + stored)[:24]]


def _ahead_events(brand_id: str, posts: list[dict]) -> list[dict]:
    events = []
    for alert in _alerts(posts):
        if not alert.get("id"):
            continue
        events.append(_event(brand_id, "ahead", str(alert["id"]), "", str(alert.get("detail") or "")))
    return events


def _push(state: dict, brand_id: str, kind: str, pattern_id: str, before: str, after: str) -> list[dict]:
    return ([_event(brand_id, kind, pattern_id, before, after), *(state.get("memory_log") or [])])[:80]


def _event(brand_id: str, kind: str, pattern_id: str, before: str, after: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "brand_id": brand_id,
        "at": datetime.now(_ZONE).isoformat(),
        "kind": kind,
        "pattern_id": pattern_id,
        "before": redact_memory(str(before or ""))[:500],
        "after": redact_memory(str(after or ""))[:500],
    }


def _public_event(item: dict) -> dict:
    return {
        "id": item.get("id") or "",
        "at": item.get("at") or "",
        "kind": item.get("kind") or "",
        "pattern_id": item.get("pattern_id") or "",
        "before": item.get("before") or "",
        "after": item.get("after") or "",
    }


def _markdown(view: dict) -> str:
    parts = ["# Memory", ""]
    for section in view["sections"]:
        parts.append("## " + section["label"])
        for line in section["lines"]:
            parts.append(f"- {line['title']}: {line['detail']} ({line['standing']})")
        parts.append("")
    parts.append("## Changes")
    if not view["timeline"]:
        parts.append("- No changes yet.")
    for item in view["timeline"]:
        parts.append(f"- {item['kind']} {item['pattern_id']}: {item['before']} -> {item['after']}")
    return "\n".join(parts).strip() + "\n"


def _marks(state: dict, brand_id: str) -> dict:
    raw = (state.get("memory_marks") or {}).get(brand_id) or {}
    if not isinstance(raw, dict):
        return {}
    return {str(key): value for key, value in raw.items() if value in {"pinned", "demoted", "deleted"}}


def _span(posts: list[dict]) -> tuple[str, str, str]:
    days = sorted(str(post.get("published_at") or "")[:10] for post in posts if str(post.get("published_at") or "")[:10])
    if not days:
        return "", "", "No dated posts in this window."
    return days[0], days[-1], f"From {days[0]} to {days[-1]}."


def _is_thin(detail: str) -> bool:
    text = detail.lower()
    if "too close" in text or "clearly ahead" in text or "highest" in text:
        return False
    return True


def _written(value: object) -> str:
    if isinstance(value, list):
        return "; ".join(str(item).strip() for item in value if str(item).strip())[:240]
    return str(value or "").strip()[:240]


def _brand_posts(state: dict, brand_id: str) -> tuple[list[dict], list[dict]]:
    from store import brand_history

    posts, _days = brand_history(state, brand_id)
    pieces = [piece for piece in state.get("pieces") or [] if piece.get("brand_id") == brand_id]
    return list(posts), pieces


def _error(message: str):
    from adapt import DraftError

    return DraftError(message)
