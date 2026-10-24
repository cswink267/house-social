"""Display-only engagement map for one brand.

Callers: studio and the Map desk. Numbers come from stored posts and
page days. A missing metric stays missing. Nothing is sent. The user
said continue, and this is the engagement-map item.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from learn import _local_day


_ZONE = ZoneInfo("America/New_York")
_PLATFORMS = ("facebook", "instagram", "threads")
_WINDOWS = (7, 28, 90)
_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def map_for(posts: list[dict], page_days: list[dict] | None = None, today=None) -> dict:
    when = today or datetime.now(_ZONE).date()
    days = list(page_days or [])
    return {
        "windows": {str(size): _window(posts, days, when, size) for size in _WINDOWS},
        "posts": [_post_card(post) for post in _dated(posts)][:40],
        "hourly": False,
        "demographics": False,
    }


def _window(posts: list[dict], page_days: list[dict], today, size: int) -> dict:
    start = today - timedelta(days=size - 1)
    prior_start = start - timedelta(days=size)
    current = [post for post in _dated(posts) if start.isoformat() <= _local_day(post["published_at"]) <= today.isoformat()]
    prior = [post for post in _dated(posts) if prior_start.isoformat() <= _local_day(post["published_at"]) < start.isoformat()]
    return {
        "days": size,
        "series": _series(current, start, today),
        "cards": {name: _card(name, current) for name in _PLATFORMS},
        "change": _change(current, prior),
        "followers": _followers(page_days, start, today),
        "formats": _formats(current),
        "heatmap": _heatmap(current),
        "top": [_top(post) for post in sorted(current, key=lambda post: int(post.get("engagements") or 0), reverse=True)[:8]],
        "rates": _rates(current, prior),
    }


def _series(posts: list[dict], start, today) -> list[dict]:
    found = []
    for name in _PLATFORMS:
        mine = [post for post in posts if post.get("platform") == name]
        if not mine:
            continue
        points = []
        day = start
        while day <= today:
            key = day.isoformat()
            values = [int(post.get("engagements") or 0) for post in mine if _local_day(post.get("published_at") or "") == key]
            if values:
                points.append({"date": key, "value": sum(values)})
            day += timedelta(days=1)
        if points:
            found.append({"platform": name, "points": points})
    return found


def _card(platform: str, posts: list[dict]) -> dict:
    mine = [post for post in posts if post.get("platform") == platform]
    if not mine:
        return {"platform": platform, "detail": "No numbers in this window.", "rows": []}
    rows = []
    engagements = _sum(mine, "engagements")
    if engagements is not None:
        rows.append({"label": "Engagements", "value": engagements})
    for key, label in _fields(platform):
        value = _present(mine, key)
        if value is None:
            continue
        rows.append({"label": label, "value": value})
    if _present(mine, "impressions") is None:
        rows.append({"label": "Reach", "value": None})
    return {"platform": platform, "detail": "", "rows": rows}


def _fields(platform: str) -> tuple:
    if platform == "instagram":
        return (("reactions", "Likes"), ("comments", "Comments"), ("saves", "Saves"), ("shares", "Shares"), ("video_views", "Reel plays"))
    if platform == "threads":
        return (("reactions", "Likes"), ("comments", "Replies"), ("shares", "Reposts"))
    return (("reactions", "Reactions"), ("comments", "Comments"), ("shares", "Shares"), ("clicks", "Link clicks"))


def _change(current: list[dict], prior: list[dict]) -> list[dict]:
    rows = []
    for name in _PLATFORMS:
        now = _sum([post for post in current if post.get("platform") == name], "engagements")
        then = _sum([post for post in prior if post.get("platform") == name], "engagements")
        if now is None or then is None:
            continue
        if then == 0:
            detail = f"The prior window was 0, so a percent is not a comparison. This window is {now}."
            percent = None
        else:
            percent = round((now - then) / then * 100, 1)
            detail = f"This window is {now} against {then} before. That is {percent} percent."
        rows.append({"platform": name, "detail": detail, "percent": percent})
    return rows


def _followers(page_days: list[dict], start, today) -> list[dict]:
    wanted = [day for day in page_days if start.isoformat() <= str(day.get("date") or "") <= today.isoformat()]
    follows = _day_sum(wanted, "follows")
    leaves = _day_sum(wanted, "unfollows")
    if follows is None and leaves is None:
        return []
    parts = []
    if follows is not None:
        parts.append(f"Follows {follows}")
    if leaves is not None:
        parts.append(f"Unfollows {leaves}")
    if follows is not None and leaves is not None:
        parts.append(f"Net {follows - leaves}")
    return [{"platform": "facebook", "detail": ". ".join(parts) + "."}]


def _formats(posts: list[dict]) -> list[dict]:
    buckets: dict[str, list[dict]] = {}
    for post in posts:
        name = str(post.get("format") or "")
        if not name or name == "unknown":
            continue
        buckets.setdefault(name, []).append(post)
    cards = []
    for name, group in sorted(buckets.items()):
        if len(group) < 3:
            cards.append({"format": name, "n": len(group), "mean": None, "detail": f"This is thin. Based on {len(group)} posts."})
            continue
        mean = round(sum(int(post.get("engagements") or 0) for post in group) / len(group), 1)
        cards.append({"format": name, "n": len(group), "mean": mean, "reach": _mean_present(group, "impressions"), "detail": f"Average {mean} engagements (n={len(group)})."})
    return cards


def _heatmap(posts: list[dict]) -> list[dict]:
    buckets: dict[tuple[int, int], list[int]] = {}
    for post in posts:
        day = _local_day(str(post.get("published_at") or ""))
        hour = post.get("local_hour")
        if not day or not isinstance(hour, int):
            continue
        buckets.setdefault((datetime.fromisoformat(day).weekday(), hour), []).append(int(post.get("engagements") or 0))
    return [
        {"weekday": _WEEKDAYS[weekday], "hour": f"{hour:02d}:00", "n": len(values), "mean": round(sum(values) / len(values), 1)}
        for (weekday, hour), values in sorted(buckets.items())
    ]


def _rates(current: list[dict], prior: list[dict]) -> list[dict]:
    rows = []
    for label, num_key in (("Engagement rate", "engagements"), ("Save rate", "saves")):
        now = _ratio(current, num_key, "impressions")
        then = _ratio(prior, num_key, "impressions")
        if now is None:
            continue
        detail = f"{label}: {now['num']} over {now['den']} impressions."
        if then is not None:
            detail += f" The prior window was {then['num']} over {then['den']}."
        rows.append({"label": label, "detail": detail})
    return rows


def _top(post: dict) -> dict:
    impressions = post.get("impressions")
    engagements = post.get("engagements")
    rate = None
    if isinstance(impressions, int) and impressions > 0 and engagements is not None:
        rate = round(int(engagements) / impressions * 100, 1)
    return {
        "id": post.get("id") or "",
        "platform": post.get("platform") or "",
        "format": post.get("format") or "",
        "preview": str(post.get("preview") or "")[:80],
        "engagements": engagements,
        "saves": post.get("saves") if post.get("saves") is not None else None,
        "shares": post.get("shares") if "shares" in post else None,
        "rate": rate,
        "at": _local_day(str(post.get("published_at") or "")),
    }


def _post_card(post: dict) -> dict:
    parts = []
    for key, label in (("reactions", "Reactions"), ("comments", "Comments"), ("shares", "Shares"), ("saves", "Saves"), ("clicks", "Clicks")):
        if post.get(key) is None:
            continue
        if key == "shares" and int(post.get(key) or 0) == 0 and post.get("platform") != "facebook":
            continue
        parts.append({"label": label, "value": int(post.get(key) or 0)})
    return {
        "id": post.get("id") or "",
        "platform": post.get("platform") or "",
        "format": post.get("format") or "",
        "preview": str(post.get("preview") or "")[:140],
        "at": str(post.get("published_at") or ""),
        "engagements": post.get("engagements"),
        "impressions": post.get("impressions") if isinstance(post.get("impressions"), int) and int(post.get("impressions") or 0) > 0 else None,
        "parts": parts,
        "hourly": False,
    }


def _dated(posts: list[dict]) -> list[dict]:
    return [post for post in posts if post.get("published_at") and post.get("engagements") is not None]


def _sum(posts: list[dict], key: str) -> int | None:
    if not posts:
        return None
    return sum(int(post.get(key) or 0) for post in posts)


def _present(posts: list[dict], key: str) -> int | None:
    values = [post.get(key) for post in posts if post.get(key) is not None]
    if not values:
        return None
    if key == "impressions" and all(int(value or 0) == 0 for value in values):
        return None
    return sum(int(value or 0) for value in values)


def _mean_present(posts: list[dict], key: str) -> float | None:
    values = [int(post.get(key)) for post in posts if isinstance(post.get(key), int) and int(post.get(key) or 0) > 0]
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def _day_sum(days: list[dict], key: str) -> int | None:
    values = [day.get(key) for day in days if day.get(key) is not None]
    if not values:
        return None
    return sum(int(value or 0) for value in values)


def _ratio(posts: list[dict], num_key: str, den_key: str) -> dict | None:
    den = _present(posts, den_key)
    values = [post.get(num_key) for post in posts if post.get(num_key) is not None]
    if den is None or not values:
        return None
    return {"num": sum(int(value or 0) for value in values), "den": den}
