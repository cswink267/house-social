"""Analytics extras for House Social.

Patterns, goals, and imported history. A comparison needs three posts on
both sides and a real gap. A rate exists only when impressions do.

Called by learn.analytics and the history routes. A history row stores the
text, the date, and only the metrics the file actually had. The user asked
for the analytics feedback loop, including historical import.
"""

from __future__ import annotations

import csv
import re
from datetime import date, datetime, timedelta, timezone
from io import StringIO
from zoneinfo import ZoneInfo

from adapt import DraftError
from brands import FORMATS, PLATFORMS
from learn import MIN_SAMPLE, _hour_lesson, _in_window, _local_day, _mean, _totals, format_table
from meta import redact


_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_METRICS = {"engagements", "shares", "saves", "reach", "follows"}
_TEXT = ("text", "message", "caption", "body", "post", "content")


def annotate(posts: list[dict], pieces: list[dict]) -> dict:
    context = _context(posts, pieces)
    ranked = sorted(posts, key=lambda post: int(post.get("engagements") or 0), reverse=True)
    lows = list(reversed(ranked))[:5] if len(ranked) > 1 else []
    return {
        "patterns": _patterns(posts, pieces, context),
        "alerts": _alerts(posts),
        "top": [_public(post, context) for post in ranked[:5]],
        "bottom": [_public(post, context) for post in lows],
    }


def goal_line(goal: dict, posts: list[dict], page_days: list[dict], today: date) -> dict:
    start = date.fromisoformat(str(goal.get("start")))
    finish = min(date.fromisoformat(str(goal.get("end"))), today)
    if finish < start:
        finish = start
    length = (finish - start).days + 1
    baseline_end = start - timedelta(days=1)
    baseline_start = baseline_end - timedelta(days=length - 1)
    metric = str(goal.get("metric") or "")
    current, note = _metric_value(metric, posts, page_days, start, finish)
    previous, _previous_note = _metric_value(metric, posts, page_days, baseline_start, baseline_end)
    change = int(goal.get("change") or 0)
    if current is None or previous is None:
        detail = note or "This metric was not in the pull."
        actual = None
    elif previous == 0:
        detail = (
            f"The stretch before this goal was 0, so a percent is not a real comparison. "
            f"This stretch is {current}."
        )
        actual = None
    else:
        actual = round((current - previous) / previous * 100, 1)
        detail = (
            f"{_metric_label(metric)} is {current} against {previous} before. "
            f"That is {actual} percent. The goal is {change} percent."
        )
        if actual >= change:
            detail += " The change meets the goal."
    return {
        "id": goal.get("id"),
        "metric": metric,
        "change": change,
        "start": goal.get("start"),
        "end": goal.get("end"),
        "current": current,
        "previous": previous,
        "actual": actual,
        "detail": detail,
    }


def parse_history_csv(text: str) -> tuple[list[dict], int]:
    raw = str(text or "")
    if len(raw) > 400_000:
        raise DraftError("That file is too big.")
    reader = csv.DictReader(StringIO(raw))
    if not reader.fieldnames:
        raise DraftError("The CSV needs a header row.")
    fields = {str(name or "").strip().lower(): name for name in reader.fieldnames}
    text_key = next((fields[name] for name in _TEXT if name in fields), None)
    if text_key is None:
        raise DraftError("The CSV needs a text, message, caption, or body column.")
    rows = []
    undated = 0
    for record in reader:
        body = redact(str(record.get(text_key) or "")).strip()
        if not body:
            continue
        published = _date_cell(record, fields)
        if not published:
            undated += 1
        rows.append(_history_row(body, published, record, fields))
        if len(rows) >= 500:
            break
    if not rows:
        raise DraftError("No posts were in that file.")
    return rows, undated


def metric_allowed(metric: str) -> bool:
    return metric in _METRICS


