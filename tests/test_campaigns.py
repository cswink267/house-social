"""A campaign groups the pieces, the assets, the goal, and the dates."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapt import DraftError  # noqa: E402
from campaigns import attach_campaign, campaigns_for, revise_campaign, save_campaign  # noqa: E402
from library import save_asset  # noqa: E402
from store import create_piece, empty_state, load, roster  # noqa: E402


def test_campaign_groups_work_and_counts_only_linked_posts(tmp_path, monkeypatch):
    monkeypatch.setenv("HOUSE_SOCIAL_ASSETS", str(tmp_path / "files"))
    path = tmp_path / "state.json"
    piece = create_piece(empty_state(), "misfit-mindset", "The fire held. The night did not.", campaign="October", path=path)
    asset = save_asset(load(path), "misfit-mindset", {"kind": "copy", "name": "The line", "body": "You felt it."}, path)
    saved = save_campaign(
        load(path),
        "misfit-mindset",
        {
            "name": "October",
            "kind": "seasonal",
            "goal": "Four posts before the month ends.",
            "goal_posts": 4,
            "start": "2026-10-01",
            "end": "2026-10-31",
        },
        path,
    )
    assert saved["progress"]["posts"] == 1
    assert saved["progress"]["goal_posts"] == 4
    assert saved["progress"]["phase"] == "In its dates"
    attached = attach_campaign(load(path), saved["id"], {"asset_ids": [asset["id"]]}, path)
    assert attached["progress"]["assets"] == 1
    assert attached["pieces"][0]["id"] == piece["id"]
    posts = [{
        "id": "p1",
        "piece_id": piece["id"],
        "engagements": 11,
        "shares": 2,
        "published_at": "2026-10-20T16:00:00+00:00",
    }]
    view = campaigns_for(load(path), "misfit-mindset", posts, date(2026, 10, 21))
    card = view["campaigns"][0]
    assert card["performance"]["engagements"] == 11
    assert card["performance"]["shares"] == 2
    assert card["performance"]["saves"] is None
    assert card["performance"]["clear"] is False
    renamed = revise_campaign(load(path), saved["id"], {"name": "Late October"}, path)
    assert renamed["name"] == "Late October"
    linked = next(item for item in load(path)["pieces"] if item["id"] == piece["id"])
    assert linked["campaign"] == "Late October"
    other = create_piece(load(path), "jamhaul", "What is a haul?", path=path)
    with pytest.raises(DraftError, match="another brand"):
        attach_campaign(load(path), saved["id"], {"piece_ids": [other["id"]]}, path)
    with pytest.raises(DraftError, match="before the start"):
        save_campaign(
            load(path),
            "jamhaul",
            {"name": "Launch", "kind": "launch", "start": "2026-11-02", "end": "2026-11-01"},
            path,
        )
    evergreen = save_campaign(
        load(path),
        "jamhaul",
        {"name": "The question", "kind": "evergreen", "goal": "Keep one question in the queue."},
        path,
    )
    assert evergreen["progress"]["phase"] == "Open"
    assert any(section["id"] == "campaigns" for section in roster(empty_state())[0]["sections"])
