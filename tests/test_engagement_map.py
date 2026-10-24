"""The map draws only stored numbers.

pytest imports this. Callers are map_for. The user said continue.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engagement_map import map_for  # noqa: E402


TODAY = date(2026, 10, 24)


def _post(name, platform, engagements, day, fmt="feed", impressions=0, saves=None):
    return {
        "id": name,
        "platform": platform,
        "preview": "SECRET-CAPTION-" + name,
        "published_at": f"2026-10-{day}T15:00:00-04:00",
        "local_hour": 11,
        "engagements": engagements,
        "reactions": engagements,
        "comments": 0,
        "shares": 0,
        "impressions": impressions,
        "saves": saves,
        "format": fmt,
        "source": "history",
    }


def test_a_platform_with_no_posts_stays_blank_and_zero_reach_is_not_a_rate():
    posts = [_post(f"f{i}", "facebook", 10, 20 + i) for i in range(3)]
    found = map_for(posts, [{"date": "2026-10-22", "follows": 2, "unfollows": 1}], today=TODAY)
    week = found["windows"]["7"]
    assert week["cards"]["instagram"]["detail"] == "No numbers in this window."
    assert week["cards"]["threads"]["detail"] == "No numbers in this window."
    assert any(row["label"] == "Reach" and row["value"] is None for row in week["cards"]["facebook"]["rows"])
    assert all(item["rate"] is None for item in week["top"])
    assert found["hourly"] is False
    assert found["demographics"] is False
    assert week["followers"][0]["detail"].startswith("Follows 2")
    thin = map_for([_post("one", "facebook", 3, 22, fmt="reel"), _post("two", "facebook", 5, 23, fmt="reel")], today=TODAY)
    card = thin["windows"]["28"]["formats"][0]
    assert card["mean"] is None
    assert card["detail"].startswith("This is thin.")
    dumped = json.dumps(found)
    assert "cities" not in dumped
    assert "age band" not in dumped


def test_a_real_prior_window_can_name_a_percent_and_three_posts_can_average():
    posts = [_post(f"n{i}", "facebook", 20, 22, impressions=100, saves=5) for i in range(3)]
    posts += [_post(f"p{i}", "facebook", 10, 12, impressions=50, saves=1) for i in range(3)]
    found = map_for(posts, today=TODAY)
    change = found["windows"]["7"]["change"][0]
    assert change["percent"] is not None
    assert "against" in change["detail"]
    formats = [item for item in found["windows"]["28"]["formats"] if item["format"] == "feed"]
    assert formats[0]["n"] >= 3
    assert formats[0]["mean"] is not None
    assert "over" in found["windows"]["28"]["rates"][0]["detail"]
    assert "impressions" in found["windows"]["28"]["rates"][0]["detail"]
