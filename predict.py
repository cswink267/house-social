"""A wide, low, medium, or high range for one draft.

Callers: the draft-read route, record_stat, and memory_for. The range
uses only patterns that already clear the three-post gap. A thin window
stays wide. Nothing here calls out. The user said continue, and this is
the prediction item.
"""

from __future__ import annotations

import copy
import re
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from analytics_desk import _DRAFT_STOP, _context, _has_cta, _length_name, _short_hook


_ZONE = ZoneInfo("America/New_York")
_HELD = {"deleted", "demoted"}
_EXPECTED = {"high": "higher", "low": "lower", "medium": "about"}
_CHANGES = {
    "hook": "Shorten the first sentence.",
    "question": "Ask a question.",
    "cta": "Ask a question or add a link.",
    "length": "Match the length that is ahead.",
    "format": "Use the format that is ahead.",
    "pillar": "Use the pillar that is ahead.",
}


def predict_range(
    text: str,
    posts: list[dict],
    *,
    fmt: str = "",
    pillar: str = "",
    marks: dict | None = None,
    hidden: bool = False,
) -> dict:
    window = [post for post in posts if post.get("published_at") and post.get("engagements") is not None]
    count = len(window)
    similar = _closest(text, window)
    if hidden:
        return _pack("hidden", "The range is hidden for this brand.", [], similar, "", count, True)
    body = str(text or "").strip()
    if not body:
        return _pack("wide", "Write a draft before asking for a range.", [], similar, "", count, False)
    if count < 3:
        return _pack("wide", f"The range is wide. Based on {count} posts.", [], similar, "", count, False)
    context = _context(window, [])
    factors = _factors(body, context, fmt, pillar, marks or {})
    clear = [item for item in factors if item["clear"]]
    if not clear:
        return _pack(
            "wide",
            f"No pattern is clear enough to narrow the range. Based on {count} posts.",
            [],
            similar,
            "",
            count,
            False,
        )
    matched = [item for item in clear if item["matched"]]
    missed = [item for item in clear if not item["matched"]]
    if matched and not missed:
        band = "high"
        detail = f"High. The draft matches the patterns that are ahead. Based on {count} posts."
    elif missed and not matched:
        band = "low"
        detail = f"Low. The draft misses the patterns that are ahead. Based on {count} posts."
    else:
        band = "medium"
        detail = f"Medium. The draft matches some of the patterns that are ahead and misses others. Based on {count} posts."
    change = _CHANGES.get(missed[0]["id"], "") if missed else ""
    if missed and missed[0]["id"] == "format" and context.get("format_name"):
        change = f"Use the {context['format_name']} format."
    if missed and missed[0]["id"] == "pillar" and context.get("pillar_name"):
        change = f"Use the {context['pillar_name']} pillar."
    return _pack(band, detail, clear, similar, change, count, False)


def remember_prediction(state: dict, brand_id: str, piece_id: str, found: dict, path: Path | None = None) -> dict:
    from store import resolve_brand, save

    resolve_brand(state, brand_id)
    name = str(piece_id or "").strip()
    if not name or found.get("hidden") or found.get("band") in {"", "hidden"}:
        return state
    updated = copy.deepcopy(state)
    others = [item for item in updated.get("predictions") or [] if not (item.get("brand_id") == brand_id and item.get("piece_id") == name)]
    mine = [item for item in updated.get("predictions") or [] if item.get("brand_id") == brand_id and item.get("piece_id") == name]
    previous = mine[0] if mine else {}
    row = {
        "id": previous.get("id") or str(uuid.uuid4()),
        "brand_id": brand_id,
        "piece_id": name,
        "at": datetime.now(_ZONE).isoformat(),
        "band": found.get("band") or "wide",
        "preview": str(found.get("detail") or "")[:180],
        "graded": previous.get("graded") if previous.get("band") == found.get("band") else None,
    }
    updated["predictions"] = ([row, *others])[:80]
    updated = apply_grades(updated, brand_id)
    save(updated, path)
    return updated


def set_prediction_hidden(state: dict, brand_id: str, hidden: bool, scope: str, path: Path | None = None) -> dict:
    from store import resolve_brand, save

    resolve_brand(state, brand_id)
    which = str(scope or "brand").strip().lower()
    if which not in {"brand", "all"}:
        raise _error("Hide the range for this brand, or for every brand.")
    updated = copy.deepcopy(state)
    book = dict(updated.get("prediction_hidden") or {})
    key = "*" if which == "all" else brand_id
    if hidden:
        book[key] = True
    else:
        book.pop(key, None)
    updated["prediction_hidden"] = book
    save(updated, path)
    return {"hidden": is_hidden(updated, brand_id), "scope": which}


def is_hidden(state: dict, brand_id: str) -> bool:
    book = state.get("prediction_hidden") or {}
    return bool(book.get("*") or book.get(brand_id))


def apply_grades(state: dict, brand_id: str) -> dict:
    from store import brand_history

    posts, _days = brand_history(state, brand_id)
    rows = []
    changed = False
    for item in state.get("predictions") or []:
        if item.get("brand_id") != brand_id or item.get("graded"):
            rows.append(item)
            continue
        graded = _grade(item, state, posts)
        if graded is None:
            rows.append(item)
            continue
        changed = True
        rows.append({**item, "graded": graded})
    if not changed:
        return state
    return {**state, "predictions": rows}


