"""Studio is read for Misfit Mindset and never written."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapt import DraftError  # noqa: E402
from store import empty_state, load, studio  # noqa: E402
from studio_read import pull_studio  # noqa: E402


def test_studio_read_keeps_the_queue_and_does_not_write(tmp_path: Path):
    path = tmp_path / "state.json"
    calls = []

    def getter(route: str):
        calls.append(route)
        if route == "/api/schedule":
            return {
                "jobs": [
                    {
                        "id": 4,
                        "post_day": "mon",
                        "platform": "facebook",
                        "status": "queued",
                        "scheduled_for_et": "Mon 2026-10-26 09:00 ET",
                        "caption": "Stay. access_token=SECRET",
                        "remote_id": "999",
                        "image_path": "/tmp/card.png",
                    },
                    {"id": 5, "post_day": "tue", "platform": "instagram", "status": "posted", "caption": "Already up."},
                ]
            }
        if route == "/api/meta":
            return {
                "quotes": ["You felt that dread."],
                "day_names": {"mon": "Mindset Monday"},
                "tracks": [{"artist": "A band", "title": "A song", "volume": 3}],
                "weeks": [{"id": 26, "week_number": 1, "cycle_name": "October"}],
                "cycle": {"current_week": 1, "cycle_name": "October"},
                "published": [
                    {
                        "cycle_name": "October",
                        "week_number": 2,
                        "posts": [{"day": "mon", "title": "The fire", "quote_card": "Stay with it.", "body": "A long post."}],
                    }
                ],
            }
        if route == "/api/weeks/26":
            return {
                "cycle_name": "October",
                "week_number": 1,
                "theme_arc": "The fire",
                "posts": [{"day": "mon", "title": "The fire", "quote_card": "Stay with it."}],
                "peak_posts": [{"day": "peak1", "title": "The peak", "quote_card": "Hold the line.", "when": "Wed 14:00"}],
            }
        raise AssertionError(route)

    snap = pull_studio(empty_state(), "misfit-mindset", path, getter)
    assert calls == ["/api/schedule", "/api/meta", "/api/weeks/26"]
    assert snap["writing"] is False
    assert snap["queue"][0]["status"] == "queued"
    assert snap["queue"][0]["caption"].endswith("REDACTED")
    assert "SECRET" not in snap["queue"][0]["caption"]
    assert "remote_id" not in snap["queue"][0]
    assert len(snap["queue"]) == 1
    assert snap["week"]["posts"][0]["title"] == "The fire"
    assert snap["week"]["peaks"][0]["quote_card"] == "Hold the line."
    assert snap["learning"]["quotes"] == 1
    assert "does not write back" in snap["learning"]["detail"]
    assert "Mindset Monday" in snap["learning"]["days"][0]
    saved = studio(load(path), "misfit-mindset")
    assert saved["studio_read"]["linked"] is True
    assert saved["studio_read"]["queue"][0]["day"] == "mon"
    quiet = studio(empty_state(), "josie-blackthorn")
    assert quiet["studio_read"]["linked"] is False
    with pytest.raises(DraftError, match="only read for Misfit"):
        pull_studio(empty_state(), "josie-blackthorn", path, getter)
