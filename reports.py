"""Weekly and monthly brand reports. The file is safe to hand to someone.

Numbers come from the same analytics as the desk. A missing count stays
missing. The export does not carry a token.

Called by store.reports_for and the dashboard report routes. A report row
stores the period, the written note, the analytics document, and markdown.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from adapt import DraftError
from learn import analytics, _campaigns, _in_window, _local_day, _top, _totals, _window_lines, format_table
from meta import redact
from store import _label, brand_history, resolve_brand, save


def reports_for(state: dict, brand_id: str) -> dict:
    brand = resolve_brand(state, brand_id)
    rows = [_public(item) for item in state.get("reports") or [] if item.get("brand_id") == brand.id]
    return {"reports": rows}


def generate_report(state: dict, brand_id: str, period: str, note: str = "", path: Path | None = None, today: date | None = None) -> dict:
    brand = resolve_brand(state, brand_id)
    kind = (period or "").strip().lower()
    if kind not in {"week", "month"}:
        raise DraftError("A report is a week or a month.")
    when = today or datetime.now(ZoneInfo("America/New_York")).date()
    posts, page_days = brand_history(state, brand.id)
    pieces = [piece for piece in state.get("pieces") or [] if piece.get("brand_id") == brand.id]
    if kind == "week":
        start = when - timedelta(days=6)
        body = analytics(posts, page_days, pieces, today=when, days=7)
        title = f"Week of {start.isoformat()} through {when.isoformat()}"
    else:
        start = when.replace(day=1)
        previous_end = start - timedelta(days=1)
        previous_start = previous_end.replace(day=1)
        body = _between(posts, page_days, pieces, start, when, previous_start, previous_end, "This month against last month")
        title = f"{when.strftime('%B %Y')} through {when.isoformat()}"
    written = _label(note or "", 1000)
    body = _with_learning(body, state, brand.id, posts, page_days, when)
    body = _redact_tree(body)
    markdown = redact(_markdown(brand.name, title, written, body))
    row = {
        "id": str(uuid.uuid4()),
        "brand_id": brand.id,
        "period": kind,
        "title": title,
        "note": written,
        "start": start.isoformat(),
        "end": when.isoformat(),
        "generated_at": datetime.now(ZoneInfo("America/New_York")).isoformat(),
        "markdown": markdown,
        "document": body,
    }
    kept = [item for item in state.get("reports") or [] if item.get("brand_id") != brand.id]
    mine = [row, *[item for item in state.get("reports") or [] if item.get("brand_id") == brand.id]][:24]
    save({**state, "reports": [*mine, *kept]}, path)
    return _public(row)


def report_export(state: dict, report_id: str, fmt: str) -> tuple[str, str, str]:
    row = next((item for item in state.get("reports") or [] if item.get("id") == report_id), None)
    if row is None:
        raise DraftError("That report is not on this brand.")
    kind = (fmt or "md").strip().lower()
    if kind == "md":
        return redact(row.get("markdown") or ""), "text/markdown; charset=utf-8", f"{row['title']}.md"
    if kind == "json":
        payload = {
            "title": row.get("title"),
            "period": row.get("period"),
            "note": row.get("note") or "",
            "start": row.get("start"),
            "end": row.get("end"),
            "generated_at": row.get("generated_at"),
            "document": _redact_tree(row.get("document") or {}),
        }
        return json.dumps(payload, indent=2), "application/json", f"{row['title']}.json"
    raise DraftError("Export is markdown or json.")


def write_insight(state: dict, report_id: str, complete, path: Path | None = None) -> dict:
    from assist import assist
    from voice import guide_for

    index, row = _report(state, report_id)
    brief = _brief(row.get("document") or {})
    guide = guide_for(row["brand_id"], (state.get("voices") or {}).get(row["brand_id"]))
    try:
        result = assist(guide, "report", brief, complete=complete)
    except DraftError:
        raise
    except (OSError, TimeoutError) as exc:
        raise DraftError("The assistant is offline.") from exc
    text = _label(result.get("text") or "", 1000)
    if "%" in text and "%" not in brief:
        raise DraftError("The assistant added a percent the report does not have.")
    document = {**(row.get("document") or {}), "insight": text}
    brand = resolve_brand(state, row["brand_id"])
    markdown = redact(_markdown(brand.name, row.get("title") or "", row.get("note") or "", document))
    updated = {**row, "document": document, "markdown": markdown}
    reports = list(state.get("reports") or [])
    reports[index] = updated
    save({**state, "reports": reports}, path)
    return _public(updated)


def _between(posts, page_days, pieces, start, end, previous_start, previous_end, label) -> dict:
    current_posts = [post for post in posts if _in_window(_local_day(str(post.get("published_at") or "")), start, end)]
    current_days = [day for day in page_days if _in_window(str(day.get("date") or ""), start, end)]
    previous_posts = [post for post in posts if _in_window(_local_day(str(post.get("published_at") or "")), previous_start, previous_end)]
    previous_days = [day for day in page_days if _in_window(str(day.get("date") or ""), previous_start, previous_end)]
    current = _totals(current_posts, current_days)
    previous = _totals(previous_posts, previous_days)
    return {
        "days": None,
        "totals": current,
        "comparison": _window_lines(current, previous, label),
        "campaigns": _campaigns(current_posts, pieces),
        "formats": format_table([post for post in current_posts if post.get("format") not in (None, "", "unknown")]),
        "top": _top(current_posts),
        **_annotate(current_posts, pieces),
    }


def _markdown(brand: str, title: str, note: str, body: dict) -> str:
    totals = body.get("totals") or {}
    lines = [
        f"# {brand}",
        "",
        title,
        "",
        note or "No note.",
        "",
        "## Numbers",
        f"- Engagements: {totals.get('engagements', 0)} across {totals.get('posts', 0)} posts",
        f"- Shares: {totals.get('shares', 0)}",
        f"- Reach: {_shown(totals.get('reach'), totals.get('reach_note'))}",
        f"- Saves: {_shown(totals.get('saves'), totals.get('saves_note'))}",
        f"- Follower change: {_shown(totals.get('growth'), totals.get('growth_note'))}",
        "",
        f"## {(body.get('comparison') or {}).get('label') or 'Comparison'}",
    ]
    lines.extend(f"- {line}" for line in (body.get("comparison") or {}).get("lines") or [])
    lines.extend(["", "## Top posts"])
    top = body.get("top") or []
    if not top:
        lines.append("- No posts in this window.")
    for index, post in enumerate(top, start=1):
        preview = redact(str(post.get("preview") or "Untitled")).replace("\n", " ")
        lines.append(f"- {index}. {preview} — {post.get('engagements', 0)} engagements, {post.get('shares', 0)} shares")
    lines.extend(["", "## Formats"])
    formats = body.get("formats") or []
    if not formats:
        lines.append("- No format in this window.")
    for item in formats:
        lines.append(f"- {item.get('label')}: mean {item.get('mean')} (n={item.get('n')})")
    lines.extend(["", "## What worked"])
    worked = body.get("worked") or ["Nothing in this window is clear enough to call what worked."]
    lines.extend(f"- {line}" for line in worked)
    lines.extend(["", "## What did not"])
    missed = body.get("missed") or ["Nothing in this window is clear enough to call what did not."]
    lines.extend(f"- {line}" for line in missed)
    lines.extend(["", "## Goals"])
    lines.extend(f"- {line}" for line in body.get("goals") or ["No goal is set for this brand."])
    lines.extend(["", "## Next period"])
    lines.extend(f"- {line}" for line in body.get("recommendations") or ["No recommendation is clear enough for the next period."])
    lines.extend(["", "## Insight", body.get("insight") or "The assistant has not written this yet.", ""])
    lines.extend(["", "## Campaigns"])
    campaigns = body.get("campaigns") or []
    if not campaigns:
        lines.append("- No campaign in this window.")
    for item in campaigns:
        lines.append(f"- {item.get('detail')}")
    lines.extend(
        [
            "",
            "This report stays on the desk. It is not a public link, and nothing is mailed.",
            "This report does not include account tokens.",
            "",
        ]
    )
    return "\n".join(lines)


def _redact_tree(value):
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [_redact_tree(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact_tree(item) for key, item in value.items()}
    return value


def _with_learning(body: dict, state: dict, brand_id: str, posts: list[dict], page_days: list[dict], today: date) -> dict:
    learned = dict(body)
    learned["goals"] = _goal_lines(state, brand_id, posts, page_days, today)
    learned["worked"], learned["missed"] = _sides(learned)
    learned["recommendations"] = _recommendations(learned)
    learned["insight"] = "The assistant has not written this yet."
    return learned


def _goal_lines(state: dict, brand_id: str, posts: list[dict], page_days: list[dict], today: date) -> list[str]:
    from analytics_desk import goal_line

    goals = [goal for goal in state.get("goals") or [] if goal.get("brand_id") == brand_id]
    if not goals:
        return ["No goal is set for this brand."]
    return [goal_line(goal, posts, page_days, today)["detail"] for goal in goals[:6]]


def _sides(body: dict) -> tuple[list[str], list[str]]:
    clear = [item.get("detail") for item in body.get("patterns") or [] if item.get("clear") and item.get("detail")]
    alerts = [item.get("detail") for item in body.get("alerts") or [] if item.get("detail")]
    worked = [*clear, *alerts]
    if not worked:
        return (
            ["Nothing in this window is clear enough to call what worked."],
            ["Nothing in this window is clear enough to call what did not."],
        )
    missed = []
    for post in (body.get("bottom") or [])[:3]:
        preview = str(post.get("preview") or "Untitled").replace("\n", " ")
        missed.append(f"Lowest in this window: {preview} — {int(post.get('engagements') or 0)} engagements.")
    if not missed:
        missed = ["Nothing in this window is clear enough to call what did not."]
    return worked, missed


def _recommendations(body: dict) -> list[str]:
    lines = [item.get("detail") for item in body.get("patterns") or [] if item.get("clear") and item.get("detail")]
    lines.extend(item.get("detail") for item in body.get("alerts") or [] if item.get("detail"))
    if not lines:
        return ["No recommendation is clear enough for the next period."]
    return [f"Next period: {line}" for line in lines[:6]]


def _brief(body: dict) -> str:
    lines = ["Use only these lines. Do not invent a metric."]
    lines.extend(body.get("recommendations") or [])
    lines.extend(body.get("goals") or [])
    lines.extend((body.get("comparison") or {}).get("lines") or [])
    return "\n".join(str(line) for line in lines if line)


def _annotate(posts: list[dict], pieces: list[dict]) -> dict:
    from analytics_desk import annotate

    extra = annotate(posts, pieces)
    return {"patterns": extra["patterns"], "alerts": extra["alerts"], "bottom": extra["bottom"]}


def _report(state: dict, report_id: str) -> tuple[int, dict]:
    for index, row in enumerate(state.get("reports") or []):
        if row.get("id") == report_id:
            return index, row
    raise DraftError("That report is not on this brand.")


def _shown(value, note: str) -> str:
    if value is None:
        return note or "Not in the pull."
    return str(value)


def _public(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "brand_id": row.get("brand_id"),
        "period": row.get("period"),
        "title": row.get("title") or "",
        "note": row.get("note") or "",
        "start": row.get("start") or "",
        "end": row.get("end") or "",
        "generated_at": row.get("generated_at") or "",
        "markdown": row.get("markdown") or "",
        "document": row.get("document") or {},
    }
