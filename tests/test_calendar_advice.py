"""The calendar names a real gap and a real slot.

pytest imports this. Callers are advise, save_recurrence, and apply_recurrence.
Advice stores gap lines, a mix, warnings, and a slot. The user asked the
calendar to plan from what the posts already showed.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapt import DraftError  # noqa: E402
from calendar_desk import advise  # noqa: E402
from store import apply_recurrence, empty_state, load, save_recurrence, studio  # noqa: E402


TODAY = date(2026, 10, 21)


def _post(name, engagements, hour, fmt):
    return {
        "id": name,
        "preview": name,
        "published_at": "2026-10-20T16:00:00+00:00",
        "local_hour": hour,
        "engagements": engagements,
        "format": fmt,
    }


def test_gaps_name_missing_pillars_and_slots_wait_for_a_real_hour():
    pillars = [{"id": "raw-truth", "name": "Raw truth"}, {"id": "music", "name": "Music"}]
    entries = [{"kind": "piece", "date": "2026-10-23", "pillar": "raw-truth", "format": "feed"}]
    found = advise(entries, pillars, [], TODAY)
    assert any("Music" in line for line in found["gaps"])
    assert all("educational" not in line.lower() for line in found["gaps"])
    assert not any("have no Raw truth" in line for line in found["gaps"])
    assert found["mix"][0]["n"] == 1
    assert found["slot"]["clear"] is False
    assert found["warnings"] == []

    posts = [_post(f"a{i}", 30, 9, "feed") for i in range(3)] + [_post(f"b{i}", 4, 15, "text") for i in range(3)]
    heavy = [
        {"kind": "piece", "date": "2026-10-23", "pillar": "music", "format": "text"},
        {"kind": "piece", "date": "2026-10-24", "pillar": "music", "format": "text"},
    ]
    warned = advise(heavy, pillars, posts, TODAY)
    assert warned["slot"]["clear"] is True
    assert warned["slot"]["hour"] == 9
    assert warned["warnings"]
    assert "text" in warned["warnings"][0]
    assert "feed" in warned["warnings"][0]
    quiet = advise(
        [{"kind": "piece", "date": "2026-10-23", "pillar": "raw-truth", "format": "feed"}],
        pillars,
        posts,
        TODAY,
    )
    assert quiet["warnings"] == []


def test_recurrence_holds_future_weekdays_and_does_not_repeat(tmp_path: Path):
    path = tmp_path / "state.json"
    try:
        save_recurrence(empty_state(), "misfit-mindset", {"name": "Monday", "idea": "You felt it.", "weekday": 0, "weeks": 9}, path)
    except DraftError as exc:
        assert "8" in str(exc)
    else:
        raise AssertionError("nine weeks was accepted")
    row = save_recurrence(empty_state(), "misfit-mindset", {"name": "Monday", "idea": "You felt it.", "weekday": 0, "weeks": 2}, path)
    first = apply_recurrence(load(path), "misfit-mindset", row["id"], path, today=TODAY)
    assert first["created"] == 2
    pieces = [piece for piece in load(path)["pieces"] if piece.get("recurrence_id") == row["id"]]
    assert len(pieces) == 2
    assert all(piece["status"] == "planned" for piece in pieces)
    assert sorted(piece["scheduled_for"][:10] for piece in pieces) == ["2026-10-26", "2026-11-02"]
    second = apply_recurrence(load(path), "misfit-mindset", row["id"], path, today=TODAY)
    assert second["created"] == 0
    view = studio(load(path), "misfit-mindset", today=TODAY)
    assert view["calendar"]["recurrences"][0]["name"] == "Monday"
    assert any("have no" in line for line in view["calendar"]["advice"]["gaps"])
