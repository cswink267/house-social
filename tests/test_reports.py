"""A report is the numbers we already have, plus a note, with no token in the file.

pytest calls this. It covers generate_report and report_export, the report
row stored on a brand, and the Reports desk id. The user asked for weekly
and monthly brand reports with key metrics, top content, notes, and export.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapt import DraftError  # noqa: E402
from reports import generate_report, report_export, reports_for  # noqa: E402
from store import empty_state, load, roster  # noqa: E402


TODAY = date(2026, 10, 21)


def _state() -> dict:
    state = empty_state()
    posts = [
        {
            "id": "week",
            "preview": "Quote access_token=SECRET",
            "published_at": "2026-10-20T16:00:00+00:00",
            "engagements": 18,
            "shares": 3,
            "format": "quote-image",
            "impressions": 0,
        },
        {
            "id": "mid",
            "preview": "Mid month",
            "published_at": "2026-10-10T16:00:00+00:00",
            "engagements": 4,
            "shares": 1,
            "format": "feed",
            "impressions": 0,
        },
        {
            "id": "sep",
            "preview": "September",
            "published_at": "2026-09-15T16:00:00+00:00",
            "engagements": 9,
            "shares": 2,
            "format": "text",
            "impressions": 0,
        },
    ]
    return {**state, "pulls": {"misfit-mindset": {"posts": posts}}}


def test_week_and_month_reports_keep_missing_numbers_and_drop_tokens(tmp_path: Path):
    path = tmp_path / "state.json"
    week = generate_report(_state(), "misfit-mindset", "week", "Sent to the client.", path=path, today=TODAY)
    assert week["title"] == "Week of 2026-10-15 through 2026-10-21"
    assert "Sent to the client." in week["markdown"]
    assert "Engagements: 18 across 1 posts" in week["markdown"]
    assert "Engagements 18 in this window, 4 in the one before." in week["markdown"]
    assert "The pull did not include reach." in week["markdown"]
    assert "Saves were not in this pull." in week["markdown"]
    assert "Follower counts were not in this pull." in week["markdown"]
    assert "No post in this window is tied to a campaign." in week["markdown"]
    assert "access_token=REDACTED" in week["markdown"]
    assert "SECRET" not in week["markdown"]
    assert "SECRET" not in json.dumps(week["document"])
    assert "/home/" not in week["markdown"]

    month = generate_report(load(path), "misfit-mindset", "month", "", path=path, today=TODAY)
    assert month["title"] == "October 2026 through 2026-10-21"
    assert "Engagements: 22 across 2 posts" in month["markdown"]
    assert "Engagements 22 in this window, 9 in the one before." in month["markdown"]
    assert "This month against last month" in month["markdown"]
    assert "No note." in month["markdown"]

    saved = load(path)
    assert [item["id"] for item in reports_for(saved, "misfit-mindset")["reports"]] == [month["id"], week["id"]]
    assert reports_for(saved, "okay")["reports"] == []
    text, media, _name = report_export(saved, week["id"], "md")
    assert media.startswith("text/markdown")
    assert "SECRET" not in text
    payload, kind, _json_name = report_export(saved, week["id"], "json")
    assert kind == "application/json"
    assert "SECRET" not in payload
    assert json.loads(payload)["note"] == "Sent to the client."

    try:
        generate_report(saved, "misfit-mindset", "year", path=path, today=TODAY)
    except DraftError as exc:
        assert "week or a month" in str(exc)
    else:
        raise AssertionError("a year is not a report")
    assert len(load(path)["reports"]) == 2
    assert any(section["id"] == "reports" for section in roster(empty_state())[0]["sections"])
