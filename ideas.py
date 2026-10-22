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


SOURCES = ("spark", "competitor", "trend", "question", "comment")
PRIORITIES = ("low", "normal", "high")
_RANK = {"high": 0, "normal": 1, "low": 2}
_LABELS = {
    "spark": "Spark",
    "competitor": "Competitor",
    "trend": "Trend",
    "question": "Question",
    "comment": "Comment",
}


def ideas_for(state: dict, brand_id: str, posts: list[dict] | None = None) -> dict:
    from analytics_desk import _alerts, _ahead, read_draft

    brand = resolve_brand(state, brand_id)
    history = list(posts or [])
    ahead = {item.get("id") for item in _alerts(history)}
    rows = []
    for item in state.get("ideas") or []:
        if item.get("brand_id") != brand.id:
            continue
        public = _public(item)
        reading = read_draft(public["text"], history)
        public["pattern"] = _pattern_label(reading)
        public["pattern_lines"] = reading.get("lines") or []
        linked = [post for post in history if post.get("piece_id") and post.get("piece_id") == item.get("piece_id")]
        public["performed"] = any(post.get("id") in ahead for post in linked)
        public["engagements"] = max((int(post.get("engagements") or 0) for post in linked), default=None) if linked else None
        rows.append(public)
    rows.sort(key=lambda item: (_RANK.get(item["priority"], 1), item.get("created_at") or ""))
    archive = [item for item in rows if item.get("performed")]
    return {
        "ideas": rows,
        "sources": list(SOURCES),
        "priorities": list(PRIORITIES),
        "archive": archive,
        "lesson": _source_lesson(rows, history, _ahead),
        "shapes": _shapes(history, ahead, rows),
        "comments": _comments(state, brand.id, rows),
    }


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
    piece = create_piece(
        state,
        idea["brand_id"],
        idea["text"],
        path=path,
        pillar=str(idea.get("pillar") or ""),
    )
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
        raise DraftError("Source is spark, competitor, trend, question, or comment.")
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
        "pillar": _label(spec.get("pillar") or "", 40),
        "inbox_id": _label(spec.get("inbox_id") or "", 80),
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
        "pillar": idea.get("pillar") or "",
        "status": idea.get("status") or "open",
        "piece_id": idea.get("piece_id") or "",
        "created_at": idea.get("created_at") or "",
    }


def keep_shape(state: dict, brand_id: str, post_id: str, path: Path | None = None) -> dict:
    from analytics_desk import _alerts
    from store import brand_history

    resolve_brand(state, brand_id)
    posts, _days = brand_history(state, brand_id)
    ahead = {item.get("id") for item in _alerts(posts)}
    post = next((item for item in posts if str(item.get("id") or "") == post_id), None)
    if post is None or post.get("id") not in ahead:
        raise DraftError("That post is not ahead of the others.")
    preview = str(post.get("preview") or "").strip()
    if not preview:
        raise DraftError("That post has no words to keep.")
    return save_idea(
        state,
        brand_id,
        {
            "text": preview,
            "source": "spark",
            "priority": "normal",
            "note": f"Kept from a post that was ahead. {int(post.get('engagements') or 0)} engagements.",
        },
        path,
    )


def idea_brief(pillars: list[dict], posts: list[dict], trends: list[dict], lessons: list[dict] | None = None) -> str:
    from analytics_desk import _alerts

    lines = ["Pillars: " + ", ".join(item.get("name") or "" for item in pillars if item.get("name")) or "No pillars saved."]
    ahead = _alerts(posts)
    if ahead:
        lines.append("Posts that are at least 3× the others:")
        for item in ahead[:3]:
            lines.append(f"- {item.get('preview') or 'Untitled'} ({item.get('engagements')} engagements)")
    else:
        lines.append("No post is at least 3× the others.")
    notes = [item for item in trends if str(item.get("name") or "").strip()]
    if notes:
        lines.append("Trend notes saved by hand:")
        for item in notes[:5]:
            lines.append(f"- {item.get('name')}: {item.get('note') or ''}".strip())
    else:
        lines.append("No trend note is saved.")
    winning = [item for item in lessons or [] if item.get("ahead") and item.get("approach")]
    if winning:
        lines.append("Campaign kinds that are ahead:")
        for item in winning:
            lines.append(f"- {item.get('detail')} {item.get('approach')}".strip())
    else:
        lines.append("No campaign kind is clearly ahead.")
    lines.append("Do not invent a metric or a result.")
    return "\n".join(lines)


def _pattern_label(reading: dict) -> str:
    if reading.get("lines"):
        return "Matches a pattern that is ahead."
    if reading.get("misses"):
        return "Misses a pattern that is ahead."
    return "No pattern to score this yet."


def _source_lesson(ideas: list[dict], posts: list[dict], ahead) -> dict:
    grouped: dict[str, list[dict]] = {}
    for idea in ideas:
        if idea.get("status") != "drafted" or not idea.get("piece_id"):
            continue
        linked = [post for post in posts if post.get("piece_id") == idea.get("piece_id")]
        if linked:
            grouped.setdefault(idea.get("source") or "spark", []).extend(linked)
    ready = [(name, rows) for name, rows in grouped.items() if len(rows) >= 3]
    if len(ready) < 1:
        return {"clear": False, "detail": "Not enough drafted ideas have results to compare sources."}
    best = None
    for name, rows in ready:
        others = [post for source, group in grouped.items() if source != name for post in group]
        won = ahead(rows, others)
        if not won:
            continue
        mean_yes, mean_no = won
        if best is None or mean_yes - mean_no > best[0]:
            best = (mean_yes - mean_no, name, len(rows), len(others), mean_yes, mean_no)
    if not best:
        return {"clear": False, "detail": "Idea sources are too close to call, or one side still has fewer than three results."}
    _gap, name, n_yes, n_no, mean_yes, mean_no = best
    return {
        "clear": True,
        "detail": f"{name} ideas averaged {mean_yes:.1f} engagements (n={n_yes}). The other sources averaged {mean_no:.1f} (n={n_no}).",
    }


def _shapes(posts: list[dict], ahead: set, ideas: list[dict]) -> list[dict]:
    kept = {item.get("text", "").strip().lower() for item in ideas}
    rows = []
    for post in posts:
        if post.get("id") not in ahead:
            continue
        preview = str(post.get("preview") or "").strip()
        if not preview or preview.lower() in kept:
            continue
        rows.append({"id": post.get("id") or "", "preview": preview[:140], "engagements": int(post.get("engagements") or 0)})
    rows.sort(key=lambda item: item["engagements"], reverse=True)
    return rows[:3]


def _comments(state: dict, brand_id: str, ideas: list[dict]) -> list[dict]:
    taken = {item.get("inbox_id") for item in state.get("ideas") or [] if item.get("inbox_id")}
    rows = []
    for item in state.get("inbox") or []:
        if item.get("brand_id") != brand_id or item.get("dismissed"):
            continue
        if item.get("id") in taken:
            continue
        text = str(item.get("text") or "").strip()
        if item.get("kind") != "comment" and "?" not in text:
            continue
        if not text:
            continue
        rows.append({"id": item.get("id") or "", "text": text[:240], "author": item.get("author") or ""})
        if len(rows) == 6:
            break
    return rows


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
