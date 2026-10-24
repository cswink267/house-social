"""The supports do not send, and a preview cannot schedule itself.

pytest imports this. Callers are support_view, preview_week, and mix_hold.
The user said continue.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapt import DraftError  # noqa: E402
from modes import prepare_batch, run_auto, set_mode  # noqa: E402
from series import save_series  # noqa: E402
from store import empty_state, load  # noqa: E402
from support import clear_log, export_decisions, fill_series, mail_notice, preview_week, promote_preview, save_adapt, save_mail, save_mix, save_pause, set_series_pause, support_view, teach_rejection  # noqa: E402


def _posts():
    rows = []
    for index in range(3):
        rows.append({"id": f"a{index}", "brand_id": "okay", "preview": "a line", "published_at": "2026-10-20T15:00:00-04:00", "local_hour": 10, "engagements": 30, "format": "feed", "source": "history"})
    for index in range(3):
        rows.append({"id": f"b{index}", "brand_id": "okay", "preview": "a line", "published_at": "2026-10-21T15:00:00-04:00", "local_hour": 20, "engagements": 4, "format": "feed", "source": "history"})
    return rows


def test_health_preview_pause_and_a_hard_mix_hold(tmp_path: Path):
    path = tmp_path / "state.json"
    state = empty_state()
    state["history"] = _posts()
    card = support_view(state, "okay")["health"]
    assert card["ingest"] == "none"
    assert card["posts"] == 6
    assert "thin" in card["rate"]
    assert card["hint"] == ""
    save_pause(state, "okay", {"start": date.today().isoformat(), "end": (date.today() + timedelta(days=2)).isoformat()}, path)
    set_mode(load(path), "okay", "approval", path=path)
    with pytest.raises(DraftError, match="paused"):
        prepare_batch(load(path), "okay", path)
    save_pause(load(path), "okay", {"start": "", "end": ""}, path)
    save_mix(load(path), "okay", {"kind": "format", "name": "feed", "bound": "most", "count": 0, "hard": True}, path)
    set_mode(load(path), "okay", "auto", confirm=True, path=path)
    ran = run_auto(load(path), "okay", path)
    assert all(item.get("status") != "scheduled" for item in load(path)["pieces"])
    assert any("Held." in item["outcome"] for item in ran["log"])
    shown = preview_week(load(path), "okay", path)
    assert len(shown["previews"]) == 7
    assert all(item["preview"] and not item["stale"] for item in shown["previews"])
    promoted = promote_preview(load(path), "okay", shown["previews"][0]["id"], path)
    made = next(item for item in load(path)["pieces"] if "Preview only" in str(item.get("idea") or ""))
    assert made["status"] == "planned"
    assert made["posted"] is False
    assert len(promoted["previews"]) == 6
    exported = export_decisions(load(path), "okay", "markdown")
    dirty = export_decisions(
        {"mode_log": [{"brand_id": "okay", "at": "t", "mode": "manual", "action": "x", "outcome": "vault:house.secret " + "/home/" + "blackthorn/x"}]},
        "okay",
        "markdown",
    )
    assert "house.secret" not in dirty["body"]
    assert "/home/" not in dirty["body"]
    assert "%" not in exported["body"]
    with pytest.raises(DraftError, match="quote image"):
        save_adapt(empty_state(), "josie-blackthorn", {"quote_image": False}, path)


def test_a_rejection_can_ban_a_phrase_and_a_paused_series_does_not_fill(tmp_path: Path):
    path = tmp_path / "state.json"
    state = empty_state()
    state["history"] = _posts()
    teach_rejection(state, "okay", "banned", "rise and grind", "", path)
    assert "rise and grind" in load(path)["voices"]["okay"]["banned"]
    saved = save_series(load(path), "okay", {"name": "Monday", "structure": ["{topic}", "Ask."]}, path)
    filled = fill_series(load(path), "okay", saved["id"])
    assert filled["topic"] in filled["lines"][0]
    set_series_pause(load(path), "okay", saved["id"], True, path)
    with pytest.raises(DraftError, match="paused"):
        fill_series(load(path), "okay", saved["id"])
    save_mail(load(path), "okay", {"cadence": "digest", "quiet_start": 0, "quiet_end": 0}, path)
    notice = mail_notice(load(path), "okay")
    assert "Digest" in notice
    assert "vault:" not in notice
    clear_log(load(path), "okay", path)
    assert load(path)["mode_log"][0]["action"] == "clear"
