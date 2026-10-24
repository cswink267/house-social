"""Local feedback on suggestions.

Callers: the feedback routes, series_for, hashtags_for, assist, and
memory_for. A later mark replaces the one on screen. Deleting it
restores the earlier mark. Counts stay counts. Nothing is sent.
The user said continue, and this is the feedback item.
"""

from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from pathlib import Path

from adapt import DraftError


_KINDS = {"composer", "ideas", "hashtags", "series"}
_VERDICTS = {"used", "better", "worse", "off-brand", "irrelevant"}
_BLOCK = {"worse", "off-brand", "irrelevant"}
_LABELS = {"used": "Used", "better": "Better", "worse": "Worse", "off-brand": "Off-brand", "irrelevant": "Irrelevant"}


def save_feedback(state: dict, brand_id: str, spec: dict, path: Path | None = None) -> dict:
    from store import resolve_brand, save

    brand = resolve_brand(state, brand_id)
    row = _row(brand.id, spec)
    updated = copy.deepcopy(state)
    mine = [item for item in updated.get("feedback") or [] if item.get("brand_id") == brand.id]
    others = [item for item in updated.get("feedback") or [] if item.get("brand_id") != brand.id]
    updated["feedback"] = others + (mine + [row])[-200:]
    save(updated, path)
    return feedback_for(updated, brand.id)


def correct_feedback(state: dict, brand_id: str, entry_id: str, spec: dict, path: Path | None = None) -> dict:
    found = _owned(state, brand_id, entry_id)
    return save_feedback(
        state,
        brand_id,
        {
            "kind": found["kind"],
            "target": found["target"],
            "verdict": (spec or {}).get("verdict") or found["verdict"],
            "note": (spec or {}).get("note") if spec and "note" in spec else found.get("note") or "",
            "pillar": found.get("pillar") or "",
            "format": found.get("format") or "",
        },
        path,
    )


def delete_feedback(state: dict, brand_id: str, entry_id: str, path: Path | None = None) -> dict:
    from store import resolve_brand, save

    brand = resolve_brand(state, brand_id)
    _owned(state, brand.id, entry_id)
    updated = copy.deepcopy(state)
    updated["feedback"] = [item for item in updated.get("feedback") or [] if item.get("id") != entry_id]
    save(updated, path)
    return feedback_for(updated, brand.id)


def feedback_for(state: dict, brand_id: str) -> dict:
    current = _current(state, brand_id)
    counts = {name: 0 for name in _LABELS}
    entries = []
    for entry in current.values():
        counts[entry["verdict"]] = counts.get(entry["verdict"], 0) + 1
        entries.append(_public(entry))
    lines = [f"{_LABELS[name]}: {counts[name]}" for name in _LABELS if counts[name]]
    return {
        "counts": counts,
        "lines": lines or ["No feedback yet."],
        "entries": entries,
        "blocked": [item["target"] for item in entries if item["verdict"] in _BLOCK],
    }


def apply_series(items: list[dict], state: dict, brand_id: str) -> list[dict]:
    current = _current(state, brand_id, "series")
    blocked = {key for key, entry in current.items() if entry["verdict"] in _BLOCK}
    preferred = [key for key, entry in current.items() if entry["verdict"] == "better"]
    kept = [item for item in items if item.get("id") not in blocked]
    have = {item.get("id") for item in kept}
    for target in preferred:
        if target in blocked or target in have:
            continue
        kept.append({"id": target, "name": target, "outline": "", "detail": "You marked this better. The posts have not shown a gap.", "examples": []})
    return kept


def apply_tags(suggestion: dict, state: dict, brand_id: str) -> dict:
    current = _current(state, brand_id, "hashtags")
    blocked = {key.lower() for key, entry in current.items() if entry["verdict"] in _BLOCK}
    tags = [tag for tag in suggestion.get("tags") or [] if tag.lower() not in blocked]
    extra = False
    for target, entry in current.items():
        if entry["verdict"] != "better" or target.lower() in blocked:
            continue
        if target.lower() not in {tag.lower() for tag in tags}:
            tags.append(target)
            extra = True
    detail = str(suggestion.get("detail") or "")
    if not tags and blocked:
        detail = "The tags that were ahead were marked off. Nothing was left."
    elif extra:
        detail = (detail + " A tag you marked better is included. That is not a gap.").strip()
    return {"tags": tags[:5], "detail": detail}


def apply_texts(texts: list[str], state: dict, brand_id: str, kind: str) -> list[str]:
    current = _current(state, brand_id, kind)
    blocked = {key for key, entry in current.items() if entry["verdict"] in _BLOCK}
    kept = [text for text in texts if text not in blocked]
    for target, entry in current.items():
        if entry["verdict"] == "better" and target not in blocked and target not in kept:
            kept.insert(0, target)
    return kept


def apply_options(options: list[dict], state: dict, brand_id: str) -> list[dict]:
    texts = apply_texts([str(item.get("text") or "") for item in options if item.get("text")], state, brand_id, "composer")
    by_text = {str(item.get("text") or ""): item for item in options}
    return [by_text.get(text) or {"text": text, "feedback": "better"} for text in texts]


def _row(brand_id: str, spec: dict) -> dict:
    if not isinstance(spec, dict):
        raise DraftError("Feedback needs a suggestion and a mark.")
    kind = str(spec.get("kind") or "").strip().lower()
    verdict = str(spec.get("verdict") or "").strip().lower()
    target = str(spec.get("target") or "").strip()[:180]
    if kind not in _KINDS:
        raise DraftError("Feedback is for the composer, ideas, hashtags, or a series.")
    if verdict not in _VERDICTS:
        raise DraftError("The marks are used, better, worse, off-brand, and irrelevant.")
    if not target:
        raise DraftError("Feedback needs the suggestion it is about.")
    return {
        "id": str(uuid.uuid4()),
        "brand_id": brand_id,
        "kind": kind,
        "target": target,
        "verdict": verdict,
        "note": str(spec.get("note") or "").strip()[:240],
        "pillar": str(spec.get("pillar") or "").strip()[:40],
        "format": str(spec.get("format") or "").strip()[:40],
        "at": datetime.now(timezone.utc).isoformat(),
        "user": "chris",
    }


def _current(state: dict, brand_id: str, kind: str = "") -> dict:
    found: dict[str, dict] = {}
    for item in state.get("feedback") or []:
        if item.get("brand_id") != brand_id:
            continue
        if kind and item.get("kind") != kind:
            continue
        found[str(item.get("kind") or "") + ":" + str(item.get("target") or "")] = item
    if kind:
        return {str(item.get("target") or ""): item for item in found.values()}
    return found


def _owned(state: dict, brand_id: str, entry_id: str) -> dict:
    found = next((item for item in state.get("feedback") or [] if item.get("id") == entry_id), None)
    if found is None or found.get("brand_id") != brand_id:
        raise DraftError("That feedback is not on this brand.")
    return found


def _public(entry: dict) -> dict:
    return {
        "id": entry.get("id") or "",
        "kind": entry.get("kind") or "",
        "target": entry.get("target") or "",
        "verdict": entry.get("verdict") or "",
        "note": entry.get("note") or "",
        "pillar": entry.get("pillar") or "",
        "format": entry.get("format") or "",
        "at": entry.get("at") or "",
    }
