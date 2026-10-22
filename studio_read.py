"""Read-only pull from Studio for Misfit Mindset.

Called by store._studio_read_view and the dashboard route
POST /brands/misfit-mindset/studio-read. The route only GETs
/api/schedule and /api/meta. It does not write to Studio.
A saved snapshot lives on state["studio_reads"]["misfit-mindset"].
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from adapt import DraftError
from meta import redact

STUDIO_SITE = "https://studio.misfitmindset.com"
STUDIO_READ = os.environ.get("HOUSE_SOCIAL_STUDIO_URL", "http://127.0.0.1:3317").rstrip("/")
_WEEK = re.compile(r"/api/weeks/[0-9]+")
_BRAND = "misfit-mindset"


def studio_view(state: dict, brand_id: str) -> dict:
    if brand_id != _BRAND:
        return {"linked": False, "writing": False}
    saved = (state.get("studio_reads") or {}).get(_BRAND) or {}
    base = _shell()
    if not saved:
        return base
    return {**base, **saved, "linked": True, "writing": False}


def pull_studio(state: dict, brand_id: str, path: Path | None = None, getter=None) -> dict:
    if brand_id != _BRAND:
        raise DraftError("Studio is only read for Misfit Mindset.")
    get = getter or _http_get
    try:
        schedule = get("/api/schedule")
        meta_body = get("/api/meta")
        week_id = _week_id(meta_body)
        week = get(f"/api/weeks/{week_id}") if week_id else {}
    except DraftError:
        raise
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise DraftError("Studio did not answer. Nothing was written there.") from exc
    if not isinstance(schedule, dict) or not isinstance(meta_body, dict):
        raise DraftError("Studio did not answer. Nothing was written there.")
    snap = _shape(schedule, meta_body, week if isinstance(week, dict) else {})
    from store import save

    updated = {**state, "studio_reads": {**(state.get("studio_reads") or {}), _BRAND: snap}}
    save(updated, path)
    return snap


def _shell() -> dict:
    return {
        "linked": True,
        "writing": False,
        "url": STUDIO_SITE,
        "cards_url": STUDIO_SITE + "/cards",
        "pulled_at": "",
        "queue": [],
        "week": {"cycle": "", "number": None, "arc": "", "posts": [], "peaks": []},
        "quotes": [],
        "cards": [],
        "tracks": [],
        "published": [],
        "learning": {
            "quotes": 0,
            "published_posts": 0,
            "days": [],
            "detail": "Nothing has been read from Studio yet.",
        },
    }


def _week_id(meta_body: dict) -> int | None:
    cycle = meta_body.get("cycle") if isinstance(meta_body.get("cycle"), dict) else {}
    name = str(cycle.get("cycle_name") or "").strip().lower()
    number = cycle.get("current_week")
    weeks = [item for item in meta_body.get("weeks") or [] if isinstance(item, dict) and isinstance(item.get("id"), int)]
    for item in weeks:
        if isinstance(number, int) and item.get("week_number") == number and str(item.get("cycle_name") or "").strip().lower() == name:
            return int(item["id"])
    return int(weeks[0]["id"]) if weeks else None


def _post_line(post: dict) -> dict:
    return {
        "day": _clean(post.get("day"), 16),
        "title": _clean(post.get("title") or post.get("header"), 120),
        "quote_card": _clean(post.get("quote_card"), 240),
        "when": _clean(post.get("when"), 40),
    }


def _shape(schedule: dict, meta_body: dict, week: dict) -> dict:
    quotes = [_clean(item, 240) for item in list(meta_body.get("quotes") or []) if str(item or "").strip()]
    cards = []
    published = []
    for item in list(meta_body.get("published") or [])[:4]:
        if not isinstance(item, dict):
            continue
        cycle = _clean(item.get("cycle_name"), 80)
        number = item.get("week_number")
        for post in list(item.get("posts") or [])[:8]:
            if not isinstance(post, dict):
                continue
            card = _clean(post.get("quote_card"), 240)
            if card and card not in cards:
                cards.append(card)
            published.append(
                {
                    "cycle": cycle,
                    "week": number if isinstance(number, int) else None,
                    "day": _clean(post.get("day"), 16),
                    "title": _clean(post.get("title") or post.get("header"), 120),
                    "quote_card": card,
                }
            )
    for post in list(week.get("posts") or []) + list(week.get("peak_posts") or []):
        if isinstance(post, dict):
            card = _clean(post.get("quote_card"), 240)
            if card and card not in cards:
                cards.append(card)
    tracks = []
    for track in list(meta_body.get("tracks") or [])[-8:]:
        if not isinstance(track, dict):
            continue
        tracks.append(
            {
                "artist": _clean(track.get("artist"), 80),
                "title": _clean(track.get("title"), 120),
                "volume": track.get("volume") if isinstance(track.get("volume"), int) else None,
            }
        )
    days = meta_body.get("day_names") if isinstance(meta_body.get("day_names"), dict) else {}
    day_line = [f"{_clean(key, 16)} {_clean(value, 40)}" for key, value in list(days.items())[:8]]
    queue = []
    for job in list(schedule.get("jobs") or []):
        if not isinstance(job, dict):
            continue
        status = _clean(job.get("status"), 24).lower()
        if status not in {"queued", "posting", "failed"}:
            continue
        queue.append(
            {
                "id": job.get("id") if isinstance(job.get("id"), int) else None,
                "day": _clean(job.get("post_day"), 16),
                "platform": _clean(job.get("platform"), 16),
                "when": _clean(job.get("scheduled_for_et") or job.get("scheduled_for"), 40),
                "status": status,
                "caption": _clean(job.get("caption"), 180),
            }
        )
        if len(queue) == 24:
            break
    held = {
        "cycle": _clean(week.get("cycle_name"), 80),
        "number": week.get("week_number") if isinstance(week.get("week_number"), int) else None,
        "arc": _clean(week.get("theme_arc"), 160),
        "posts": [_post_line(post) for post in list(week.get("posts") or [])[:8] if isinstance(post, dict)],
        "peaks": [_post_line(post) for post in list(week.get("peak_posts") or [])[:6] if isinstance(post, dict)],
    }
    detail = (
        f"{len(quotes)} used quotes and {len(published)} published posts are on Studio. "
        "This desk reads them. It does not write back, and it does not send the queue."
    )
    if not quotes and not published and not queue and not held["posts"] and not held["peaks"]:
        detail = "Studio answered, and it has no queue, quotes, or published posts yet."
    return {
        "linked": True,
        "writing": False,
        "url": STUDIO_SITE,
        "cards_url": STUDIO_SITE + "/cards",
        "pulled_at": datetime.now(timezone.utc).isoformat(),
        "queue": queue,
        "week": held,
        "quotes": quotes[-12:],
        "cards": cards[:12],
        "tracks": tracks,
        "published": published[:12],
        "learning": {
            "quotes": len(quotes),
            "published_posts": len(published),
            "days": day_line,
            "detail": detail,
        },
    }


def _clean(value, limit: int) -> str:
    return redact(" ".join(str(value or "").split()))[:limit]


def _allowed(path: str) -> bool:
    return path in {"/api/schedule", "/api/meta"} or bool(_WEEK.fullmatch(path))


def _http_get(path: str) -> dict:
    if not _allowed(path):
        raise DraftError("That Studio path is not read.")
    request = urllib.request.Request(STUDIO_READ + path, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise DraftError("Studio did not answer. Nothing was written there.") from exc
    if not isinstance(body, dict):
        raise DraftError("Studio did not answer. Nothing was written there.")
    return body
