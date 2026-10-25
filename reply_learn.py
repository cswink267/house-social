"""What a sent reply drew, from counts a later pull actually returned.

A missing like or reply count stays missing. A lesson needs three
replies on each side of a trait and a real gap. Nothing here calls a
network.

Callers: inbox refresh, the send path, and the Learning desk.
State key reply_outcomes. The user said: continue.
"""

from __future__ import annotations

from learn import MIN_SAMPLE


def note_sent(state: dict, item: dict, sent_at: str) -> dict:
    """Remember that a reply went out. Counts stay empty until a pull fills them."""
    rows = [dict(row) for row in state.get("reply_outcomes") or []]
    if any(row.get("id") == item.get("id") for row in rows):
        return {**state, "reply_outcomes": rows}
    rows.append({
        "id": str(item.get("id") or ""),
        "brand_id": str(item.get("brand_id") or ""),
        "platform": str(item.get("platform") or ""),
        "reply": str(item.get("reply") or "")[:240],
        "sent_at": sent_at,
        "likes": None,
        "replies": None,
        "likes_at_send": _number(item.get("likes")),
        "replies_at_send": _number(item.get("replies")),
    })
    return {**state, "reply_outcomes": rows[:500]}


def apply_counts(state: dict, items: list[dict]) -> dict:
    """Write a count only when this pull included that field."""
    found = {item.get("id"): item for item in items if isinstance(item, dict)}
    rows = []
    for row in state.get("reply_outcomes") or []:
        fresh = found.get(row.get("id"))
        nxt = dict(row)
        if fresh:
            nxt = _seen(nxt, "likes", "likes_at_send", fresh)
            nxt = _seen(nxt, "replies", "replies_at_send", fresh)
        rows.append(nxt)
    return {**state, "reply_outcomes": rows}


def reply_lessons(outcomes: list[dict], brand_id: str) -> list[dict]:
    """The same shape as a post lesson. Thin numbers stay thin."""
    mine = [row for row in outcomes if row.get("brand_id") == brand_id]
    if not mine:
        return []
    checked = []
    for row in mine:
        score = _further(row)
        if score is None:
            continue
        checked.append({**row, "further": score})
    if not checked:
        return [{
            "id": "reply-sample",
            "title": "Reply outcomes",
            "detail": f"{len(mine)} replies were sent. A later pull has not shown a change yet.",
            "clear": False,
        }]
    if len(checked) < MIN_SAMPLE * 2:
        return [{
            "id": "reply-sample",
            "title": "Reply outcomes",
            "detail": (
                f"{len(checked)} sent replies have a count back. "
                "A comparison waits for three with a trait and three without."
            ),
            "clear": False,
        }]
    found = []
    for trait_id, label, holds in (
        ("reply-question", "a question", lambda row: "?" in str(row.get("reply") or "")),
        ("reply-short", "a short reply", lambda row: 0 < len(str(row.get("reply") or "")) < 90),
    ):
        found.append(_trait(checked, trait_id, label, holds))
    return found


def _trait(rows: list[dict], trait_id: str, label: str, holds) -> dict:
    yes = [row for row in rows if holds(row)]
    no = [row for row in rows if str(row.get("reply") or "") and not holds(row)]
    if len(yes) < MIN_SAMPLE or len(no) < MIN_SAMPLE:
        return {
            "id": trait_id,
            "title": "Reply outcomes",
            "detail": (
                f"Replies with {label}: {len(yes)} have a count. The others: {len(no)}. "
                "A comparison waits for three and three."
            ),
            "clear": False,
        }
    mean_yes = sum(row["further"] for row in yes) / len(yes)
    mean_no = sum(row["further"] for row in no) / len(no)
    hi, lo = max(mean_yes, mean_no), min(mean_yes, mean_no)
    clear = hi >= lo * 1.5 and (hi - lo) >= 3
    if not clear:
        detail = (
            f"Replies with {label} are too close to call. "
            f"{mean_yes:.1f} more than when they were sent (n={len(yes)}) against {mean_no:.1f} without (n={len(no)})."
        )
    elif mean_yes > mean_no:
        detail = (
            f"Replies with {label} averaged {mean_yes:.1f} more likes or replies than when they were sent (n={len(yes)}). "
            f"Without that, {mean_no:.1f} (n={len(no)})."
        )
    else:
        detail = (
            f"Replies with {label} averaged less: {mean_yes:.1f} more than when they were sent (n={len(yes)}) "
            f"against {mean_no:.1f} without (n={len(no)})."
        )
    return {"id": trait_id, "title": "Reply outcomes", "detail": detail, "clear": clear}


def _further(row: dict) -> int | None:
    parts = [
        _delta(row.get("likes"), row.get("likes_at_send")),
        _delta(row.get("replies"), row.get("replies_at_send")),
    ]
    present = [number for number in parts if number is not None]
    if not present:
        return None
    return sum(present)


def _delta(latest, baseline) -> int | None:
    if not _number_ok(latest) or not _number_ok(baseline):
        return None
    if latest < baseline:
        return None
    return latest - baseline


def _seen(row: dict, key: str, base_key: str, fresh: dict) -> dict:
    if key not in fresh:
        return row
    number = fresh.get(key)
    if not _number_ok(number):
        return row
    nxt = dict(row)
    if nxt.get(base_key) is None and nxt.get(key) is None:
        nxt[base_key] = number
        return nxt
    nxt[key] = number
    return nxt


def _number(value):
    if _number_ok(value):
        return value
    return None


def _number_ok(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0
