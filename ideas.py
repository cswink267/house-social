"""An idea board for one brand.

Sparks, competitor notes, trends, and questions stay here until
someone turns one into a draft. The board does not fetch the web.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from adapt import DraftError
from store import _label, create_piece, load, resolve_brand, save


SOURCES = ("spark", "competitor", "trend", "question")
PRIORITIES = ("low", "normal", "high")
_RANK = {"high": 0, "normal": 1, "low": 2}
_LABELS = {
    "spark": "Spark",
    "competitor": "Competitor",
    "trend": "Trend",
    "question": "Question",
}


def ideas_for(state: dict, brand_id: str) -> dict:
    brand = resolve_brand(state, brand_id)
    rows = [_public(item) for item in state.get("ideas") or [] if item.get("brand_id") == brand.id]
    rows.sort(key=lambda item: (_RANK.get(item["priority"], 1), item.get("created_at") or ""))
    return {"ideas": rows, "sources": list(SOURCES), "priorities": list(PRIORITIES)}


def save_idea(state: dict, brand_id: str, spec: dict, path: Path | None = None) -> dict:
    brand = resolve_brand(state, brand_id)
    idea = _new(brand.id, spec)
    updated = {**state, "ideas": [idea, *(state.get("ideas") or [])]}
    save(updated, path)
    return _public(idea)


def revise_idea(state: dict, idea_id: str, spec: dict, path: Path | None = None) -> dict:
    if not isinstance(spec, dict):
        raise DraftError("The idea needs fields.")
    index, current = _idea(state, idea_id)
    if current.get("status") == "drafted":
        raise DraftError("That idea is already a draft.")
    revised = _new(current["brand_id"], {**current, **spec}, idea_id=current["id"])
    revised["created_at"] = current.get("created_at")
    revised["status"] = "open"
    revised["piece_id"] = ""
    ideas = list(state.get("ideas") or [])
    ideas[index] = revised
    save({**state, "ideas": ideas}, path)
    return _public(revised)


def draft_idea(state: dict, idea_id: str, path: Path | None = None) -> dict:
    _index, idea = _idea(state, idea_id)
    if idea.get("status") == "drafted" and idea.get("piece_id"):
        return {"created": False, "piece_id": idea["piece_id"], "idea": _public(idea)}
    piece = create_piece(state, idea["brand_id"], idea["text"], path=path)
    current = load(path) if path else load()
    ideas = []
    for item in current.get("ideas") or []:
        if item.get("id") == idea["id"]:
            ideas.append({**item, "status": "drafted", "piece_id": piece["id"]})
        else:
            ideas.append(item)
    save({**current, "ideas": ideas}, path)
    drafted = next(item for item in ideas if item.get("id") == idea["id"])
    return {"created": True, "piece_id": piece["id"], "idea": _public(drafted)}


def _new(brand_id: str, spec: dict, idea_id: str = "") -> dict:
    if not isinstance(spec, dict):
        raise DraftError("The idea needs words.")
    text = str(spec.get("text") or "").strip()
    if not text:
        raise DraftError("The idea needs words.")
    if len(text) > 2000:
        raise DraftError("That idea is too long.")
    source = str(spec.get("source") or "spark").strip().lower()
    if source not in SOURCES:
        raise DraftError("Source is spark, competitor, trend, or question.")
    priority = str(spec.get("priority") or "normal").strip().lower()
    if priority not in PRIORITIES:
        raise DraftError("Priority is low, normal, or high.")
    return {
        "id": idea_id or str(uuid.uuid4()),
        "brand_id": brand_id,
        "text": text,
        "source": source,
        "priority": priority,
        "tags": _tags(spec.get("tags") or []),
        "note": _label(spec.get("note") or "", 240),
        "link": _link(spec.get("link") or ""),
        "status": "open",
        "piece_id": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _public(idea: dict) -> dict:
    return {
        "id": idea.get("id"),
        "brand_id": idea.get("brand_id"),
        "text": idea.get("text") or "",
        "source": idea.get("source") or "spark",
        "source_label": _LABELS.get(idea.get("source") or "", "Spark"),
        "priority": idea.get("priority") or "normal",
        "tags": list(idea.get("tags") or []),
        "note": idea.get("note") or "",
        "link": idea.get("link") or "",
        "status": idea.get("status") or "open",
        "piece_id": idea.get("piece_id") or "",
        "created_at": idea.get("created_at") or "",
    }


def _idea(state: dict, idea_id: str) -> tuple[int, dict]:
    for index, idea in enumerate(state.get("ideas") or []):
        if idea.get("id") == idea_id:
            return index, idea
    raise DraftError("That idea is not on this board.")


def _tags(values) -> list[str]:
    if isinstance(values, str):
        values = values.split(",")
    rows = []
    for value in values or []:
        text = str(value or "").strip().lstrip("#")
        if text and text.lower() not in {row.lower() for row in rows}:
            rows.append(text[:24])
    return rows[:8]


def _link(value) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) > 300 or not text.startswith(("http://", "https://")):
        raise DraftError("A link is an http or https address.")
    return text