def _history_row(body: str, published: str, record: dict, fields: dict) -> dict:
    engagements = _cell_int(record, fields, ("engagements", "engagement"))
    comments = _cell_int(record, fields, ("comments", "comment"))
    shares = _cell_int(record, fields, ("shares", "share"))
    likes = _cell_int(record, fields, ("likes", "reactions"))
    if engagements is None and any(value is not None for value in (comments, shares, likes)):
        engagements = int(likes or 0) + int(comments or 0) + int(shares or 0)
    platform = str(record.get(fields.get("platform") or "") or "").strip().lower()
    fmt = str(record.get(fields.get("format") or "") or "").strip().lower()
    return {
        "text": body[:500],
        "published_at": published,
        "local_hour": _hour_from(published),
        "engagements": engagements,
        "impressions": _cell_int(record, fields, ("impressions", "impression", "reach")),
        "comments": comments,
        "shares": shares,
        "saves": _cell_int(record, fields, ("saves", "save")),
        "clicks": _cell_int(record, fields, ("clicks", "click", "click_throughs")),
        "video_completion": _cell_int(record, fields, ("video_completion", "completion"), limit=100),
        "platform": platform if platform in PLATFORMS else "",
        "format": fmt if fmt in FORMATS else "unknown",
        "pillar": str(record.get(fields.get("pillar") or "") or "").strip()[:40],
    }


def _patterns(posts: list[dict], pieces: list[dict], context: dict) -> list[dict]:
    return [
        _hour_pattern(posts),
        _weekday_pattern(posts),
        {
            "id": "format",
            "title": "Formats",
            "clear": bool(context.get("format_clear")),
            "detail": context.get("format_detail") or "",
        },
        _pillar_pattern(posts, pieces),
        _split_pattern(posts, "hook", "Hook length", _short_hook, "a short first sentence", "a longer first sentence"),
        _length_pattern(posts),
        _split_pattern(posts, "question", "Questions", lambda post: "?" in str(post.get("preview") or ""), "a question", "no question"),
        _split_pattern(posts, "cta", "Asks or links", _has_cta, "a question or a link", "neither"),
        _assisted_pattern(posts, pieces),
    ]


def _context(posts: list[dict], pieces: list[dict]) -> dict:
    ready = [row for row in format_table(posts) if row["n"] >= MIN_SAMPLE]
    format_clear = False
    format_name = ""
    format_detail = "No format in this window has enough posts to compare."
    if len(ready) >= 2:
        best, second = ready[0], ready[1]
        format_clear = best["mean"] >= second["mean"] * 1.5 and (best["mean"] - second["mean"]) >= 3
        format_name = best["format"]
        format_detail = (
            f"{best['label']} averaged {best['mean']} engagements (n={best['n']}). "
            f"{second['label']} averaged {second['mean']} (n={second['n']})."
        )
        if not format_clear:
            format_detail += " They are too close to call."
    hour = _hour_lesson(posts) or {}
    pillar = _pillar_winner(posts, pieces)
    return {
        "format_clear": format_clear,
        "format_name": format_name,
        "format_detail": format_detail,
        "hour_clear": bool(hour.get("clear")),
        "hour": hour.get("hour"),
        "pillar_clear": bool(pillar and pillar.get("clear")),
        "pillar_name": (pillar or {}).get("name") or "",
        "pieces": pieces,
        "hook_clear": _split_winner(posts, _short_hook) is not None,
        "length_name": (_length_winner(posts) or {}).get("name") or "",
        "length_clear": _length_winner(posts) is not None,
        "question_clear": _split_winner(posts, lambda post: "?" in str(post.get("preview") or "")) is not None,
        "cta_clear": _split_winner(posts, _has_cta) is not None,
    }


