"""Append a real note to TODO.md. Off until Chris turns it on.

Callers: the todo-notes route and the Brief check. A note is appended,
never used to delete an older item. Two a day. Nothing is sent.
The user said continue, and that this trust is why the notes matter.
"""

from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from adapt import DraftError
from memory import redact_memory


_ZONE = ZoneInfo("America/New_York")
_LIMIT = 2


def notes_view(state: dict, brand_id: str) -> dict:
    book = _book(state)
    brand_on = bool((book.get("brands") or {}).get(brand_id))
    global_on = bool(book.get("global"))
    return {
        "global": global_on,
        "brand": brand_on,
        "on": global_on or brand_on,
        "limit": int(book.get("limit") or _LIMIT),
        "today": _today_count(state),
        "held": len([item for item in state.get("todo_held") or [] if _day(item.get("at")) == _today()]),
    }


def set_notes(state: dict, brand_id: str, enabled: bool, scope: str, path: Path | None = None) -> dict:
    from store import resolve_brand, save

    brand = resolve_brand(state, brand_id)
    which = str(scope or "brand").strip().lower()
    if which not in {"brand", "global"}:
        raise DraftError("The todo note switch is for this brand, or for every brand.")
    updated = copy.deepcopy(state)
    book = _book(updated)
    if which == "global":
        book["global"] = bool(enabled)
    else:
        brands = dict(book.get("brands") or {})
        if enabled:
            brands[brand.id] = True
        else:
            brands.pop(brand.id, None)
        book["brands"] = brands
    updated["todo_notes"] = book
    save(updated, path)
    return notes_view(updated, brand.id)


def append_note(state: dict, brand_id: str, spec: dict, path: Path | None = None, todo_file: Path | None = None) -> dict:
    from store import resolve_brand, save

    brand = resolve_brand(state, brand_id)
    view = notes_view(state, brand.id)
    if not view["on"]:
        raise DraftError("Todo notes are off.")
    if not isinstance(spec, dict):
        raise DraftError("A note needs a heading.")
    heading = redact_memory(str(spec.get("heading") or "").strip())[:80]
    happened = redact_memory(str(spec.get("happened") or "").strip())[:500]
    why = redact_memory(str(spec.get("why") or "").strip())[:320]
    nxt = redact_memory(str(spec.get("next") or "").strip())[:320]
    desk = redact_memory(str(spec.get("desk") or "").strip())[:40]
    if not heading or not happened or not why or not nxt:
        raise DraftError("A note needs what happened, why it matters, and a next step.")
    target = todo_file or _todo_file()
    text = target.read_text(encoding="utf-8") if target.exists() else ""
    if heading.lower() in text.lower():
        return {"added": False, "reason": "That note is already on the list.", **view}
    if view["today"] >= view["limit"]:
        updated = copy.deepcopy(state)
        updated["todo_held"] = ([{"at": _now(), "brand_id": brand.id, "heading": heading}, *(updated.get("todo_held") or [])])[:40]
        save(updated, path)
        held = notes_view(updated, brand.id)
        return {"added": False, "reason": "The day's notes are held. Nothing new was written.", **held}
    block = (
        f"### {heading}\n\n"
        f"{_today()}. Desk: {desk or 'house'}.\n\n"
        f"What happened: {happened}\n\n"
        f"Why: {why}\n\n"
        f"Next: {nxt}\n"
    )
    if any(line.strip() == "## Suggested improvements" for line in text.splitlines()):
        updated_text = text.rstrip() + "\n\n" + block
    else:
        updated_text = text.rstrip() + "\n\n## Suggested improvements\n\n" + block
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(updated_text if updated_text.endswith("\n") else updated_text + "\n", encoding="utf-8")
    updated = copy.deepcopy(state)
    updated["todo_notes_log"] = ([{"at": _now(), "brand_id": brand.id, "heading": heading}, *(updated.get("todo_notes_log") or [])])[:80]
    save(updated, path)
    return {"added": True, "reason": "Added.", "heading": heading, **notes_view(updated, brand.id)}


def _book(state: dict) -> dict:
    raw = state.get("todo_notes") if isinstance(state.get("todo_notes"), dict) else {}
    limit = raw.get("limit") or _LIMIT
    return {"global": bool(raw.get("global")), "brands": dict(raw.get("brands") or {}), "limit": int(limit)}


def _today_count(state: dict) -> int:
    day = _today()
    return len([item for item in state.get("todo_notes_log") or [] if _day(item.get("at")) == day])


def _today() -> str:
    return datetime.now(_ZONE).date().isoformat()


def _now() -> str:
    return datetime.now(_ZONE).isoformat()


def _day(value: object) -> str:
    return str(value or "")[:10]


def _todo_file() -> Path:
    return Path(__file__).resolve().parent / "TODO.md"