def accuracy_for(state: dict, brand_id: str) -> list[dict]:
    rows = [item for item in state.get("predictions") or [] if item.get("brand_id") == brand_id]
    found = []
    waiting = 0
    for item in rows:
        graded = item.get("graded") if isinstance(item.get("graded"), dict) else None
        if not graded:
            waiting += 1
            continue
        found.append({"id": item.get("id") or "", "correct": graded.get("correct"), "detail": graded.get("detail") or ""})
    if waiting:
        found.append({"id": "waiting", "correct": None, "detail": f"{waiting} drafts are still waiting on real numbers."})
    return found[:12]


def _grade(item: dict, state: dict, posts: list[dict]) -> dict | None:
    band = str(item.get("band") or "")
    piece_id = str(item.get("piece_id") or "")
    engagements = _engagements(state, str(item.get("brand_id") or ""), piece_id)
    if engagements is None:
        return None
    if band == "wide":
        return {"correct": None, "direction": "", "expected": "", "engagements": engagements, "mean": None, "n": 0, "detail": "The range was wide, so this post is not graded."}
    others = [post for post in posts if post.get("piece_id") != piece_id and post.get("engagements") is not None]
    if len(others) < 3:
        return {"correct": None, "direction": "", "expected": "", "engagements": engagements, "mean": None, "n": len(others), "detail": "This post has numbers, and the rest of the window is still thin, so it is not graded."}
    mean = round(sum(int(post.get("engagements") or 0) for post in others) / len(others), 1)
    direction = _direction(engagements, mean)
    expected = _EXPECTED.get(band, "")
    if not expected:
        return None
    correct = direction == expected
    word = "matched" if correct else "did not match"
    detail = (
        f"The range said {band}, which expects {expected} than the others. "
        f"This post reached {engagements}. The other posts averaged {mean} (n={len(others)}). "
        f"That is {direction}. The direction {word}."
    )
    return {
        "correct": correct,
        "direction": direction,
        "expected": expected,
        "engagements": engagements,
        "mean": mean,
        "n": len(others),
        "detail": detail.replace("about than", "about the same as"),
    }


def _engagements(state: dict, brand_id: str, piece_id: str) -> int | None:
    if not piece_id:
        return None
    for stat in state.get("stats") or []:
        if stat.get("brand_id") != brand_id or stat.get("piece_id") != piece_id:
            continue
        metrics = stat.get("metrics") if isinstance(stat.get("metrics"), dict) else {}
        if "engagements" in metrics and metrics.get("engagements") is not None:
            return int(metrics["engagements"])
    return None


def _direction(engagements: int, mean: float) -> str:
    if mean <= 0:
        return "about"
    if engagements >= mean * 1.5 and engagements - mean >= 3:
        return "higher"
    if mean >= engagements * 1.5 and mean - engagements >= 3:
        return "lower"
    return "about"


def _factors(body: str, context: dict, fmt: str, pillar: str, marks: dict) -> list[dict]:
    preview = {"preview": body}
    rows = [
        ("hook", "Hook", _open(context, marks, "hook", "hook_clear"), _short_hook(preview)),
        ("question", "Question", _open(context, marks, "question", "question_clear"), "?" in body),
        ("cta", "Ask or link", _open(context, marks, "cta", "cta_clear"), _has_cta(preview)),
        ("length", "Length", _open(context, marks, "length", "length_clear"), bool(context.get("length_name")) and _length_name(preview) == context.get("length_name")),
    ]
    if fmt:
        rows.append(("format", "Format", _open(context, marks, "format", "format_clear"), fmt == context.get("format_name")))
    if pillar:
        rows.append(("pillar", "Pillar", _open(context, marks, "pillar", "pillar_clear"), pillar == context.get("pillar_name")))
    return [{"id": key, "title": title, "clear": clear, "matched": bool(clear and holds)} for key, title, clear, holds in rows]


def _open(context: dict, marks: dict, pattern_id: str, flag: str) -> bool:
    if marks.get(pattern_id) in _HELD:
        return False
    return bool(context.get(flag))


def _closest(text: str, posts: list[dict]) -> list[dict]:
    words = set(re.findall(r"[a-z0-9']{4,}", str(text or "").lower())) - _DRAFT_STOP
    rows = []
    for post in posts:
        preview = str(post.get("preview") or "").strip()
        if not preview or post.get("engagements") is None:
            continue
        if preview.lower() == str(text or "").strip().lower():
            continue
        shared = words & set(re.findall(r"[a-z0-9']{4,}", preview.lower()))
        if not shared:
            continue
        rows.append({"id": post.get("id") or "", "preview": preview[:140], "engagements": int(post.get("engagements") or 0), "shared": len(shared)})
    rows.sort(key=lambda item: (item["shared"], item["engagements"]), reverse=True)
    return [{"id": item["id"], "preview": item["preview"], "engagements": item["engagements"]} for item in rows[:3]]


def _pack(band: str, detail: str, factors: list[dict], similar: list[dict], change: str, count: int, hidden: bool) -> dict:
    note = detail
    if not hidden and count and len(similar) < 3:
        extra = "Fewer than three past posts share words with this draft." if similar else "No saved post shares words with this draft."
        note = f"{note} {extra}"
    return {
        "band": "" if hidden else band,
        "detail": note,
        "factors": [{"id": item["id"], "title": item["title"], "matched": item["matched"]} for item in factors],
        "similar": similar,
        "change": "" if hidden else change,
        "posts": count,
        "hidden": hidden,
    }


def _error(message: str):
    from adapt import DraftError

    return DraftError(message)
