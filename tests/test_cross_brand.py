"""Cross-brand stays aggregated and off until two brands opt in.

pytest imports this. Callers are set_cross, accept_cross, and cross_for.
The user said continue todo.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapt import DraftError  # noqa: E402
from cross_brand import accept_cross, cross_for, set_cross  # noqa: E402
from store import empty_state, load  # noqa: E402


def _post(brand, name, engagements, fmt, hour):
    return {
        "id": name,
        "brand_id": brand,
        "preview": "SECRET-CAPTION-" + name,
        "published_at": "2026-10-20T15:00:00-04:00",
        "local_hour": hour,
        "engagements": engagements,
        "format": fmt,
        "source": "history",
    }


def test_cross_brand_is_off_until_two_brands_and_hides_their_words(tmp_path: Path):
    path = tmp_path / "state.json"
    state = empty_state()
    state["history"] = [
        *[_post("okay", f"a{i}", 30, "feed", 10) for i in range(3)],
        *[_post("jamhaul", f"b{i}", 4, "text", 20) for i in range(3)],
    ]
    quiet = cross_for(state, "okay")
    assert quiet["enabled"] is False
    assert quiet["offer"] is None
    assert "SECRET-CAPTION" not in json.dumps(quiet)
    one = set_cross(state, "okay", True, path)
    assert "two brands" in one["lines"][0]["detail"]
    assert one["offer"] is None
    both = set_cross(load(path), "jamhaul", True, path)
    assert both["enabled"] is True
    assert any(item["clear"] and "feed" in item["detail"] and "n=3" in item["detail"] for item in both["lines"])
    dumped = json.dumps(both)
    assert "SECRET-CAPTION" not in dumped
    assert "%" not in dumped
    assert both["offer"]["label"] == "cross-brand"
    accepted = accept_cross(load(path), "okay", both["offer"]["key"], path)
    assert any(item["key"] == both["offer"]["key"] for item in accepted["accepted"])
    assert accepted["offer"] is None or accepted["offer"]["key"] != both["offer"]["key"]
    assert "cross-brand" in accepted["accepted"][0]["detail"]
    gone = set_cross(load(path), "jamhaul", False, path)
    assert "two brands" in gone["lines"][0]["detail"]
    with pytest.raises(DraftError, match="not included"):
        accept_cross(load(path), "jamhaul", "format:feed:text", path)
