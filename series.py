"""Reusable series for one brand.

Callers: studio, the series routes, and the composer apply action.
A suggestion exists only when the same shape is already ahead, with
three posts on both sides and a real gap. A series never moves to
another brand. The user said continue, and this is the formats item.
"""

from __future__ import annotations

import copy
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from adapt import DraftError
from analytics_desk import _has_cta, _short_hook
from voice import guide_for


_MIN = 3
_SHAPES = (
    ("question", "Question", "Ask a question.", lambda text: "?" in text),
    ("before-after", "Before and after", "Name the before and the after.", lambda text: _both(text, "before", "after")),
    ("myth-reality", "Myth and reality", "Name the myth and the reality.", lambda text: _both(text, "myth", "reality")),
    ("short-tip", "Short tip", "Open short, then ask or link.", lambda text: _short_hook({"preview": text}) and _has_cta({"preview": text})),
)


def series_for(state: dict, brand_id: str, posts: list[dict] | None = None, q: str = "", tag: str = "") -> dict:
    from store import brand_history, resolve_brand

    brand = resolve_brand(state, brand_id)
    history = list(posts) if posts is not None else brand_history(state, brand.id)[0]
    needle = q.strip().lower()
    wanted = tag.strip().lower()
    rows = []
    for item in state.get("series") or []:
        if item.get("brand_id") != brand.id:
            continue
        card = _public(item, history)
        if wanted and wanted not in {name.lower() for name in card["tags"]}:
            continue
        haystack = " ".join([card["name"], card["hook"], card["media"], " ".join(card["structure"]), " ".join(card["tags"])]).lower()
        if needle and needle not in haystack:
            continue
        rows.append(card)
    from feedback import apply_series

    return {"items": rows, "suggestions": apply_series(suggest_series(history), state, brand.id), "tags": sorted({tag_name for card in rows for tag_name in card["tags"]})}


def suggest_series(posts: list[dict]) -> list[dict]:
    usable = [post for post in posts if post.get("published_at") and post.get("engagements") is not None and str(post.get("preview") or "").strip()]
    found = []
    for shape_id, label, outline, holds in _SHAPES:
        yes = [post for post in usable if holds(str(post.get("preview") or ""))]
        no = [post for post in usable if not holds(str(post.get("preview") or ""))]
        if len(yes) < _MIN or len(no) < _MIN:
            continue
        mean_yes = _mean(yes)
        mean_no = _mean(no)
        if not (mean_yes >= mean_no * 1.5 and mean_yes - mean_no >= 3):
            continue
        found.append(
            {
                "id": shape_id,
                "name": label,
                "outline": outline,
                "detail": (
                    f"{label} averaged {mean_yes} engagements (n={len(yes)}). "
                    f"The other posts averaged {mean_no} (n={len(no)}). "
                    "This shape is ahead. It is not saved until you keep it."
                ),
                "examples": [str(post.get("id") or "") for post in yes[:3] if post.get("id")],
            }
        )
    return found


