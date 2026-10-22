"""Saved hashtag sets and the tags posts actually used.

A trend note is something a person wrote down. It is not a live chart.
Format numbers come from this brand's own posts.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from adapt import DraftError
from learn import MIN_SAMPLE, format_table
from store import _find, _label, resolve_brand, save, update_piece


_TAG = re.compile(r"(?<!\w)#([A-Za-z0-9_]+)")
_KINDS = ("topic", "sound", "format")
_SET_LIMIT = 5


def hashtags_for(state: dict, brand_id: str, posts: list[dict] | None = None) -> dict:
    brand = resolve_brand(state, brand_id)
    owned = [item for item in posts or [] if _belongs(item, brand.id, state)]
    sets = [_set_public(item) for item in state.get("hashtag_sets") or [] if item.get("brand_id") == brand.id]
    trends = [_trend_public(item) for item in state.get("trends") or [] if item.get("brand_id") == brand.id]
    pieces = [piece for piece in state.get("pieces") or [] if piece.get("brand_id") == brand.id]
    return {
        "sets": sets,
        "tags": _tag_rows(owned, pieces),
        "formats": _formats(owned),
        "trends": trends,
        "kinds": list(_KINDS),
    }


def save_set(state: dict, brand_id: str, spec: dict, path: Path | None = None) -> dict:
    brand = resolve_brand(state, brand_id)
    if not isinstance(spec, dict):
        raise DraftError("The set needs a name and tags.")
    name = _label(spec.get("name") or "", 40)
    tags = _clean_tags(spec.get("tags") or [])
    if not name or not tags:
        raise DraftError("The set needs a name and tags.")
    if any(
        str(item.get("name") or "").lower() == name.lower()
        for item in state.get("hashtag_sets") or []
        if item.get("brand_id") == brand.id
    ):
        raise DraftError("This brand already has that set.")
    row = {
        "id": str(uuid.uuid4()),
        "brand_id": brand.id,
        "name": name,
        "tags": tags,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    save({**state, "hashtag_sets": [row, *(state.get("hashtag_sets") or [])]}, path)
    return _set_public(row)


def save_trend(state: dict, brand_id: str, spec: dict, path: Path | None = None) -> dict:
    brand = resolve_brand(state, brand_id)
    if not isinstance(spec, dict):
        raise DraftError("The note needs a name.")
    kind = str(spec.get("kind") or "").strip().lower()
    if kind not in _KINDS:
        raise DraftError("A trend note is a topic, a sound, or a format.")
    name = _label(spec.get("name") or "", 80)
    if not name:
        raise DraftError("The note needs a name.")
    row = {
        "id": str(uuid.uuid4()),
        "brand_id": brand.id,
        "kind": kind,
        "name": name,
        "note": _label(spec.get("note") or "", 240),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    save({**state, "trends": [row, *(state.get("trends") or [])]}, path)
    return _trend_public(row)


def apply_set(state: dict, set_id: str, piece_id: str, path: Path | None = None) -> dict:
    row = next((item for item in state.get("hashtag_sets") or [] if item.get("id") == set_id), None)
    if row is None:
        raise DraftError("That set is not on this brand.")
    _index, piece = _find(state, piece_id)
    if piece.get("brand_id") != row.get("brand_id"):
        raise DraftError("That piece belongs to another brand.")
    update_piece(state, piece_id, variants={"instagram": {"hashtags": list(row.get("tags") or [])}}, path=path)
    return {"piece_id": piece_id, "tags": list(row.get("tags") or [])}


def _tag_rows(posts: list[dict], pieces: list[dict]) -> list[dict]:
    tagged = [(post, _post_tags(post, pieces)) for post in posts]
    names: list[str] = []
    for _post, tags in tagged:
        for tag in tags:
            if tag.lower() not in {item.lower() for item in names}:
                names.append(tag)
    rows = []
    for tag in names:
        yes = [post for post, tags in tagged if tag.lower() in {item.lower() for item in tags}]
        no = [post for post, tags in tagged if tag.lower() not in {item.lower() for item in tags}]
        mean_yes = _mean(yes)
        mean_no = _mean(no)
        clear = (
            len(yes) >= MIN_SAMPLE
            and len(no) >= MIN_SAMPLE
            and abs(mean_yes - mean_no) >= 3
            and max(mean_yes, mean_no) >= min(mean_yes, mean_no) * 1.5
        )
        if len(yes) < MIN_SAMPLE or len(no) < MIN_SAMPLE:
            detail = f"#{tag} is on {len(yes)} posts. A comparison waits for {MIN_SAMPLE} with it and {MIN_SAMPLE} without it."
        elif not clear:
            detail = f"#{tag} is too close to call. {mean_yes:.1f} (n={len(yes)}) against {mean_no:.1f} without it (n={len(no)})."
        elif mean_yes > mean_no:
            detail = f"#{tag} averaged {mean_yes:.1f} engagements (n={len(yes)}). Without it, {mean_no:.1f} (n={len(no)})."
        else:
            detail = f"#{tag} averaged less: {mean_yes:.1f} (n={len(yes)}) against {mean_no:.1f} without it (n={len(no)})."
        rows.append({"tag": tag, "n": len(yes), "mean": round(mean_yes, 1), "clear": clear, "detail": detail})
    rows.sort(key=lambda item: (not item["clear"], -item["mean"], item["tag"].lower()))
    return rows


def _formats(posts: list[dict]) -> dict:
    known = [post for post in posts if post.get("format") not in (None, "", "unknown")]
    rows = format_table(known)
    ready = [row for row in rows if row["n"] >= MIN_SAMPLE]
    clear = False
    detail = "No format in these posts has enough uses to compare."
    if len(ready) >= 2:
        best = max(ready, key=lambda row: row["mean"])
        others = [row for row in ready if row["id"] != best["id"]]
        rest = sum(row["mean"] for row in others) / len(others)
        clear = best["mean"] >= rest * 1.5 and best["mean"] - rest >= 3
        if clear:
            detail = f"{best['label']} leads at {best['mean']} (n={best['n']}). The other measured formats sit near {round(rest, 1)}."
        else:
            detail = f"No format is clearly ahead. {best['label']} is highest at {best['mean']} (n={best['n']})."
    elif len(ready) == 1:
        detail = f"Only {ready[0]['label']} has {ready[0]['n']} posts. That is not a comparison."
    return {"rows": rows, "clear": clear, "detail": detail}


def _post_tags(post: dict, pieces: list[dict]) -> list[str]:
    found = _clean_tags(post.get("hashtags") or [])
    found.extend(_TAG.findall(str(post.get("preview") or "")))
    piece_id = str(post.get("piece_id") or "")
    if piece_id:
        piece = next((item for item in pieces if item.get("id") == piece_id), None)
        instagram = ((piece or {}).get("variants") or {}).get("instagram") or {}
        found.extend(_clean_tags(instagram.get("hashtags") or []))
    return _clean_tags(found)


def _clean_tags(values) -> list[str]:
    if isinstance(values, str):
        values = values.replace("#", " ").split(",")
        if len(values) == 1:
            values = values[0].split()
    rows = []
    for value in values or []:
        text = str(value or "").strip().lstrip("#")
        if text and text.lower() not in {row.lower() for row in rows}:
            rows.append(text[:40])
    return rows[:_SET_LIMIT]


def _belongs(post: dict, brand_id: str, state: dict) -> bool:
    posted_brand = post.get("brand_id")
    if posted_brand:
        return posted_brand == brand_id
    piece_id = str(post.get("piece_id") or "")
    if not piece_id:
        return True
    piece = next((item for item in state.get("pieces") or [] if item.get("id") == piece_id), None)
    return bool(piece and piece.get("brand_id") == brand_id)


def _mean(posts: list[dict]) -> float:
    if not posts:
        return 0.0
    return sum(int(post.get("engagements") or 0) for post in posts) / len(posts)


def _set_public(row: dict) -> dict:
    return {"id": row.get("id"), "name": row.get("name") or "", "tags": list(row.get("tags") or [])}


def _trend_public(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "kind": row.get("kind") or "topic",
        "name": row.get("name") or "",
        "note": row.get("note") or "",
        "rising": False,
    }