def _public(post: dict, context: dict) -> dict:
    return {
        "id": post.get("id") or "",
        "preview": str(post.get("preview") or "")[:140],
        "engagements": int(post.get("engagements") or 0),
        "shares": int(post.get("shares") or 0),
        "saves": post.get("saves"),
        "comments": post.get("comments"),
        "format": post.get("format") or "",
        "platform": post.get("platform") or "",
        "permalink": post.get("permalink") or "",
        "reasons": _reasons(post, context),
    }


def _reasons(post: dict, context: dict) -> list[str]:
    reasons = []
    if context.get("format_clear") and post.get("format") == context.get("format_name"):
        reasons.append(f"Format {context['format_name']} is ahead in this window.")
    if context.get("hour_clear") and post.get("local_hour") == context.get("hour"):
        reasons.append("Posted in the hour that is ahead.")
    if context.get("pillar_clear") and _pillar_of(post, context.get("pieces") or []) == context.get("pillar_name"):
        reasons.append(f"Pillar {context['pillar_name']} is ahead in this window.")
    if context.get("hook_clear") and _short_hook(post):
        reasons.append("The first sentence is short, and that pattern is ahead.")
    if context.get("length_clear") and _length_name(post) == context.get("length_name"):
        reasons.append(f"Length {context['length_name']} is ahead in this window.")
    if context.get("question_clear") and "?" in str(post.get("preview") or ""):
        reasons.append("It asks a question, and that pattern is ahead.")
    if context.get("cta_clear") and _has_cta(post):
        reasons.append("It asks or links, and that pattern is ahead.")
    return reasons or ["No reason is clear from this window."]


def _hour_pattern(posts: list[dict]) -> dict:
    lesson = _hour_lesson(posts)
    if not lesson:
        return {"id": "hour", "title": "Hours", "clear": False, "detail": "Not enough hours to compare."}
    return {"id": "hour", "title": "Hours", "clear": bool(lesson.get("clear")), "detail": lesson.get("detail") or ""}


