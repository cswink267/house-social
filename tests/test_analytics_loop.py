"""Analytics adds a rate only when impressions exist, and a pattern only on a real gap.

pytest imports this. Callers are analytics, import_history, save_goal, and
mark_assisted. History rows and goals live on the brand. The user asked for
the performance loop, including a bulk import of past posts.
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapt import DraftError  # noqa: E402
from learn import analytics  # noqa: E402
from store import create_piece, empty_state, import_history, load, mark_assisted, save_goal, studio  # noqa: E402


TODAY = date(2026, 10, 21)


def _post(name, day, engagements, **extra):
    row = {
        "id": name,
        "preview": extra.pop("preview", "Monday morning still carries the same quiet mark."),
        "published_at": f"{day}T16:00:00+00:00",
        "engagements": engagements,
        "shares": extra.pop("shares", 1),
        "format": extra.pop("format", "unknown"),
        "impressions": extra.pop("impressions", 0),
    }
    row.update(extra)
    return row


def _dates(weekday: int, count: int = 3) -> list[str]:
    day = date(2026, 10, 1)
    found = []
    while len(found) < count:
        if day.weekday() == weekday:
            found.append(day.isoformat())
        day += timedelta(days=1)
    return found


def test_rate_stays_missing_until_impressions_exist_and_patterns_need_a_gap():
    quiet = analytics([_post("one", "2026-10-20", 10)], [], [], today=TODAY, days=7)
    assert quiet["totals"]["rate"] is None
    assert quiet["totals"]["video_completion"] is None
    assert quiet["totals"]["clicks"] is None
    assert quiet["totals"]["comments"] is None
    assert "no rate" in quiet["totals"]["rate_note"].lower()

    rated = analytics(
        [_post("one", "2026-10-20", 10, comments=2, clicks=1, video_completion=40)],
        [{"date": "2026-10-20", "impressions": 100}],
        [],
        today=TODAY,
        days=7,
    )
    assert rated["totals"]["rate"] == 10.0
    assert rated["totals"]["comments"] == 2
    assert rated["totals"]["clicks"] == 1
    assert rated["totals"]["video_completion"] == 40

    mondays = _dates(0)
    tuesdays = _dates(1)
    days = [_post(f"m{i}", mondays[i], 20) for i in range(3)] + [_post(f"t{i}", tuesdays[i], 4) for i in range(3)]
    report = analytics(days, [], [], today=TODAY, days=None)
    weekday = next(item for item in report["patterns"] if item["id"] == "weekday")
    assert weekday["clear"] is True
    assert "Monday" in weekday["detail"]
    assert "%" not in weekday["detail"]

    shaped = [_post(f"f{i}", "2026-10-20", 20, format="feed") for i in range(3)] + [
        _post(f"x{i}", "2026-10-20", 4, format="text") for i in range(3)
    ]
    formats = analytics(shaped, [], [], today=TODAY, days=None)
    assert any("Format feed is ahead" in reason for reason in formats["top"][0]["reasons"])
    assert "hook strength" not in json.dumps(formats["top"][0]["reasons"]).lower()
    assert formats["bottom"][0]["engagements"] == 4

    loud = [_post("big", "2026-10-20", 30)] + [_post(f"s{i}", "2026-10-20", 4) for i in range(3)]
    assert any("3×" in item["detail"] for item in analytics(loud, [], [], today=TODAY, days=None)["alerts"])
    near = [_post("mid", "2026-10-20", 8)] + [_post(f"n{i}", "2026-10-20", 4) for i in range(3)]
    assert analytics(near, [], [], today=TODAY, days=None)["alerts"] == []
    zeros = [_post("z", "2026-10-20", 9)] + [_post(f"z{i}", "2026-10-20", 0) for i in range(3)]
    assert analytics(zeros, [], [], today=TODAY, days=None)["alerts"] == []


def test_assisted_posts_goals_and_history_import(tmp_path: Path):
    pieces = [{"id": f"a{i}", "assisted": True, "pillar": ""} for i in range(3)] + [
        {"id": f"b{i}", "assisted": False, "pillar": ""} for i in range(3)
    ]
    posts = [_post(f"a{i}", "2026-10-20", 20, piece_id=f"a{i}") for i in range(3)] + [
        _post(f"b{i}", "2026-10-20", 4, piece_id=f"b{i}") for i in range(3)
    ]
    assisted = next(item for item in analytics(posts, [], pieces, today=TODAY, days=None)["patterns"] if item["id"] == "assisted")
    assert assisted["clear"] is True
    thin = next(
        item
        for item in analytics(posts[:1], [], pieces[:1], today=TODAY, days=None)["patterns"]
        if item["id"] == "assisted"
    )
    assert thin["clear"] is False
    assert "three" in thin["detail"]

    path = tmp_path / "state.json"
    state = {
        **empty_state(),
        "pulls": {
            "misfit-mindset": {
                "posts": [
                    _post("now", "2026-10-20", 12),
                    _post("then", "2026-10-10", 10),
                ]
            }
        },
    }
    save_goal(state, "misfit-mindset", {"metric": "engagements", "change": 20, "start": "2026-10-15", "end": "2026-10-21"}, path)
    view = studio(load(path), "misfit-mindset", today=TODAY)
    assert "20" in view["performance"]["goals"][0]["detail"]
    assert "meets the goal" in view["performance"]["goals"][0]["detail"]
    save_goal(load(path), "misfit-mindset", {"metric": "saves", "change": 20, "start": "2026-10-15", "end": "2026-10-21"}, path)
    saves = studio(load(path), "misfit-mindset", today=TODAY)["performance"]["goals"][0]
    assert saves["actual"] is None
    assert "not in this pull" in saves["detail"].lower() or "were not" in saves["detail"].lower()

    bare = {**empty_state(), "pulls": {"okay": {"posts": [_post("only", "2026-10-20", 5)]}}}
    save_goal(bare, "okay", {"metric": "engagements", "change": 20, "start": "2026-10-15", "end": "2026-10-21"}, path)
    zero = studio(load(path), "okay", today=TODAY)["performance"]["goals"][0]
    assert "not a real comparison" in zero["detail"]

    imported = import_history(
        empty_state(),
        "blunt",
        "text,date,engagements\nYou felt that dread access_token=SECRET,2026-10-20,15\nNo date here,,4\n",
        path,
    )
    assert imported["used"] == 1
    assert imported["undated"] == 1
    saved = load(path)
    assert saved["pulls"] == {}
    assert "SECRET" not in json.dumps(saved["history"])
    blunt = studio(saved, "blunt", today=TODAY)
    assert blunt["performance"]["ranges"]["all"]["totals"]["engagements"] == 15
    assert blunt["performance"]["imported"] == 1

    voiced = {
        **empty_state(),
        "voice_imports": [
            {"id": "import:dated", "brand_id": "rowan-blackthorn", "preview": "A dated line.", "published_at": "2026-10-20", "engagements": 7, "shares": 0},
            {"id": "import:open", "brand_id": "rowan-blackthorn", "preview": "No day.", "published_at": "", "engagements": 99, "shares": 0},
        ],
    }
    rowan = studio(voiced, "rowan-blackthorn", today=TODAY)
    assert rowan["performance"]["ranges"]["all"]["totals"]["engagements"] == 7

    try:
        import_history(empty_state(), "blunt", "likes,day\n1,2026-10-01\n", path)
    except DraftError as exc:
        assert "text" in str(exc).lower()
    else:
        raise AssertionError("a csv without text was accepted")

    piece = create_piece(empty_state(), "blunt", "Send a file.", path=path)
    assert mark_assisted(load(path), piece["id"], path)["assisted"] is True
