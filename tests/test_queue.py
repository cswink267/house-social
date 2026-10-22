"""The queue separates drafting from what is going out, and it does not send."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from learn import suggest_hour  # noqa: E402
from queue_desk import bulk_queue, next_local_hour, queue_for  # noqa: E402
from store import create_piece, empty_state, load, roster  # noqa: E402


def _post(hour: int, engagements: int, name: str) -> dict:
    return {"id": name, "local_hour": hour, "engagements": engagements, "format": "feed"}


def test_queue_blocks_a_broken_piece_and_suggests_only_a_clear_hour(tmp_path: Path):
    path = tmp_path / "state.json"
    josie = create_piece(empty_state(), "josie-blackthorn", "Stay. The rest can wait.", path=path)
    haul = create_piece(load(path), "jamhaul", "What is a haul?", path=path)
    mixed = bulk_queue(load(path), "josie-blackthorn", [josie["id"], haul["id"]], "pending", path=path)
    josie_result = next(item for item in mixed["results"] if item["id"] == josie["id"])
    assert josie_result["ok"] is False
    assert josie_result["status"] == "failed"
    assert "quote image" in josie_result["error"]
    assert next(item for item in mixed["results"] if item["id"] == haul["id"])["ok"] is False
    haul_piece = next(item for item in load(path)["pieces"] if item["id"] == haul["id"])
    assert haul_piece["status"] == "draft"

    held = bulk_queue(load(path), "jamhaul", [haul["id"]], "pending", path=path)
    assert held["results"][0]["ok"] is True
    assert held["results"][0]["status"] == "pending"

    clear = [_post(10, 30, f"a{i}") for i in range(3)] + [_post(20, 4, f"b{i}") for i in range(3)]
    view = queue_for(load(path), "jamhaul", clear)
    assert view["suggestion"]["clear"] is True
    assert view["suggestion"]["hour"] == 10
    assert any("500" in rule for rule in view["rules"])
    assert any(section["id"] == "queue" for section in roster(empty_state())[0]["sections"])

    from approval import decide
    decide(load(path), haul["id"], {"author": "Approver", "decision": "approved"}, path)
    scheduled = bulk_queue(load(path), "jamhaul", [haul["id"]], "schedule", path=path, posts=clear)
    assert scheduled["results"][0]["ok"] is True
    saved = next(item for item in load(path)["pieces"] if item["id"] == haul["id"])
    local = datetime.fromisoformat(saved["scheduled_for"]).astimezone(ZoneInfo("America/New_York"))
    assert local.hour == 10
    assert saved["posted"] is False
    assert saved["failure"] == ""

    close = [_post(10, 5, f"c{i}") for i in range(3)] + [_post(12, 4, f"d{i}") for i in range(3)]
    assert suggest_hour(close)["clear"] is False
    quiet = create_piece(load(path), "jamhaul", "What is a haul?", path=path)
    bulk_queue(load(path), "jamhaul", [quiet["id"]], "pending", path=path)
    missed = bulk_queue(load(path), "jamhaul", [quiet["id"]], "schedule", path=path, posts=close)
    assert missed["results"][0]["ok"] is False
    assert missed["results"][0]["status"] == "failed"
    returned = bulk_queue(load(path), "jamhaul", [quiet["id"]], "draft", path=path)
    assert returned["results"][0]["status"] == "draft"
    assert next(item for item in load(path)["pieces"] if item["id"] == quiet["id"])["failure"] == ""

    morning = datetime(2026, 10, 21, 9, 30, tzinfo=ZoneInfo("America/New_York"))
    assert next_local_hour(10, morning).startswith("2026-10-21T10:00:00")
    later = datetime(2026, 10, 21, 11, 0, tzinfo=ZoneInfo("America/New_York"))
    assert next_local_hour(10, later).startswith("2026-10-22T10:00:00")
