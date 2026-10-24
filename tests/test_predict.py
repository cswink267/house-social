"""The range stays wide until the posts can narrow it.

pytest imports this. Callers are predict_range, remember_prediction, and
apply_grades. The user said continue, one todo item at a time.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from predict import apply_grades, is_hidden, predict_range, remember_prediction, set_prediction_hidden  # noqa: E402
from store import create_piece, empty_state, load, record_stat  # noqa: E402


def _post(name, preview, engagements):
    return {
        "id": name,
        "brand_id": "okay",
        "preview": preview,
        "published_at": "2026-10-20T16:00:00+00:00",
        "local_hour": 12,
        "engagements": engagements,
        "format": "text",
        "source": "history",
    }


def _split():
    short = [_post(f"s{i}", "You felt that dread.", 20) for i in range(3)]
    long = [_post(f"l{i}", "Monday morning still carries the same quiet mark for them.", 4) for i in range(3)]
    return short + long


def test_a_thin_window_stays_wide_and_a_clear_hook_sets_the_range():
    thin = predict_range("You felt that dread.", _split()[:2])
    assert thin["band"] == "wide"
    assert "Based on 2 posts." in thin["detail"]
    assert thin["factors"] == []
    assert "%" not in thin["detail"]
    posts = _split()
    low = predict_range("Monday morning still carries the same quiet mark for them today.", posts)
    high = predict_range("You felt that dread extra.", posts)
    assert low["band"] == "low"
    assert high["band"] == "high"
    assert low["factors"]
    assert "0-100" not in low["detail"]
    muted = predict_range(
        "Monday morning still carries the same quiet mark for them today.",
        posts,
        marks={"hook": "deleted", "length": "deleted", "question": "deleted", "cta": "deleted"},
    )
    assert muted["band"] == "wide"
    assert muted["change"] == ""


def test_a_grade_waits_for_real_numbers_and_a_wide_range_is_not_graded(tmp_path: Path):
    path = tmp_path / "state.json"
    state = empty_state()
    state["history"] = [_post(f"h{i}", "A quiet evening post.", 4) for i in range(3)]
    piece = create_piece(state, "okay", "You felt that dread.", path)
    saved = load(path)
    found = predict_range("You felt that dread extra.", list(saved["history"]) + _split())
    remembered = remember_prediction(saved, "okay", piece["id"], found, path)
    assert remembered["predictions"][0]["graded"] is None
    record_stat(
        load(path),
        {"brand_id": "okay", "platform": "facebook", "piece_id": piece["id"], "engagements": 30, "preview": "You felt that dread extra."},
        path,
    )
    graded = next(item for item in load(path)["predictions"] if item["piece_id"] == piece["id"])
    assert graded["graded"]["correct"] is True
    assert graded["graded"]["direction"] == "higher"
    assert "%" not in graded["graded"]["detail"]
    other = create_piece(load(path), "okay", "Something quiet.", path)
    remember_prediction(load(path), "okay", other["id"], {**found, "band": "wide"}, path)
    record_stat(
        load(path),
        {"brand_id": "okay", "platform": "facebook", "piece_id": other["id"], "impressions": 10, "preview": "Something quiet."},
        path,
    )
    waiting = next(item for item in load(path)["predictions"] if item["piece_id"] == other["id"])
    assert waiting["graded"] is None
    record_stat(
        load(path),
        {"brand_id": "okay", "platform": "facebook", "piece_id": other["id"], "engagements": 30, "preview": "Something quiet."},
        path,
    )
    done = next(item for item in load(path)["predictions"] if item["piece_id"] == other["id"])
    assert done["graded"]["correct"] is None
    assert "not graded" in done["graded"]["detail"]


def test_hide_is_per_brand_or_global(tmp_path: Path):
    path = tmp_path / "state.json"
    set_prediction_hidden(empty_state(), "okay", True, "brand", path)
    assert is_hidden(load(path), "okay") is True
    assert is_hidden(load(path), "josie-blackthorn") is False
    hidden = predict_range("You felt that dread.", _split(), hidden=True)
    assert hidden["hidden"] is True
    assert hidden["band"] == ""
    set_prediction_hidden(load(path), "okay", False, "brand", path)
    set_prediction_hidden(load(path), "okay", True, "all", path)
    assert is_hidden(load(path), "josie-blackthorn") is True
    assert apply_grades(empty_state(), "okay")["predictions"] == []