def save_series(state: dict, brand_id: str, spec: dict, path: Path | None = None, posts: list[dict] | None = None) -> dict:
    from store import brand_history, resolve_brand, save

    brand = resolve_brand(state, brand_id)
    if not isinstance(spec, dict):
        raise DraftError("A series needs a name and a structure.")
    name = _clip(spec.get("name"), 80)
    structure = _structure(spec.get("structure"))
    if not name or not structure:
        raise DraftError("A series needs a name and a structure.")
    history = list(posts) if posts is not None else brand_history(state, brand.id)[0]
    examples = _examples(spec.get("examples"), history)
    updated = copy.deepcopy(state)
    row = {
        "id": str(uuid.uuid4()),
        "brand_id": brand.id,
        "name": name,
        "structure": structure,
        "hook": _clip(spec.get("hook"), 160),
        "media": _clip(spec.get("media"), 160),
        "examples": examples,
        "tags": _tags(spec.get("tags")),
        "uses": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    mine = [item for item in updated.get("series") or [] if item.get("brand_id") == brand.id]
    others = [item for item in updated.get("series") or [] if item.get("brand_id") != brand.id]
    updated["series"] = others + (mine + [row])[-40:]
    save(updated, path)
    return _public(row, history)


def keep_series(state: dict, brand_id: str, shape_id: str, path: Path | None = None) -> dict:
    from store import brand_history

    history = brand_history(state, brand_id)[0]
    found = next((item for item in suggest_series(history) if item["id"] == str(shape_id or "")), None)
    if found is None:
        raise DraftError("That shape is not ahead for this brand.")
    return save_series(
        state,
        brand_id,
        {"name": found["name"], "structure": ["{topic}", found["outline"]], "examples": found["examples"], "tags": [found["id"]]},
        path,
        history,
    )


def apply_series(state: dict, brand_id: str, series_id: str, topic: str, path: Path | None = None) -> dict:
    from store import create_piece, load, resolve_brand, save

    brand = resolve_brand(state, brand_id)
    row = _find(state, brand.id, series_id)
    subject = _clip(topic, 120)
    if not subject:
        raise DraftError("A series needs a topic.")
    idea = _fill(row, subject, guide_for(brand.id, (state.get("voices") or {}).get(brand.id)))
    piece = create_piece(state, brand.id, idea, path, status="draft")
    current = load(path) if path else load()
    updated = copy.deepcopy(current)
    for item in updated.get("pieces") or []:
        if item.get("id") == piece["id"]:
            item["series_id"] = row["id"]
    for item in updated.get("series") or []:
        if item.get("id") == row["id"] and item.get("brand_id") == brand.id:
            item["uses"] = ([{"at": datetime.now(timezone.utc).isoformat(), "topic": subject, "piece_id": piece["id"]}, *(item.get("uses") or [])])[:40]
    save(updated, path)
    return {"piece_id": piece["id"], "idea": idea, "series_id": row["id"]}


def _public(item: dict, posts: list[dict]) -> dict:
    by_id = {str(post.get("id") or ""): post for post in posts}
    by_piece = {str(post.get("piece_id") or ""): post for post in posts if post.get("piece_id")}
    examples = []
    for example_id in item.get("examples") or []:
        post = by_id.get(str(example_id))
        examples.append(
            {
                "id": str(example_id),
                "preview": str((post or {}).get("preview") or "Not in the pull.")[:140],
                "engagements": None if post is None or post.get("engagements") is None else int(post.get("engagements") or 0),
            }
        )
    counted = []
    for use in item.get("uses") or []:
        post = by_piece.get(str(use.get("piece_id") or ""))
        if post and post.get("published_at") and post.get("engagements") is not None:
            counted.append(post)
    return {
        "id": item.get("id") or "",
        "name": item.get("name") or "",
        "structure": list(item.get("structure") or []),
        "hook": item.get("hook") or "",
        "media": item.get("media") or "",
        "tags": list(item.get("tags") or []),
        "examples": examples,
        "uses": len(item.get("uses") or []),
        "stats": _stats(counted),
        "notice": _notice(counted),
    }


def _stats(posts: list[dict]) -> dict:
    if len(posts) < _MIN:
        return {"ready": False, "n": len(posts), "mean": None, "detail": f"Not enough uses with numbers. {len(posts)} so far."}
    mean = _mean(posts)
    best = max(posts, key=lambda post: int(post.get("engagements") or 0))
    return {
        "ready": True,
        "n": len(posts),
        "mean": mean,
        "detail": f"Average {mean} engagements (n={len(posts)}). Best reached {int(best.get('engagements') or 0)}.",
    }


def _notice(posts: list[dict]) -> str:
    ordered = sorted(posts, key=lambda post: str(post.get("published_at") or ""))
    if len(ordered) < _MIN * 2:
        return ""
    half = len(ordered) // 2
    earlier, later = ordered[:half], ordered[half:]
    if len(earlier) < _MIN or len(later) < _MIN:
        return ""
    mean_early = _mean(earlier)
    mean_late = _mean(later)
    if mean_early >= mean_late * 1.5 and mean_early - mean_late >= 3:
        return (
            f"Later uses averaged {mean_late} (n={len(later)}) against {mean_early} earlier (n={len(earlier)}). "
            "Worth a refresh. Nothing was deleted."
        )
    return ""


def _fill(item: dict, topic: str, guide: dict) -> str:
    lines = []
    for line in item.get("structure") or []:
        text = str(line).replace("{topic}", topic).strip()
        if text:
            lines.append(text)
    if topic and all(topic not in line for line in lines):
        lines.insert(0, topic)
    hook = str(item.get("hook") or "").strip()
    if hook:
        lines.append(hook.replace("{topic}", topic))
    required = [str(line).strip() for line in (guide.get("required") or []) if str(line).strip()]
    if required:
        lines.append("Voice to keep: " + "; ".join(required[:4]))
    return "\n".join(lines)[:2000]


def _examples(raw, posts: list[dict]) -> list[str]:
    if raw in (None, "", []):
        return []
    if isinstance(raw, str):
        raw = [part.strip() for part in raw.split(",") if part.strip()]
    if not isinstance(raw, list):
        raise DraftError("Example posts are ids from this brand.")
    known = {str(post.get("id") or "") for post in posts}
    found = []
    for item in raw:
        name = str(item or "").strip()
        if not name:
            continue
        if name not in known:
            raise DraftError("That post is not on this brand.")
        if name not in found:
            found.append(name)
        if len(found) >= 6:
            break
    return found


def _structure(raw) -> list[str]:
    if isinstance(raw, str):
        raw = [line.strip() for line in raw.splitlines() if line.strip()]
    if not isinstance(raw, list):
        return []
    lines = []
    for item in raw:
        text = _clip(item, 160)
        if text:
            lines.append(text)
        if len(lines) >= 8:
            break
    return lines


def _tags(raw) -> list[str]:
    if isinstance(raw, str):
        raw = [part.strip() for part in raw.split(",") if part.strip()]
    if not isinstance(raw, list):
        return []
    found = []
    for item in raw:
        text = _clip(item, 32)
        if text and text.lower() not in {name.lower() for name in found}:
            found.append(text)
        if len(found) >= 8:
            break
    return found


def _find(state: dict, brand_id: str, series_id: str) -> dict:
    found = next((item for item in state.get("series") or [] if item.get("id") == series_id), None)
    if found is None:
        raise DraftError("That series is not on this brand.")
    if found.get("brand_id") != brand_id:
        raise DraftError("A series stays on its brand.")
    return found


def _mean(posts: list[dict]) -> float:
    return round(sum(int(post.get("engagements") or 0) for post in posts) / len(posts), 1)


def _both(text: str, left: str, right: str) -> bool:
    words = set(re.findall(r"[a-z0-9']+", text.lower()))
    return left in words and right in words


def _clip(value, limit: int) -> str:
    return str(value or "").strip()[:limit]
