"""Manual drafts nothing. Approval does not schedule. Auto does not send.

pytest imports this. Callers are set_mode, prepare_batch, decide_batch,
and run_auto. The user said continue.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapt import DraftError  # noqa: E402
from modes import decide_batch, mode_view, prepare_batch, run_auto, set_mode  # noqa: E402
from store import empty_state, load  # noqa: E402


def _posts(brand="okay"):
    rows = []
    for index in range(3):
        rows.append({"id": f"a{index}", "brand_id": brand, "preview": "a line", "published_at": "2026-10-20T15:00:00-04:00", "local_hour": 10, "engagements": 30, "format": "text", "source": "history"})
    for index in range(3):
        rows.append({"id": f"b{index}", "brand_id": brand, "preview": "a line", "published_at": "2026-10-21T15:00:00-04:00", "local_hour": 20, "engagements": 4, "format": "text", "source": "history"})
    return rows


def test_manual_is_the_default_and_a_batch_does_not_schedule_or_send(tmp_path: Path):
    path = tmp_path / "state.json"
    state = empty_state()
    state["history"] = _posts()
    assert mode_view(state, "okay")["mode"] == "manual"
    with pytest.raises(DraftError, match="Manual does not"):
        prepare_batch(state, "okay", path)
    with pytest.raises(DraftError, match="thin"):
        set_mode(state, "okay", "auto", path=path)
    approval = set_mode(state, "okay", "approval", path=path)
    assert approval["mode"] == "approval"
    prepared = prepare_batch(load(path), "okay", path)
    piece = prepared["batch"]["pieces"][0]
    assert piece["status"] == "planned"
    assert piece["posted"] is False
    assert "not configured" in prepared["notice"]
    with pytest.raises(DraftError, match="still open"):
        prepare_batch(load(path), "okay", path)
    decided = decide_batch(load(path), "okay", piece["piece_id"], "approve", path)
    saved = next(item for item in load(path)["pieces"] if item["id"] == piece["piece_id"])
    assert saved["status"] == "scheduled"
    assert saved["posted"] is False
    assert decided["batch"]["pieces"][0]["decision"] == "approve"
    with pytest.raises(DraftError, match="already decided"):
        decide_batch(load(path), "okay", piece["piece_id"], "approve", path)


def test_reject_keeps_feedback_and_auto_still_does_not_send(tmp_path: Path):
    path = tmp_path / "state.json"
    state = empty_state()
    state["history"] = _posts()
    set_mode(state, "okay", "approval", path=path)
    prepared = prepare_batch(load(path), "okay", path)
    piece_id = prepared["batch"]["pieces"][0]["piece_id"]
    decide_batch(load(path), "okay", piece_id, "reject", path)
    assert all(item["id"] != piece_id for item in load(path)["pieces"])
    assert any(item.get("verdict") == "off-brand" for item in load(path)["feedback"])
    set_mode(load(path), "okay", "manual", path=path)
    assert any(item.get("status") == "scheduled" for item in load(path)["pieces"]) is False
    with pytest.raises(DraftError, match="Confirm"):
        set_mode(load(path), "okay", "auto", path=path)
    set_mode(load(path), "okay", "auto", confirm=True, path=path)
    ran = run_auto(load(path), "okay", path)
    made = next(item for item in load(path)["pieces"] if item.get("status") == "scheduled")
    assert made["posted"] is False
    assert any("not sent" in item["outcome"] for item in ran["log"])