def _weekday_pattern(posts: list[dict]) -> dict:
    buckets: dict[int, list[int]] = {}
    for post in posts:
        day = _local_day(str(post.get("published_at") or ""))
        if not day:
            continue
        buckets.setdefault(date.fromisoformat(day).weekday(), []).append(int(post.get("engagements") or 0))
    ready = []
    for weekday, values in buckets.items():
        if len(values) >= MIN_SAMPLE:
            ready.append({"weekday": weekday, "label": _WEEKDAYS[weekday], "mean": round(sum(values) / len(values), 1), "n": len(values)})
    if len(ready) < 2:
        return {"id": "weekday", "title": "Days", "clear": False, "detail": "Not enough days have three posts."}
    best = max(ready, key=lambda row: row["mean"])
    others = sorted(row["mean"] for row in ready if row["weekday"] != best["weekday"])
    median = others[len(others) // 2]
    clear = best["mean"] >= median * 1.5 and (best["mean"] - median) >= 3 and best["mean"] > median
    if clear:
        detail = f"{best['label']} leads with a mean of {best['mean']} engagements (n={best['n']}). The next qualified days sit at a median of {median}."
    else:
        detail = f"No day is clearly ahead. {best['label']} is the highest qualified mean ({best['mean']}, n={best['n']}). The others sit near {median}."
    return {"id": "weekday", "title": "Days", "clear": clear, "detail": detail}


def _pillar_pattern(posts: list[dict], pieces: list[dict]) -> dict:
    winner = _pillar_winner(posts, pieces)
    if not winner:
        return {"id": "pillar", "title": "Pillars", "clear": False, "detail": "No post in this window is tied to a pillar."}
    return {"id": "pillar", "title": "Pillars", "clear": bool(winner.get("clear")), "detail": winner["detail"]}


def _pillar_winner(posts: list[dict], pieces: list[dict]) -> dict | None:
    names = []
    tagged = []
    for post in posts:
        name = _pillar_of(post, pieces)
        tagged.append((post, name))
        if name and name not in names:
            names.append(name)
    if not names:
        return None
    best = None
    for name in names:
        inside = [post for post, label in tagged if label == name]
        outside = [post for post, label in tagged if label != name]
        won = _ahead(inside, outside)
        if not won:
            continue
        mean_in, mean_out = won
        gap = mean_in - mean_out
        if best is None or gap > best["gap"]:
            best = {
                "name": name,
                "clear": True,
                "gap": gap,
                "detail": f"{name} averaged {mean_in:.1f} engagements (n={len(inside)}). The other posts averaged {mean_out:.1f} (n={len(outside)}).",
            }
    if best:
        return best
    return {"name": "", "clear": False, "detail": "Pillars are too close to call, or one side still has fewer than three posts."}


def _split_pattern(posts, pattern_id, title, holds, yes_label, no_label) -> dict:
    yes = [post for post in posts if str(post.get("preview") or "") and holds(post)]
    no = [post for post in posts if str(post.get("preview") or "") and not holds(post)]
    won = _ahead(yes, no)
    if not won:
        return {"id": pattern_id, "title": title, "clear": False, "detail": f"{title} wait for three posts with {yes_label} and three without, and a real gap."}
    mean_yes, mean_no = won
    return {
        "id": pattern_id,
        "title": title,
        "clear": True,
        "detail": f"Posts with {yes_label} averaged {mean_yes:.1f} engagements (n={len(yes)}). Posts with {no_label} averaged {mean_no:.1f} (n={len(no)}).",
    }


def _length_pattern(posts: list[dict]) -> dict:
    winner = _length_winner(posts)
    if not winner:
        return {"id": "length", "title": "Length", "clear": False, "detail": "Length is too close to call, or one side still has fewer than three posts."}
    return {"id": "length", "title": "Length", "clear": True, "detail": winner["detail"]}


def _length_winner(posts: list[dict]) -> dict | None:
    buckets: dict[str, list[dict]] = {"short": [], "middle": [], "long": []}
    for post in posts:
        name = _length_name(post)
        if name:
            buckets[name].append(post)
    best = None
    for name, inside in buckets.items():
        outside = [post for post in posts if _length_name(post) and _length_name(post) != name]
        won = _ahead(inside, outside)
        if not won:
            continue
        mean_in, mean_out = won
        gap = mean_in - mean_out
        if best is None or gap > best["gap"]:
            best = {
                "name": name,
                "gap": gap,
                "detail": f"{name} posts averaged {mean_in:.1f} engagements (n={len(inside)}). The other lengths averaged {mean_out:.1f} (n={len(outside)}).",
            }
    return best


def _assisted_pattern(posts: list[dict], pieces: list[dict]) -> dict:
    assisted = {piece.get("id") for piece in pieces if piece.get("assisted")}
    yes = [post for post in posts if post.get("piece_id") in assisted]
    no = [post for post in posts if post.get("piece_id") not in assisted]
    won = _ahead(yes, no)
    if not won:
        return {
            "id": "assisted",
            "title": "Assisted drafts",
            "clear": False,
            "detail": f"{len(yes)} posts came from a draft the assistant touched. A comparison waits for three of those and three others, and a real gap.",
        }
    mean_yes, mean_no = won
    return {
        "id": "assisted",
        "title": "Assisted drafts",
        "clear": True,
        "detail": f"Posts from assisted drafts averaged {mean_yes:.1f} engagements (n={len(yes)}). The others averaged {mean_no:.1f} (n={len(no)}).",
    }


def _alerts(posts: list[dict]) -> list[dict]:
    found = []
    for post in posts:
        others = [item for item in posts if item.get("id") != post.get("id")]
        if len(others) < MIN_SAMPLE:
            continue
        mean = _mean(others)
        engagements = int(post.get("engagements") or 0)
        if mean <= 0 or engagements < mean * 3 or (engagements - mean) < 3:
            continue
        found.append(
            {
                "id": post.get("id") or "",
                "preview": str(post.get("preview") or "")[:140],
                "engagements": engagements,
                "detail": (
                    f"This post reached {engagements} engagements. The other posts averaged {mean:.1f} (n={len(others)}). "
                    "That is at least 3×. Worth a series if you want more of this."
                ),
            }
        )
    found.sort(key=lambda item: item["engagements"], reverse=True)
    return found[:3]


def _ahead(yes: list[dict], no: list[dict]) -> tuple[float, float] | None:
    if len(yes) < MIN_SAMPLE or len(no) < MIN_SAMPLE:
        return None
    mean_yes = _mean(yes)
    mean_no = _mean(no)
    if mean_yes <= mean_no or mean_yes < mean_no * 1.5 or (mean_yes - mean_no) < 3:
        return None
    return mean_yes, mean_no


def _split_winner(posts: list[dict], holds) -> dict | None:
    yes = [post for post in posts if str(post.get("preview") or "") and holds(post)]
    no = [post for post in posts if str(post.get("preview") or "") and not holds(post)]
    if _ahead(yes, no) is None:
        return None
    return {"clear": True}


def _metric_value(metric: str, posts: list[dict], page_days: list[dict], start: date, end: date) -> tuple[int | None, str]:
    window_posts = [post for post in posts if _in_window(_local_day(str(post.get("published_at") or "")), start, end)]
    window_days = [day for day in page_days if _in_window(str(day.get("date") or ""), start, end)]
    totals = _totals(window_posts, window_days)
    if metric == "engagements":
        return totals["engagements"], ""
    if metric == "shares":
        return totals["shares"], ""
    if metric == "saves":
        return totals["saves"], totals["saves_note"]
    if metric == "reach":
        return totals["reach"], totals["reach_note"]
    if metric == "follows":
        return totals["growth"], totals["growth_note"]
    return None, "That metric is not on this desk."


def _metric_label(metric: str) -> str:
    return {"engagements": "Engagements", "shares": "Shares", "saves": "Saves", "reach": "Reach", "follows": "Follower change"}.get(metric, metric)


def _pillar_of(post: dict, pieces: list[dict]) -> str:
    if post.get("pillar"):
        return str(post.get("pillar") or "")
    piece_id = str(post.get("piece_id") or "")
    if not piece_id:
        return ""
    piece = next((item for item in pieces if item.get("id") == piece_id), None)
    return str((piece or {}).get("pillar") or "")


def _short_hook(post: dict) -> bool:
    sentence = re.split(r"(?<=[.!?])\s+", str(post.get("preview") or "").strip(), maxsplit=1)[0]
    count = len(re.findall(r"[A-Za-z0-9']+", sentence))
    return 0 < count <= 8


def _length_name(post: dict) -> str:
    count = len(re.findall(r"[A-Za-z0-9']+", str(post.get("preview") or "")))
    if count <= 0:
        return ""
    if count <= 12:
        return "short"
    if count <= 40:
        return "middle"
    return "long"


def _has_cta(post: dict) -> bool:
    text = str(post.get("preview") or "").lower()
    return "?" in text or "http://" in text or "https://" in text


def _date_cell(record: dict, fields: dict) -> str:
    key = fields.get("date") or fields.get("published_at") or fields.get("published")
    text = str(record.get(key) or "").strip() if key else ""
    if re.match(r"\d{4}-\d{2}-\d{2}", text):
        return text[:40]
    return ""


def _cell_int(record: dict, fields: dict, names: tuple[str, ...], limit: int = 10_000_000) -> int | None:
    key = next((fields[name] for name in names if name in fields), None)
    if key is None:
        return None
    text = str(record.get(key) or "").strip().replace(",", "")
    if not re.fullmatch(r"\d+", text):
        return None
    number = int(text)
    if number > limit:
        return None
    return number


def _hour_from(published: str) -> int | None:
    if "T" not in str(published or ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(published).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(ZoneInfo("America/New_York")).hour


def read_draft(text: str, posts: list[dict]) -> dict:
    """What the posts can say about a draft. No predicted score."""
    body = str(text or "").strip()
    context = _context(posts, [])
    found = {item["id"]: item for item in _patterns(posts, [], context)}
    misses = []
    lines = []
    if body:
        _match(found, "hook", _short_hook({"preview": body}), "The first sentence is longer than the pattern that is ahead.", lines, misses)
        _match(found, "question", "?" in body, "This draft does not ask a question.", lines, misses)
        _match(found, "cta", _has_cta({"preview": body}), "This draft does not ask or link.", lines, misses)
        _match(
            found,
            "length",
            _length_name({"preview": body}) == (context.get("length_name") or ""),
            "The length is not the one that is ahead.",
            lines,
            misses,
        )
    clear = any(item.get("clear") for item in found.values() if item.get("id") in {"hook", "question", "cta", "length"})
    if not body:
        improve = "Write a draft before asking to improve it."
        misses = []
    elif not clear:
        improve = "Nothing learned is clear enough to change this draft."
        misses = []
    elif not misses:
        improve = "This draft already matches the patterns that are ahead."
    else:
        improve = "These are the patterns this draft misses."
    hook = found.get("hook") or {}
    cta = found.get("cta") or {}
    return {
        "lines": lines,
        "misses": misses[:6],
        "improve": improve,
        "hook": hook.get("detail") or "Hook length is not a pattern yet.",
        "cta": cta.get("detail") if cta.get("clear") else "A question or a link is not a pattern yet.",
        "similar": _similar(body, posts),
        "remix": _remix_post(posts),
    }


def remix_source(posts: list[dict], text: str) -> dict:
    found = _remix_post(posts)
    if not found["ready"]:
        raise DraftError(found["detail"])
    if str(text or "").strip() != found["preview"].strip():
        raise DraftError("That post is not ahead of the others.")
    return found


def _match(found: dict, pattern_id: str, holds: bool, miss: str, lines: list[str], misses: list[str]) -> None:
    pattern = found.get(pattern_id) or {}
    if not pattern.get("clear"):
        return
    if holds:
        lines.append(pattern.get("detail") or "")
    else:
        misses.append((miss + " " + (pattern.get("detail") or "")).strip())


def _similar(text: str, posts: list[dict]) -> list[dict]:
    words = set(re.findall(r"[a-z0-9']{4,}", text.lower())) - _DRAFT_STOP
    rows = []
    ahead = {item.get("id") for item in _alerts(posts)}
    for post in posts:
        preview = str(post.get("preview") or "").strip()
        if not preview or post.get("engagements") is None:
            continue
        if preview.lower() == text.strip().lower():
            continue
        shared = words & set(re.findall(r"[a-z0-9']{4,}", preview.lower()))
        if not shared:
            continue
        rows.append(
            {
                "id": post.get("id") or "",
                "preview": preview[:140],
                "engagements": int(post.get("engagements") or 0),
                "ahead": post.get("id") in ahead,
            }
        )
    rows.sort(key=lambda item: item["engagements"], reverse=True)
    return rows[:3]


def _remix_post(posts: list[dict]) -> dict:
    alerts = _alerts(posts)
    if not alerts:
        return {
            "ready": False,
            "detail": "No post is at least 3× the others, so there is nothing to remix.",
            "id": "",
            "preview": "",
            "engagements": 0,
        }
    top = alerts[0]
    return {
        "ready": True,
        "detail": top.get("detail") or "",
        "id": top.get("id") or "",
        "preview": top.get("preview") or "",
        "engagements": int(top.get("engagements") or 0),
    }


_DRAFT_STOP = {
    "that", "this", "with", "from", "your", "have", "just", "what", "when", "were",
    "been", "about", "into", "than", "then", "there", "their", "would", "could",
    "still", "same", "them", "they", "morning", "today",
}
