"""The agent drafts in its own words, and the brand's mode decides how far it goes."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modes import set_mode  # noqa: E402
from store import load  # noqa: E402


class Ctx:
    def __init__(self):
        self.tools = {}

    def register_tool(self, name, toolset, schema, handler):
        assert toolset == "house_social"
        assert schema["name"] == name
        self.tools[name] = handler

    def call(self, name, **params):
        return json.loads(self.tools[name](params))


def _tools() -> Ctx:
    spec = importlib.util.spec_from_file_location("house_social_plugin", ROOT / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ctx = Ctx()
    module.register(ctx)
    return ctx


def test_the_agent_drafts_and_the_mode_decides_review_or_schedule(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOUSE_SOCIAL_STATE", str(tmp_path / "state.json"))
    ctx = _tools()
    assert ctx.call("house_social_roster")["posting"] is False
    made = ctx.call(
        "house_social_draft",
        brand_id="okay",
        idea="The fire held.",
        facebook="The fire held. The night did not. Tell us about yours.",
        instagram="The fire held through the night.",
        threads="The fire held.",
    )
    assert made["ok"] is True
    piece_id = made["piece"]["id"]
    assert made["piece"]["variants"]["facebook"]["body"].endswith("Tell us about yours.")
    when = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    reviewed = ctx.call("house_social_schedule", piece_id=piece_id, scheduled_for=when)
    assert reviewed["status"] == "pending"
    queue = ctx.call("house_social_queue", brand_id="okay")
    assert queue["live"] is False
    assert queue["items"][0]["status"] == "pending"

    second = ctx.call("house_social_draft", brand_id="okay", idea="Second.", facebook="Second, long.", instagram="Second, square.", threads="Second.")
    set_mode(load(), "okay", "auto", confirm=True)
    scheduled = ctx.call("house_social_schedule", piece_id=second["piece"]["id"], scheduled_for=when)
    assert scheduled["status"] == "scheduled"
    saved = next(item for item in load()["pieces"] if item["id"] == second["piece"]["id"])
    assert saved["approval"]["by"] == "auto"
    refused = ctx.call("house_social_post_now", piece_id=piece_id)
    assert refused["ok"] is False
    assert "Posting is off" in refused["error"]
    assert ctx.call("house_social_posting", brand_id="okay")["live"] is False
