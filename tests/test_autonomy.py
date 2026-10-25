"""A brand that is not manual makes one post a day without a person.

pytest imports this. The dashboard worker calls run_daily.
State key mode_runs maps a brand id to a New York day, YYYY-MM-DD.
The user said autonomous brands should create and publish on their own.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from autonomy import run_daily  # noqa: E402
from modes import set_mode  # noqa: E402
from store import empty_state, load, save  # noqa: E402

WHEN = datetime(2026, 10, 24, 9, 0, tzinfo=ZoneInfo("America/New_York"))


def test_manual_stays_quiet_and_the_others_make_one_post_a_day(tmp_path: Path):
    path = tmp_path / "state.json"
    save(empty_state(), path)
    assert run_daily(load(path), path, now=WHEN) == []
    assert load(path)["pieces"] == []
    set_mode(load(path), "okay", "auto", confirm=True, path=path)
    made = run_daily(load(path), path, now=WHEN)
    assert made[0]["status"] == "scheduled"
    piece = load(path)["pieces"][0]
    assert piece.get("placeholder") is not True
    assert piece["status"] == "scheduled"
    assert piece["posted"] is False
    assert "facebook" in piece["variants"]
    assert run_daily(load(path), path, now=WHEN) == []
    assert len(load(path)["pieces"]) == 1


def test_approval_sends_the_day_for_review_and_does_not_schedule_it(tmp_path: Path):
    path = tmp_path / "state.json"
    save(empty_state(), path)
    set_mode(load(path), "okay", "approval", path=path)
    made = run_daily(load(path), path, now=WHEN)
    assert made[0]["status"] == "pending"
    piece = load(path)["pieces"][0]
    assert piece["status"] == "pending"
    assert piece["posted"] is False
    assert piece.get("placeholder") is not True
