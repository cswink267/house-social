"""Analytics keeps a missing number missing, and compares only real windows."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from learn import analytics  # noqa: E402


TODAY = date(2026, 10, 21)


def _post(name, day, engagements, **extra):
    row = {
        "id": name,
        "preview": name,
        "published_at": f"{day}T16:00:00+00:00",
        "engagements": engagements,
        "shares": extra.pop("shares", 1),
        "format": extra.pop("format", "feed"),
        "impressions": extra.pop("impressions", 0),
    }
    row.update(extra)
    return row


def test_analytics_compares_windows_and_refuses_a_thin_campaign():
    posts = [
        _post("now", "2026-10-20", 18, shares=3, format="quote-image"),
        _post("then", "2026-10-10", 4, shares=1, format="feed"),
        _post("old", "2026-09-01", 9, format="text"),
    ]
    days = [{"date": "2026-10-20", "impressions": 100, "follows": 5, "unfollows": 2}]
    pieces = [{"id": "piece-1", "campaign": "October"}]
    thin = posts + [_post("camp", "2026-10-19", 20, piece_id="piece-1")]
    report = analytics(thin, days, pieces, today=TODAY, days=7)
    assert report["totals"]["engagements"] == 38
    assert report["totals"]["reach"] == 100
    assert report["totals"]["saves"] is None
    assert "not in this pull" in report["totals"]["saves_note"].lower()
    assert report["totals"]["growth"] == 3
    assert any("38" in line and "4" in line for line in report["comparison"]["lines"])
    assert report["campaigns"][0]["clear"] is False
    assert "October" in report["campaigns"][0]["detail"]
    assert report["top"][0]["engagements"] == 20
    assert {item["format"] for item in report["formats"]} == {"quote-image", "feed"}

    inside = [_post(f"in{i}", "2026-10-20", 20, piece_id="piece-1") for i in range(3)]
    outside = [_post(f"out{i}", "2026-10-19", 4) for i in range(3)]
    clear = analytics(inside + outside, [], pieces, today=TODAY, days=7)
    assert clear["totals"]["reach"] is None
    campaign = next(item for item in clear["campaigns"] if item["name"] == "October")
    assert campaign["clear"] is True
    assert "20.0" in campaign["detail"]

    whole = analytics(posts, [], [], today=TODAY, days=None)
    assert whole["totals"]["engagements"] == 31
    assert whole["comparison"]["lines"] == ["There is no earlier window to set beside the full history."]
