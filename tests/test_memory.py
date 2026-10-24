"""Memory keeps a deleted pattern deleted.

pytest imports this. Callers are correct_memory, reset_memory, sync_memory,
and export_memory. A line names its count and its dates. The user said
continue, one todo item at a time.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapt import DraftError  # noqa: E402
from analytics_desk import read_draft  # noqa: E402
from brands import SECTIONS  # noqa: E402
from calendar_desk import advise  # noqa: E402
from memory import correct_memory, export_memory, memory_for, redact_memory, reset_memory, sync_memory  # noqa: E402
from queue_desk import queue_for  # noqa: E402
from store import empty_state, load  # noqa: E402


def _post(name, hour, engagements, fmt, day):
    return {
        "id": name,
        "brand_id": "okay",
        "preview": "a line",
        "published_at": f"2026-10-{day}T15:00:00-04:00",
        "local_hour": hour,
        "engagements": engagements,
        "format": fmt,
        "source": "history",
    }


def _clear():
    posts = [_post(f"a{i}", 10, 30, "feed", 18 + i) for i in range(3)]
    posts += [_post(f"b{i}", 20, 4, "text", 21 + i) for i in range(3)]
    return posts


def _state(posts):
    state = empty_state()
    state["history"] = posts
    return state


def test_memory_names_the_count_and_keeps_a_deleted_pattern(tmp_path: Path):
    posts = _clear()
    state = _state(posts)
    view = memory_for(state, "okay", posts, [])
    hour = next(line for line in view["lines"] if line["id"] == "hour")
    assert hour["thin"] is False
    assert "Based on 6 posts." in hour["detail"]
    assert "From 2026-10-18 to 2026-10-23." in hour["detail"]
    assert "%" not in hour["detail"]
    written = next(line for line in view["lines"] if line["id"] == "written:tone")
    assert "Not counted from posts." in written["detail"]
    path = tmp_path / "state.json"
    deleted = correct_memory(state, "okay", "hour", "delete", path)
    assert next(line for line in deleted["lines"] if line["id"] == "hour")["standing"] == "deleted"
    slot = advise([], [], posts, date(2026, 10, 24), marks={"hour": "deleted"})
    assert slot["slot"]["clear"] is False
    assert "deleted" in slot["slot"]["detail"]
    assert queue_for(load(path), "okay", posts)["suggestion"]["clear"] is False
    restored = correct_memory(load(path), "okay", "hour", "restore", path)
    assert next(line for line in restored["lines"] if line["id"] == "hour")["standing"] == "open"
    open_slot = advise([], [], posts, date(2026, 10, 24))
    assert open_slot["slot"]["clear"] is True
    assert "hour" in open_slot["slot"]["pattern_ids"]
    assert "memory" in {item["id"] for item in SECTIONS}


def test_a_thin_line_says_thin_and_reset_leaves_the_posts(tmp_path: Path):
    posts = [_post("one", 10, 4, "feed", 18), _post("two", 10, 5, "feed", 19)]
    state = _state(posts)
    hour = next(line for line in memory_for(state, "okay", posts, [])["lines"] if line["id"] == "hour")
    assert hour["thin"] is True
    assert hour["detail"].startswith("This is thin.")
    path = tmp_path / "state.json"
    reset_memory(state, "okay", path)
    saved = load(path)
    assert len(saved["history"]) == 2
    assert all(line["standing"] == "deleted" for line in memory_for(saved, "okay", posts, [])["lines"])
    exported = export_memory(saved, "okay", "markdown")
    assert exported["format"] == "markdown"
    assert "%" not in exported["body"]
    assert "vault:house" not in exported["body"]
    with pytest.raises(DraftError, match="markdown or json"):
        export_memory(saved, "okay", "pdf")


def test_an_ahead_post_is_recorded_once_and_a_deleted_hook_is_not_a_reason(tmp_path: Path):
    posts = [_post("big", 9, 30, "feed", 18)] + [_post(f"q{i}", 9, 4, "text", 19) for i in range(3)]
    first = sync_memory(_state(posts), "okay", tmp_path / "state.json")
    assert sum(1 for item in first["timeline"] if item["kind"] == "ahead" and item["pattern_id"] == "big") == 1
    second = sync_memory(load(tmp_path / "state.json"), "okay", tmp_path / "state.json")
    assert sum(1 for item in second["timeline"] if item["kind"] == "ahead" and item["pattern_id"] == "big") == 1
    short = [{"id": f"s{i}", "preview": "You felt that dread.", "engagements": 20, "published_at": "2026-10-20T16:00:00+00:00"} for i in range(3)]
    long = [{"id": f"l{i}", "preview": "Monday morning still carries the same quiet mark for them.", "engagements": 4, "published_at": "2026-10-20T16:00:00+00:00"} for i in range(3)]
    reading = read_draft("Monday morning still carries the same quiet mark for them today.", short + long, marks={"hook": "deleted"})
    assert "hook" not in reading["pattern_ids"]
    assert all("first sentence" not in miss.lower() for miss in reading["misses"])


def test_export_redacts_a_vault_name_and_a_machine_path():
    dirty = "vault:house-social.fake.token " + "/home/" + "blackthorn" + "/secret " + "access_token=" + ("abc" * 10)
    cleaned = redact_memory(dirty)
    assert "house-social.fake" not in cleaned
    assert "/home/" not in cleaned
    assert ("abc" * 8) not in cleaned
