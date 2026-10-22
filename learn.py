"""Engagement lessons for House Social.

Page days and post totals come from recorded stats or the Josie
Facebook ledger on disk. A comparison needs three observations in
each group. Impressions of zero never become a rate.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


MIN_SAMPLE = 3
_DAY_FILE = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")
_OFFSET = re.compile(r"([+-])(\d{2})(\d{2})$")

_INSIGHTS = (
    ("page_posts_impressions_organic", "impressions"),
    ("page_post_engagements", "engagements"),
    ("page_actions_post_reactions_total", "reactions"),
    ("page_daily_follows", "follows"),
    ("page_daily_unfollows", "unfollows"),
    ("page_views_total", "views"),
)


def parse_daily(payload: dict) -> dict:
    """One fb-engagement JSON object, normalized."""
    posts: dict[str, dict] = {}
    for raw in payload.get("posts") or []:
        post = _post_from_ledger(raw)
        if post:
            posts[post["id"]] = post
    days: dict[str, dict] = {}
    insights = payload.get("insights") if isinstance(payload.get("insights"), dict) else {}
    for metric, key in _INSIGHTS:
        for row in insights.get(metric) or []:
            if not isinstance(row, dict) or not row.get("date"):
                continue
            day = days.setdefault(str(row["date"]), {"date": str(row["date"])})
            day[key] = _nonneg(row.get("value"))
    return {"posts": posts, "days": days}


def read_ledger(directory: Path, limit_files: int = 45) -> dict:
    """Newest daily files in a ledger directory. Missing or dirty files are skipped."""
    root = directory.resolve()
    if not root.is_dir():
        return {"posts": [], "days": []}
    paths = sorted(path for path in root.iterdir() if path.is_file() and _DAY_FILE.match(path.name))
    posts: dict[str, dict] = {}
    days: dict[str, dict] = {}
    for path in paths[-limit_files:]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeError):
            continue
        if not isinstance(payload, dict):
            continue
        parsed = parse_daily(payload)
        posts.update(parsed["posts"])
        days.update(parsed["days"])
    return {
        "posts": list(posts.values()),
        "days": [days[key] for key in sorted(days)],
    }


def manual_posts(stats: list[dict]) -> list[dict]:
    rows = []
    for stat in stats:
        metrics = stat.get("metrics") if isinstance(stat.get("metrics"), dict) else {}
        engagements = metrics.get("engagements")
        if engagements is None:
            engagements = sum(int(metrics.get(key, 0) or 0) for key in ("likes", "comments", "shares", "saves", "clicks"))
        rows.append(
            {
                "id": stat.get("id") or "",
                "external_id": stat.get("external_id") or "",
                "preview": str(stat.get("preview") or stat.get("note") or "")[:140],
                "published_at": stat.get("published_at") or "",
                "local_hour": stat.get("local_hour"),
                "reactions": int(metrics.get("likes", 0) or 0),
                "comments": int(metrics.get("comments", 0) or 0),
                "shares": int(metrics.get("shares", 0) or 0),
                "engagements": int(engagements or 0),
                "impressions": int(metrics.get("impressions", 0) or 0),
                "saves": int(metrics["saves"]) if "saves" in metrics and metrics.get("saves") is not None else None,
                "follows": int(metrics["follows"]) if "follows" in metrics and metrics.get("follows") is not None else None,
                "piece_id": stat.get("piece_id") or "",
                "permalink": stat.get("permalink") or "",
                "format": stat.get("format") or "unknown",
                "source": "recorded",
            }
        )
    return rows


def combine_posts(ledger_posts: list[dict], recorded: list[dict]) -> list[dict]:
    """A recorded stat with the same external id replaces the ledger row."""
    by_external: dict[str, dict] = {}
    order: list[str] = []
    for post in ledger_posts:
        key = str(post.get("id") or "")
        if not key:
            continue
        if key not in by_external:
            order.append(key)
        by_external[key] = post
    extras: list[dict] = []
    for post in recorded:
        external = str(post.get("external_id") or "")
        if external and external in by_external:
            by_external[external] = {**post, "id": external, "source": "recorded"}
            continue
        extras.append(post)
    return [by_external[key] for key in order] + extras


def performance(posts: list[dict], page_days: list[dict], pieces: list[dict] | None = None, today: date | None = None) -> dict:
    when = today or datetime.now(ZoneInfo("America/New_York")).date()
    owned = pieces or []
    ranges = {
        "7": analytics(posts, page_days, owned, today=when, days=7),
        "28": analytics(posts, page_days, owned, today=when, days=28),
        "90": analytics(posts, page_days, owned, today=when, days=90),
        "all": analytics(posts, page_days, owned, today=when, days=None),
    }
    ranked = sorted(posts, key=lambda post: post.get("engagements", 0), reverse=True)
    return {
        "page_days": _page_series(page_days)[-30:],
        "recorded_days": _recorded_days(posts)[-30:],
        "hours": hour_table(posts),
        "posts": ranked[:12],
        "formats": format_table([post for post in posts if post.get("format") not in (None, "", "unknown")]),
        "source": "ledger" if page_days else ("recorded" if posts else "none"),
        "ranges": ranges,
    }


def analytics(
    posts: list[dict],
    page_days: list[dict],
    pieces: list[dict],
    *,
    today: date,
    days: int | None,
) -> dict:
    start, previous_start, previous_end = _bounds(today, days)
    current_posts = [post for post in posts if _in_window(_local_day(str(post.get("published_at") or "")), start, today)]
    current_days = [day for day in page_days if _in_window(str(day.get("date") or ""), start, today)]
    current = _totals(current_posts, current_days)
    if days is None:
        comparison = {"label": "Full history", "lines": ["There is no earlier window to set beside the full history."]}
    else:
        previous_posts = [
            post for post in posts
            if _in_window(_local_day(str(post.get("published_at") or "")), previous_start, previous_end)
        ]
        previous_days = [day for day in page_days if _in_window(str(day.get("date") or ""), previous_start, previous_end)]
        previous = _totals(previous_posts, previous_days)
        comparison = _window_lines(current, previous, f"These {days} days against the {days} before")
    return {
        "days": days,
        "totals": current,
        "comparison": comparison,
        "campaigns": _campaigns(current_posts, pieces),
        "formats": format_table([post for post in current_posts if post.get("format") not in (None, "", "unknown")]),
        "top": _top(current_posts),
    }


def _bounds(today: date, days: int | None) -> tuple[date | None, date | None, date | None]:
    if days is None:
        return None, None, None
    start = today - timedelta(days=days - 1)
    previous_end = start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=days - 1)
    return start, previous_start, previous_end


def _in_window(day: str, start: date | None, end: date | None) -> bool:
    if not day or end is None:
        return False
    try:
        current = date.fromisoformat(day)
    except ValueError:
        return False
    if current > end:
        return False
    return start is None or current >= start


def _local_day(value: str) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    normalized = _normalize_iso(text)
    if not normalized:
        return ""
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(ZoneInfo("America/New_York")).date().isoformat()


def _totals(posts: list[dict], page_days: list[dict]) -> dict:
    reach_days = [day for day in page_days if day.get("impressions") is not None and "impressions" in day]
    post_reach = [post for post in posts if int(post.get("impressions") or 0) > 0]
    if reach_days:
        reach = sum(int(day.get("impressions") or 0) for day in reach_days)
        reach_note = "Page impressions."
    elif post_reach:
        reach = sum(int(post.get("impressions") or 0) for post in posts)
        reach_note = "Post impressions."
    else:
        reach = None
        reach_note = "The pull did not include reach."
    save_rows = [post.get("saves") for post in posts if post.get("saves") is not None]
    follow_days = [day for day in page_days if "follows" in day or "unfollows" in day]
    follow_posts = [post.get("follows") for post in posts if post.get("follows") is not None]
    if follow_days:
        growth = sum(int(day.get("follows") or 0) - int(day.get("unfollows") or 0) for day in follow_days)
        growth_note = "Follows minus unfollows."
    elif follow_posts:
        growth = sum(int(value) for value in follow_posts)
        growth_note = "Recorded follows. Unfollows were not in the row."
    else:
        growth = None
        growth_note = "Follower counts were not in this pull."
    return {
        "posts": len(posts),
        "engagements": sum(int(post.get("engagements") or 0) for post in posts),
        "shares": sum(int(post.get("shares") or 0) for post in posts),
        "saves": sum(int(value) for value in save_rows) if save_rows else None,
        "saves_note": "Recorded saves." if save_rows else "Saves were not in this pull.",
        "reach": reach,
        "reach_note": reach_note,
        "growth": growth,
        "growth_note": growth_note,
    }


def _window_lines(current: dict, previous: dict, label: str) -> dict:
    lines = [
        f"Engagements {current['engagements']} in this window, {previous['engagements']} in the one before.",
        f"Shares {current['shares']} against {previous['shares']}.",
    ]
    if current["reach"] is not None and previous["reach"] is not None:
        lines.append(f"Reach {current['reach']} against {previous['reach']}.")
    else:
        lines.append(current["reach_note"])
    if current["saves"] is not None and previous["saves"] is not None:
        lines.append(f"Saves {current['saves']} against {previous['saves']}.")
    else:
        lines.append(current["saves_note"])
    if current["growth"] is not None and previous["growth"] is not None:
        lines.append(f"Follower change {current['growth']} against {previous['growth']}.")
    else:
        lines.append(current["growth_note"])
    return {"label": label, "lines": lines}


def _campaigns(posts: list[dict], pieces: list[dict]) -> list[dict]:
    names = []
    tagged = []
    for post in posts:
        name = _campaign_name(post, pieces)
        tagged.append((post, name))
        if name and name not in names:
            names.append(name)
    if not names:
        return [{"name": "", "clear": False, "n": 0, "detail": "No post in this window is tied to a campaign."}]
    rows = []
    for name in names:
        inside = [post for post, label in tagged if label == name]
        outside = [post for post, label in tagged if label != name]
        mean_in = _mean(inside)
        mean_out = _mean(outside)
        clear = (
            len(inside) >= MIN_SAMPLE
            and len(outside) >= MIN_SAMPLE
            and abs(mean_in - mean_out) >= 3
            and max(mean_in, mean_out) >= min(mean_in, mean_out) * 1.5
        )
        if len(inside) < MIN_SAMPLE or len(outside) < MIN_SAMPLE:
            detail = (
                f"{name} has {len(inside)} posts in this window. "
                f"A comparison waits for {MIN_SAMPLE} inside the campaign and {MIN_SAMPLE} outside it."
            )
        elif not clear:
            detail = (
                f"{name} is too close to call. {mean_in:.1f} engagements (n={len(inside)}) "
                f"against {mean_out:.1f} on the other posts (n={len(outside)})."
            )
        elif mean_in > mean_out:
            detail = (
                f"{name} averaged {mean_in:.1f} engagements (n={len(inside)}). "
                f"The other posts averaged {mean_out:.1f} (n={len(outside)})."
            )
        else:
            detail = (
                f"{name} averaged less: {mean_in:.1f} (n={len(inside)}) "
                f"against {mean_out:.1f} on the other posts (n={len(outside)})."
            )
        rows.append({"name": name, "clear": clear, "n": len(inside), "detail": detail})
    return rows


def _campaign_name(post: dict, pieces: list[dict]) -> str:
    piece_id = str(post.get("piece_id") or "")
    if not piece_id:
        return ""
    piece = next((item for item in pieces if item.get("id") == piece_id), None)
    return str((piece or {}).get("campaign") or "")


def _mean(posts: list[dict]) -> float:
    if not posts:
        return 0.0
    return sum(int(post.get("engagements") or 0) for post in posts) / len(posts)


def _top(posts: list[dict]) -> list[dict]:
    ranked = sorted(posts, key=lambda post: int(post.get("engagements") or 0), reverse=True)
    rows = []
    for post in ranked[:5]:
        rows.append(
            {
                "id": post.get("id") or "",
                "preview": str(post.get("preview") or "")[:140],
                "engagements": int(post.get("engagements") or 0),
                "shares": int(post.get("shares") or 0),
                "saves": post.get("saves"),
                "format": post.get("format") or "",
                "platform": post.get("platform") or "",
                "permalink": post.get("permalink") or "",
            }
        )
    return rows


def lessons(posts: list[dict], page_days: list[dict], recorded: list[dict]) -> list[dict]:
    found: list[dict] = []
    if len(posts) < MIN_SAMPLE:
        found.append(
            {
                "id": "sample",
                "title": "Not a pattern yet",
                "detail": f"{len(posts)} posts in this window. A comparison waits for {MIN_SAMPLE}.",
                "clear": False,
            }
        )
    hour = _hour_lesson(posts)
    if hour:
        found.append(hour)
    trend = _trend_lesson(page_days)
    if trend:
        found.append(trend)
    shaped = _format_lesson([post for post in posts if post.get("format") not in (None, "", "unknown")])
    if shaped:
        found.append(shaped)
    found.extend(_trait_lessons(posts))
    lead = _lead_lesson(posts)
    if lead:
        found.append(lead)
    return found


def _trait_lessons(posts: list[dict]) -> list[dict]:
    checks = (
        ("question", "a question", lambda post: "?" in str(post.get("preview") or "")),
        ("hashtags", "hashtags", lambda post: "#" in str(post.get("preview") or "")),
        ("short", "a short line", lambda post: 0 < len(str(post.get("preview") or "")) < 90),
    )
    found = []
    for trait_id, label, holds in checks:
        lesson = _trait_lesson(posts, trait_id, label, holds)
        if lesson:
            found.append(lesson)
    return found


def _trait_lesson(posts: list[dict], trait_id: str, label: str, holds) -> dict | None:
    yes = [post for post in posts if holds(post)]
    no = [post for post in posts if str(post.get("preview") or "") and not holds(post)]
    if len(yes) < MIN_SAMPLE or len(no) < MIN_SAMPLE:
        return None
    mean_yes = sum(int(post.get("engagements") or 0) for post in yes) / len(yes)
    mean_no = sum(int(post.get("engagements") or 0) for post in no) / len(no)
    hi, lo = max(mean_yes, mean_no), min(mean_yes, mean_no)
    clear = hi >= lo * 1.5 and (hi - lo) >= 3
    if not clear:
        detail = (
            f"Posts with {label} are too close to call. "
            f"{mean_yes:.1f} engagements (n={len(yes)}) against {mean_no:.1f} without (n={len(no)})."
        )
    elif mean_yes > mean_no:
        detail = (
            f"Posts with {label} averaged {mean_yes:.1f} engagements (n={len(yes)}). "
            f"Without them, {mean_no:.1f} (n={len(no)})."
        )
    else:
        detail = (
            f"Posts with {label} averaged less: {mean_yes:.1f} (n={len(yes)}) "
            f"against {mean_no:.1f} without (n={len(no)})."
        )
    return {"id": trait_id, "title": "What the posts did", "detail": detail, "clear": clear}


def next_step(found: list[dict], unscheduled: int) -> dict:
    hour = next((item for item in found if item.get("id") == "hour" and item.get("clear")), None)
    if hour:
        detail = hour.get("next") or hour["detail"]
    elif unscheduled:
        detail = f"{unscheduled} drafts are still unscheduled."
    else:
        detail = "Write one idea and shape it three ways. Record the result after it is live."
    return {"id": "next", "title": "Next", "detail": detail, "clear": True}


def hour_table(posts: list[dict]) -> list[dict]:
    buckets: dict[int, list[int]] = {}
    for post in posts:
        hour = post.get("local_hour")
        if not isinstance(hour, int) or not 0 <= hour <= 23:
            continue
        buckets.setdefault(hour, []).append(int(post.get("engagements") or 0))
    rows = []
    for hour in sorted(buckets):
        values = buckets[hour]
        rows.append(
            {
                "id": str(hour),
                "hour": hour,
                "label": f"{hour:02d}:00",
                "mean": round(sum(values) / len(values), 1),
                "n": len(values),
            }
        )
    return rows


def format_table(posts: list[dict]) -> list[dict]:
    buckets: dict[str, list[int]] = {}
    for post in posts:
        name = str(post.get("format") or "unknown")
        if name == "unknown":
            continue
        buckets.setdefault(name, []).append(int(post.get("engagements") or 0))
    rows = []
    for name, values in buckets.items():
        rows.append(
            {
                "id": name,
                "format": name,
                "label": name,
                "mean": round(sum(values) / len(values), 1),
                "n": len(values),
            }
        )
    rows.sort(key=lambda row: row["mean"], reverse=True)
    return rows


def suggest_hour(posts: list[dict]) -> dict:
    """A schedule hour only when the same gap rule as the hour lesson is clear."""
    lesson = _hour_lesson(posts)
    if not lesson:
        return {"clear": False, "hour": None, "label": "", "detail": "Not enough hours to suggest a time."}
    return {
        "clear": bool(lesson.get("clear")),
        "hour": lesson.get("hour") if lesson.get("clear") else None,
        "label": lesson.get("label") or "" if lesson.get("clear") else "",
        "detail": lesson.get("detail") or "",
    }


def engagement_rate(impressions: int, engagements: int) -> float | None:
    if impressions <= 0:
        return None
    return round(engagements / impressions, 4)


def _post_from_ledger(raw: dict) -> dict | None:
    if not isinstance(raw, dict) or not raw.get("id"):
        return None
    reactions = _nonneg(raw.get("reactions"))
    comments = _nonneg(raw.get("comments"))
    shares = _nonneg(raw.get("shares"))
    total = raw.get("total")
    engagements = _nonneg(total) if total is not None else reactions + comments + shares
    preview = " ".join(str(raw.get("message") or "").split())[:140]
    hour = raw.get("local_hour")
    return {
        "id": str(raw["id"]),
        "preview": preview,
        "published_at": _normalize_iso(str(raw.get("created_time_iso") or "")),
        "local_hour": hour if isinstance(hour, int) else None,
        "reactions": reactions,
        "comments": comments,
        "shares": shares,
        "engagements": engagements,
        "impressions": 0,
        "permalink": str(raw.get("permalink") or ""),
        "format": "unknown",
        "source": "ledger",
    }


def _page_series(days: list[dict]) -> list[dict]:
    rows = []
    for day in sorted(days, key=lambda item: item.get("date", "")):
        if not day.get("date"):
            continue
        rows.append(
            {
                "id": day["date"],
                "date": day["date"],
                "label": day["date"][5:],
                "impressions": int(day.get("impressions") or 0),
                "engagements": int(day.get("engagements") or 0),
                "reactions": int(day.get("reactions") or 0),
                "follows": int(day.get("follows") or 0),
                "unfollows": int(day.get("unfollows") or 0),
            }
        )
    return rows


def _recorded_days(posts: list[dict]) -> list[dict]:
    buckets: dict[str, dict] = {}
    for post in posts:
        day = str(post.get("published_at") or "")[:10]
        if len(day) != 10:
            continue
        row = buckets.setdefault(day, {"id": day, "date": day, "label": day[5:], "engagements": 0, "n": 0})
        row["engagements"] += int(post.get("engagements") or 0)
        row["n"] += 1
    return [buckets[key] for key in sorted(buckets)]


def _hour_lesson(posts: list[dict]) -> dict | None:
    ready = [row for row in hour_table(posts) if row["n"] >= MIN_SAMPLE]
    if len(ready) < 2:
        if len(ready) == 1:
            only = ready[0]
            return {
                "id": "hour",
                "title": "Hours",
                "detail": f"Only {only['label']} has {only['n']} posts. That is not a comparison.",
                "clear": False,
            }
        return None
    best = max(ready, key=lambda row: row["mean"])
    others = sorted(row["mean"] for row in ready if row["hour"] != best["hour"])
    median = others[len(others) // 2]
    gap = best["mean"] - median
    clear = best["mean"] >= median * 1.5 and gap >= 3 and best["mean"] > median
    if clear:
        detail = (
            f"{best['label']} leads with a mean of {best['mean']} engagements (n={best['n']}). "
            f"The next qualified hours sit at a median of {median}."
        )
        nxt = f"Write the next Facebook post for {best['label']} local. The ledger has n={best['n']} there."
    else:
        detail = (
            f"No hour is clearly ahead. {best['label']} is the highest qualified mean "
            f"({best['mean']}, n={best['n']}). The others sit near {median}. "
            "A gap under 3 engagements does not move the schedule."
        )
        nxt = ""
    return {
        "id": "hour",
        "title": "Hours",
        "detail": detail,
        "clear": clear,
        "next": nxt,
        "hour": best["hour"],
        "label": best["label"],
    }


def _trend_lesson(days: list[dict]) -> dict | None:
    rows = [day for day in _page_series(days) if "impressions" in day]
    if len(rows) < 11:
        return None
    last = rows[-7:]
    prev = rows[-14:-7]
    if len(prev) < 4:
        return None
    last_sum = sum(day["impressions"] for day in last)
    prev_sum = sum(day["impressions"] for day in prev)
    if last_sum == 0 and prev_sum == 0:
        return None
    if prev_sum == 0:
        movement = "show up after a quiet week"
    elif last_sum > prev_sum * 1.1:
        movement = "are up"
    elif last_sum < prev_sum * 0.9:
        movement = "are down"
    else:
        movement = "are flat"
    return {
        "id": "trend",
        "title": "Page impressions",
        "detail": (
            f"Organic impressions over the last 7 days {movement}: {last_sum} against {prev_sum} "
            "the 7 days before. These are page totals, not a single post."
        ),
        "clear": movement in {"are up", "are down"},
    }


def _format_lesson(posts: list[dict]) -> dict | None:
    ready = [row for row in format_table(posts) if row["n"] >= MIN_SAMPLE]
    if len(ready) < 2:
        return None
    best = ready[0]
    second = ready[1]
    clear = best["mean"] >= second["mean"] * 1.5 and best["mean"] > second["mean"]
    detail = (
        f"{best['label']} averages {best['mean']} engagements (n={best['n']}). "
        f"{second['label']} averages {second['mean']} (n={second['n']})."
        + ("" if clear else " They are too close to call.")
        + " This is engagements, not an impressions rate."
    )
    return {"id": "format", "title": "Formats", "detail": detail, "clear": clear}


def _lead_lesson(posts: list[dict]) -> dict | None:
    if not posts:
        return None
    lead = max(posts, key=lambda post: int(post.get("engagements") or 0))
    if int(lead.get("engagements") or 0) <= 0:
        return None
    preview = lead.get("preview") or "Untitled"
    return {
        "id": "lead-post",
        "title": "Strongest post in this window",
        "detail": (
            f"{lead['engagements']} engagements "
            f"({lead.get('reactions', 0)} reactions, {lead.get('comments', 0)} comments, "
            f"{lead.get('shares', 0)} shares). {preview}"
        ),
        "clear": False,
        "post_id": lead.get("id"),
    }


def _nonneg(value: object) -> int:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def _normalize_iso(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    matched = _OFFSET.search(text)
    if matched and ":" not in text[-6:]:
        text = text[: matched.start()] + f"{matched.group(1)}{matched.group(2)}:{matched.group(3)}"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return parsed.isoformat()
