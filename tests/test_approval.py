"""Review is a sequence, and schedule waits until it is finished."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapt import DraftError  # noqa: E402
from approval import add_comment, compare_piece, decide, mark_notice, save_steps, submit_review  # noqa: E402
from store import create_piece, empty_state, load, roster, update_piece  # noqa: E402


def test_two_steps_compare_and_a_notice(tmp_path: Path):
    path = tmp_path / "state.json"
    piece = create_piece(empty_state(), "jamhaul", "What is a haul?", path=path)
    save_steps(load(path), "jamhaul", ["First", "Second"], path)
    submit_review(load(path), piece["id"], path)
    saved = next(item for item in load(path)["pieces"] if item["id"] == piece["id"])
    assert saved["status"] == "pending"
    assert len(saved["approval"]["versions"]) == 1
    assert load(path)["notices"][0]["read"] is False
    with pytest.raises(DraftError, match="First"):
        decide(load(path), piece["id"], {"author": "Second", "decision": "approved"}, path)
    waiting = decide(load(path), piece["id"], {"author": "First", "decision": "approved", "comment": "The question lands."}, path)
    assert waiting["status"] == "pending"
    assert waiting["waiting"] == "Second"
    update_piece(
        load(path),
        piece["id"],
        variants={"facebook": {"body": "What is a haul?\n\njamhaul.com\n\nA second pass."}},
        path=path,
    )
    submit_review(load(path), piece["id"], path)
    compared = compare_piece(next(item for item in load(path)["pieces"] if item["id"] == piece["id"]))
    facebook = next(item for item in compared["platforms"] if item["platform"] == "facebook")
    assert compared["ready"] is True
    assert facebook["same"] is False
    decide(load(path), piece["id"], {"author": "First", "decision": "approved"}, path)
    done = decide(load(path), piece["id"], {"author": "Second", "decision": "approved"}, path)
    assert done["status"] == "approved"
    add_comment(load(path), piece["id"], {"author": "Second", "text": "Ship the question."}, path)
    assert any(item["text"] == "Ship the question." for item in load(path)["pieces"][0]["approval"]["comments"])
    notice_id = next(item["id"] for item in load(path)["notices"] if not item["read"])
    marked = mark_notice(load(path), notice_id, path)
    assert all(item["id"] != notice_id for item in marked["notices"])
    changes = create_piece(load(path), "jamhaul", "What is a haul?", path=path)
    submit_review(load(path), changes["id"], path)
    sent_back = decide(load(path), changes["id"], {"author": "First", "decision": "changes", "comment": "Cut the second line."}, path)
    assert sent_back["status"] == "draft"
    assert any(section["id"] == "approval" for section in roster(empty_state())[0]["sections"])
    kept = next(item for item in load(path)["pieces"] if item["id"] == piece["id"])
    actions = [item["action"] for item in kept["approval"]["trail"]]
    assert actions.count("submitted") == 2
    assert "approved" in actions
    assert "comment" in actions
    facebook = next(item for item in compare_piece(kept, 0, 1)["platforms"] if item["platform"] == "facebook")
    assert "A second pass." in facebook["added"]
    assert "A second pass." not in facebook["removed"]
    sent = next(item for item in load(path)["pieces"] if item["id"] == changes["id"])
    assert any(item["action"] == "changes" for item in sent["approval"]["trail"])
    assert all(item["id"] != notice_id for item in mark_notice(load(path), notice_id, path)["notices"])
    assert any(item["action"] == "submitted" for item in next(item for item in load(path)["pieces"] if item["id"] == piece["id"])["approval"]["trail"])
