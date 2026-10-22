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


def _posts(piece_id: str, engagements: int, prefix: str) -> list[dict]:
    return [
        {
            "id": f"{prefix}{i}",
            "piece_id": piece_id,
            "engagements": engagements,
            "shares": 1,
            "preview": "You felt the fire." if piece_id else "A quiet line.",
            "published_at": "2026-09-20T16:00:00+00:00",
        }
        for i in range(3)
    ]


def test_campaign_clone_and_retrospective_use_real_posts(tmp_path, monkeypatch):
    monkeypatch.setenv("HOUSE_SOCIAL_ASSETS", str(tmp_path / "files"))
    path = tmp_path / "state.json"
    launch = create_piece(empty_state(), "misfit-mindset", "The fire held. The night did not.", path=path)
    seasonal = create_piece(load(path), "misfit-mindset", "The month turned.", path=path)
    saved = save_campaign(
        load(path),
        "misfit-mindset",
        {
            "name": "The drop",
            "kind": "launch",
            "goal": "Three posts before it closes.",
            "goal_posts": 3,
            "start": "2026-09-01",
            "end": "2026-09-30",
            "template": True,
            "note": "A dated launch.",
        },
        path,
    )
    attach_campaign(load(path), saved["id"], {"piece_ids": [launch["id"]]}, path)
    other = save_campaign(
        load(path),
        "misfit-mindset",
        {"name": "The month", "kind": "seasonal", "start": "2026-09-01", "end": "2026-09-30"},
        path,
    )
    attach_campaign(load(path), other["id"], {"piece_ids": [seasonal["id"]]}, path)
    posts = _posts(launch["id"], 20, "in") + _posts(seasonal["id"], 4, "out")
    view = campaigns_for(load(path), "misfit-mindset", posts, date(2026, 10, 21))
    card = next(item for item in view["campaigns"] if item["id"] == saved["id"])
    assert card["template"] is True
    assert card["retrospective"]["ready"] is True
    assert card["retrospective"]["ahead"] is True
    assert "20.0" in card["performance"]["detail"]
    assert "%" not in card["performance"]["detail"]
    launch_lesson = next(item for item in view["lessons"] if item["kind"] == "launch")
    assert launch_lesson["ahead"] is True
    assert "similar approach" in launch_lesson["approach"]
    assert "seasonal" not in launch_lesson["approach"]
    behind = next(item for item in view["lessons"] if item["kind"] == "seasonal")
    assert behind["ahead"] is False

    from campaigns import clone_campaign, keep_retrospective

    copied = clone_campaign(load(path), saved["id"], path)
    assert copied["name"] == "The drop copy"
    assert copied["template"] is False
    assert copied["goal_posts"] == 3
    assert copied["start"] == ""
    assert copied["pieces"] == []
    assert next(item for item in load(path)["pieces"] if item["id"] == launch["id"])["campaign"] == "The drop"
    again = clone_campaign(load(path), saved["id"], path)
    assert again["name"] == "The drop copy 2"

    kept = keep_retrospective(load(path), saved["id"], posts, path)
    assert "You felt the fire." in [item["text"] for item in kept["voice"]["examples"]]
    assert any("20.0" in item["text"] for item in load(path)["ideas"])
    assert all(item.get("posted") is not True for item in load(path)["pieces"])
    with pytest.raises(DraftError, match="clear enough"):
        keep_retrospective(load(path), other["id"], posts, path)

    thin = campaigns_for(load(path), "misfit-mindset", posts[:1], date(2026, 10, 21))
    assert "waits for 3" in next(item for item in thin["campaigns"] if item["id"] == saved["id"])["performance"]["detail"]
    open_run = save_campaign(
        load(path),
        "jamhaul",
        {"name": "Still open", "kind": "launch", "end": "2026-12-01"},
        path,
    )
    opened = campaigns_for(load(path), "jamhaul", [], date(2026, 10, 21))
    assert "waits until the end date" in next(item for item in opened["campaigns"] if item["id"] == open_run["id"])["retrospective"]["detail"]

    from ideas import idea_brief

    brief = idea_brief([{"name": "Raw truth"}], [], [], view["lessons"])
    assert "similar approach" in brief
    assert "%" not in brief
    quiet = idea_brief([{"name": "Raw truth"}], [], [])
    assert "No campaign kind is clearly ahead." in quiet
