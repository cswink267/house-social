"""Aggregated comparisons across brands that opted in.

Callers: studio, the cross-brand routes, and the composer offer.
The view is off until two brands are included. No caption, hook, voice
line, or asset is copied. A gap still needs three posts on both sides.
The user said continue todo, and this is the cross-brand item.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from pathlib import Path

from adapt import DraftError


_IMAGE = {"feed", "quote-image", "carousel", "story"}
_VIDEO = {"reel", "video"}
_TEXT = {"text", "thread"}


def set_cross(state: dict, brand_id: str, enabled: bool, path: Path | None = None) -> dict:
    from store import resolve_brand, save

    brand = resolve_brand(state, brand_id)
    updated = copy.deepcopy(state)
    flags = dict(updated.get("cross_enabled") or {})
    if enabled:
        flags[brand.id] = True
    else:
        flags.pop(brand.id, None)
    updated["cross_enabled"] = flags
    save(updated, path)
    return cross_for(updated, brand.id)


def accept_cross(state: dict, brand_id: str, key: str, path: Path | None = None) -> dict:
    from store import resolve_brand, save

    brand = resolve_brand(state, brand_id)
    if not (state.get("cross_enabled") or {}).get(brand.id):
        raise DraftError("This brand is not included in cross-brand.")
    view = cross_for(state, brand.id)
    found = next((item for item in view["lines"] if item.get("key") == key and item.get("clear")), None)
    if found is None:
        raise DraftError("That cross-brand note is not clear.")
    updated = copy.deepcopy(state)
    kept = [
        item
        for item in updated.get("cross_accepted") or []
        if not (item.get("brand_id") == brand.id and item.get("key") == key)
    ]
    row = {"brand_id": brand.id, "key": key, "detail": found["detail"], "at": datetime.now(timezone.utc).isoformat()}
    own = [item for item in kept if item.get("brand_id") == brand.id]
    others = [item for item in kept if item.get("brand_id") != brand.id]
    updated["cross_accepted"] = others + (own + [row])[-24:]
    save(updated, path)
    return cross_for(updated, brand.id)


def cross_for(state: dict, brand_id: str) -> dict:
    from store import resolve_brand, roster

    brand = resolve_brand(state, brand_id)
    enabled = [item["id"] for item in roster(state) if (state.get("cross_enabled") or {}).get(item["id"])]
    names = [item["name"] for item in roster(state) if item["id"] in set(enabled)]
    rows = _rows(state, enabled)
    contributing = len({row["brand_id"] for row in rows})
    if len(enabled) < 2 or contributing < 2:
        public = [{"key": "", "clear": False, "detail": "Cross-brand stays off until two brands with posts are included."}]
    else:
        public = _lines(rows, contributing)
        if not public:
            public = [{"key": "", "clear": False, "detail": f"No cross-brand gap is clear. Across {contributing} brands. Based on {len(rows)} posts."}]
    accepted_keys = {item.get("key") for item in state.get("cross_accepted") or [] if item.get("brand_id") == brand.id}
    offer = None
    included = bool((state.get("cross_enabled") or {}).get(brand.id))
    if included:
        clear = next((item for item in public if item.get("clear") and item.get("key") not in accepted_keys), None)
        if clear:
            offer = {"key": clear["key"], "detail": clear["detail"], "label": "cross-brand"}
    accepted = [
        {"key": item.get("key") or "", "detail": item.get("detail") or ""}
        for item in state.get("cross_accepted") or []
        if item.get("brand_id") == brand.id and included
    ]
    return {"enabled": included, "brands": names, "posts": len(rows), "lines": public, "offer": offer, "accepted": accepted}


def _rows(state: dict, brand_ids: list[str]) -> list[dict]:
    from store import brand_history

    found = []
    for brand_id in brand_ids:
        posts, _days = brand_history(state, brand_id)
        for post in posts:
            if not post.get("published_at") or post.get("engagements") is None:
                continue
            fmt = str(post.get("format") or "")
            hour = post.get("local_hour")
            found.append(
                {
                    "brand_id": brand_id,
                    "format": fmt,
                    "hour": hour if isinstance(hour, int) else None,
                    "kind": _kind(fmt),
                    "engagements": int(post.get("engagements") or 0),
                }
            )
    return found


def _lines(rows: list[dict], brands: int) -> list[dict]:
    found = []
    posts = len(rows)
    for dimension, key, title in (("format", "format", "Format"), ("hour", "hour", "Hour"), ("kind", "kind", "Content")):
        line = _gap(dimension, title, _groups(rows, key), brands, posts)
        if line:
            found.append(line)
    return found


def _groups(rows: list[dict], key: str) -> list[dict]:
    buckets: dict[str, list[int]] = {}
    for row in rows:
        label = _label(key, row.get(key))
        if not label:
            continue
        buckets.setdefault(label, []).append(int(row["engagements"]))
    ready = []
    for label, values in buckets.items():
        if len(values) < 3:
            continue
        ready.append({"label": label, "n": len(values), "mean": round(sum(values) / len(values), 1)})
    ready.sort(key=lambda item: item["mean"], reverse=True)
    return ready


def _gap(dimension: str, title: str, groups: list[dict], brands: int, posts: int) -> dict | None:
    if len(groups) < 2:
        return None
    best, second = groups[0], groups[1]
    if not (best["mean"] >= second["mean"] * 1.5 and best["mean"] - second["mean"] >= 3):
        return None
    return {
        "key": f"{dimension}:{best['label']}:{second['label']}",
        "clear": True,
        "detail": (
            f"{title}: {best['label']} averaged {best['mean']} engagements (n={best['n']}). "
            f"{second['label']} averaged {second['mean']} (n={second['n']}). "
            f"Across {brands} brands. Based on {posts} posts. This is cross-brand."
        ),
    }


def _kind(fmt: str) -> str:
    if fmt in _IMAGE:
        return "image"
    if fmt in _VIDEO:
        return "video"
    if fmt in _TEXT:
        return "text"
    return ""


def _label(key: str, value) -> str:
    if key == "hour":
        if not isinstance(value, int) or not 0 <= value <= 23:
            return ""
        return f"{value:02d}:00"
    text = str(value or "")
    if text in {"", "unknown"}:
        return ""
    return text
