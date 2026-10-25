"""Suggest a post worth a boost. The words are copy. Nothing is spent.

A post qualifies when at least three other posts have an engagement
count, it is at least 3× their average, the gap is at least 3, it has
a format or a pillar, and it meets the minimum the brand set. A missing
count stays out of the average. A missing minimum suggests nothing.

Callers: studio() and POST /brands/{id}/boost. State key boost_minimums
maps a brand id to a whole number. The user said: Keep going.
"""

from __future__ import annotations

from pathlib import Path

from adapt import DraftError
from brands import FORMATS
from learn import MIN_SAMPLE

_PLACEHOLDER = {"unknown", "none", "n/a", "null"}


def suggestions(posts: list[dict], minimum: int | None) -> dict:
    """The list the desk shows. No network."""
    if minimum is None:
        return {
            "minimum": None,
            "note": "Set a minimum engagement count. Nothing is suggested until then.",
            "items": [],
        }
    counted = [post for post in posts if _count(post) is not None]
    items = []
    short = True
    unnamed = False
    under = False
    for post in counted:
        others = [item for item in counted if item.get("id") != post.get("id")]
        if len(others) < MIN_SAMPLE:
            continue
        short = False
        mean = sum(_count(item) or 0 for item in others) / len(others)
        engagements = _count(post) or 0
        if mean <= 0 or engagements < mean * 3 or (engagements - mean) < 3:
            continue
        label = _label(post)
        if not label:
            unnamed = True
            continue
        if engagements < minimum:
            under = True
            continue
        reason = (
            f"{engagements} engagements. The other posts averaged {mean:.1f} (n={len(others)}). "
            f"That is at least 3×, and it clears the minimum of {minimum}."
        )
        preview = str(post.get("preview") or "This post").strip()
        items.append({
            "id": str(post.get("id") or ""),
            "preview": preview[:140],
            "engagements": engagements,
            "others": len(others),
            "mean": round(mean, 1),
            "label": label,
            "reason": reason,
            "copy": f"Worth a boost or an ad. This desk does not spend. {preview} It is a {label}. {reason}",
        })
    items.sort(key=lambda item: item["engagements"], reverse=True)
    return {"minimum": minimum, "note": _note(minimum, items, short, unnamed, under), "items": items[:5]}


def boost_for(state: dict, brand_id: str, posts: list[dict] | None = None) -> dict:
    raw = (state.get("boost_minimums") or {}).get(brand_id)
    minimum = raw if isinstance(raw, int) and not isinstance(raw, bool) else None
    if posts is None:
        from store import brand_history

        posts, _days = brand_history(state, brand_id, None)
    return suggestions(posts or [], minimum)


def save_boost_minimum(state: dict, brand_id: str, spec: dict, path: Path | None = None) -> dict:
    from store import _copy, brand_history, resolve_brand, save

    brand = resolve_brand(state, brand_id)
    raw = spec.get("minimum") if isinstance(spec, dict) else None
    updated = _copy(state)
    saved = dict(updated.get("boost_minimums") or {})
    if raw is None or raw == "":
        saved.pop(brand.id, None)
        minimum = None
    else:
        minimum = _minimum(raw)
        saved[brand.id] = minimum
    updated["boost_minimums"] = saved
    save(updated, path)
    posts, _days = brand_history(updated, brand.id, None)
    return suggestions(posts, minimum)


def _note(minimum: int, items: list[dict], short: bool, unnamed: bool, under: bool) -> str:
    if items:
        return "Copy only. This desk does not boost a post or buy an ad."
    if short:
        return "A comparison waits for three other posts with an engagement count."
    if unnamed and not under:
        return "A post is at least 3× the others, and it has no format or pillar to name."
    if under:
        return f"A post is at least 3× the others, and it is under the minimum of {minimum}."
    return "Nothing is at least 3× the other posts yet."


def _count(post: dict) -> int | None:
    value = post.get("engagements")
    if isinstance(value, bool):
        return None
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if isinstance(value, float) and value == int(value):
        value = int(value)
    if isinstance(value, int) and value >= 0:
        return value
    return None


def _label(post: dict) -> str:
    format_name = str(post.get("format") or "").strip().lower()
    if format_name in FORMATS:
        return format_name
    pillar = str(post.get("pillar") or "").strip()
    if len(pillar) >= 2 and pillar.lower() not in _PLACEHOLDER:
        return pillar
    return ""


def _minimum(value: object) -> int:
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > 100000:
        raise DraftError("The minimum is a whole number from 0 to 100000.")
    return value
