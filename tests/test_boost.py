"""A boost suggestion is copy. It never spends and never invents a number.

pytest imports this. Callers are boost_for and save_boost_minimum.
The user said: Keep going.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapt import DraftError  # noqa: E402
from boost import boost_for, save_boost_minimum, suggestions  # noqa: E402
from store import empty_state, load  # noqa: E402


def _post(name: str, engagements, format_name: str = "feed", pillar: str = "") -> dict:
    return {
        "id": name,
        "brand_id": "okay",
        "preview": f"The {name} post",
        "published_at": "2026-10-20T15:00:00-04:00",
        "engagements": engagements,
        "format": format_name,
        "pillar": pillar,
    }


def _ahead() -> list[dict]:
    return [
        _post("loud", 40),
        _post("a", 4),
        _post("b", 4),
        _post("c", 4),
    ]


def test_a_missing_minimum_suggests_nothing():
    view = suggestions(_ahead(), None)
    assert view["minimum"] is None
    assert view["items"] == []
    assert "minimum" in view["note"]


def test_a_post_needs_three_others_a_format_and_the_minimum():
    thin = suggestions(_ahead()[:3], 10)
    assert thin["items"] == []
    assert "three" in thin["note"]
    plain = [_post("loud", 40, "", ""), _post("a", 4), _post("b", 4), _post("c", 4)]
    assert suggestions(plain, 10)["items"] == []
    low = suggestions(_ahead(), 50)
    assert low["items"] == []
    ready = suggestions(_ahead(), 10)
    assert len(ready["items"]) == 1
    item = ready["items"][0]
    assert item["engagements"] == 40
    assert item["others"] == 3
    assert "3×" in item["reason"]
    assert "10" in item["copy"]
    assert "$" not in item["copy"]
    assert "feed" in item["copy"]


def test_a_missing_count_is_not_zero_and_the_minimum_is_kept(tmp_path: Path):
    posts = _ahead() + [_post("blank", None, "feed")]
    view = suggestions(posts, 10)
    assert view["items"][0]["id"] == "loud"
    assert view["items"][0]["others"] == 3
    path = tmp_path / "state.json"
    saved = save_boost_minimum(empty_state(), "okay", {"minimum": 12}, path)
    assert saved["minimum"] == 12
    assert load(path)["boost_minimums"]["okay"] == 12
    cleared = save_boost_minimum(load(path), "okay", {"minimum": ""}, path)
    assert cleared["minimum"] is None
    assert "okay" not in (load(path).get("boost_minimums") or {})
    with pytest.raises(DraftError, match="whole number"):
        save_boost_minimum(load(path), "okay", {"minimum": -1}, path)
    shown = boost_for({**empty_state(), "boost_minimums": {"okay": 10}, "history": _ahead()}, "okay")
    assert shown["items"][0]["engagements"] == 40
