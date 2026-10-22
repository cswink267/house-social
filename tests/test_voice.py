"""The voice profile stays specific, and a lesson needs a real gap.

pytest imports this. Callers are save_voice, voice_lessons, import_voice_csv,
accept_voice_suggestion, restore_voice, and assist. A saved guide stores
formality, pillars, examples, and versions. The user asked for a living,
data-informed brand voice with a checklist and suggested refinements.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapt import DraftError  # noqa: E402
from assist import assist  # noqa: E402
from store import (  # noqa: E402
    accept_voice_suggestion,
    add_voice_post,
    empty_state,
    import_voice_csv,
    load,
    restore_voice,
    save_voice,
    studio,
)
from voice import guide_for, voice_lessons, voice_report  # noqa: E402


def _post(name, text, engagements):
    return {"id": name, "preview": text, "engagements": engagements, "shares": 0}


def test_profile_round_trip_and_checklist_get_stricter(tmp_path: Path):
    path = tmp_path / "state.json"
    saved = save_voice(
        empty_state(),
        "misfit-mindset",
        {
            "formality": "casual",
            "humor": "Dry.",
            "point_of_view": "Second person.",
            "preferred": ["Open with a short first sentence."],
            "differentiation": "Not a gratitude journal.",
            "pillars": [{"id": "raw-truth", "name": "Wrong name", "angles": ["Name the dread first."]}],
            "examples": [
                {"title": "Lands", "text": "You felt the dread.", "kind": "on", "source": "written"},
                {"title": "Misses", "text": "Just paste a smile on it today.", "kind": "off", "source": "written"},
            ],
        },
        path,
    )
    assert saved["formality"] == "casual"
    assert saved["pillars"][0]["name"] == "Raw truth"
    assert saved["pillars"][0]["angles"] == ["Name the dread first."]
    assert saved["examples"][1]["kind"] == "off"
    long = "The week kept going and the dread stayed right where you left it yesterday."
    missed = voice_report(saved, {"idea": long + " Just paste a smile on it today."})
    assert any(item["id"] == "preferred" and item["ok"] is False for item in missed["fields"][0]["checks"])
    assert any(item["id"].startswith("off:") and item["ok"] is False for item in missed["fields"][0]["checks"])
    held = voice_report(saved, {"idea": "Open with a short first sentence. You felt the dread, and it stayed."})
    assert all(item["ok"] for item in held["fields"][0]["checks"])
    assert guide_for("blunt")["preferred"] == []
    assert guide_for("blunt")["formality"] == ""


def test_suggestions_require_a_real_gap_and_accept_writes_a_version(tmp_path: Path):
    short = [
        _post("s1", "You felt that dread.", 20),
        _post("s2", "You named that hour.", 20),
        _post("s3", "You kept that mark.", 20),
    ]
    long = [
        _post("l1", "Monday morning still carries the same quiet for them.", 4),
        _post("l2", "The evening kept that old quiet around the table.", 4),
        _post("l3", "Night after night the quiet stayed in the room.", 4),
    ]
    lessons = voice_lessons(guide_for("misfit-mindset"), short + long)
    assert lessons["ready"] is True
    opener = next(item for item in lessons["suggestions"] if item["id"] == "opener:short")
    assert "n=3" in opener["detail"]
    assert "%" not in opener["detail"]
    assert any(item["kind"] == "example" and item["example"]["kind"] == "on" for item in lessons["suggestions"])
    thin = voice_lessons(guide_for("misfit-mindset"), short[:2] + long[:2])
    assert thin["ready"] is False
    assert thin["suggestions"] == []
    close = voice_lessons(
        guide_for("okay"),
        [_post(f"a{i}", f"Monday morning still carries the same quiet number {i} today.", 10) for i in range(3)]
        + [_post(f"b{i}", f"Monday morning still carries the same quiet total {i} today.", 9) for i in range(3)],
    )
    assert close["ready"] is True
    assert close["suggestions"] == []
    assert "too close" in close["detail"]

    path = tmp_path / "state.json"
    state = {
        **empty_state(),
        "pulls": {"misfit-mindset": {"posts": [{**post, "published_at": "2026-10-20T16:00:00+00:00"} for post in short + long]}},
    }
    accepted = accept_voice_suggestion(state, "misfit-mindset", "opener:short", path)
    assert "Open with a short first sentence." in accepted["preferred"]
    versions = load(path)["voice_versions"]["misfit-mindset"]
    assert versions[-1]["note"].startswith("accepted opener:short")
    try:
        accept_voice_suggestion(load(path), "misfit-mindset", "opener:short", path)
    except DraftError as exc:
        assert "not supported" in str(exc)
    else:
        raise AssertionError("the same pattern was offered twice")


def test_word_pattern_and_csv_stay_off_the_analytics_pull(tmp_path: Path):
    posts = [
        _post("h1", "Monday morning still carries the same dread for them.", 30),
        _post("h2", "The evening kept that old dread around the table.", 30),
        _post("h3", "Night after night the dread stayed in the room.", 30),
        _post("l1", "Monday morning still carries the same quiet for them.", 4),
        _post("l2", "The evening kept that old quiet around the table.", 4),
        _post("l3", "Night after night the quiet stayed in the room.", 4),
    ]
    lessons = voice_lessons(guide_for("okay"), posts)
    assert any(item["id"] == "word:dread" for item in lessons["suggestions"])
    assert all("%" not in item["detail"] for item in lessons["suggestions"])

    path = tmp_path / "state.json"
    imported = import_voice_csv(
        empty_state(),
        "misfit-mindset",
        "text,engagements\nYou felt that dread access_token=SECRET,20\nA quiet line.,\n",
        path,
    )
    assert imported["imported"] == 2
    saved = load(path)
    assert saved["pulls"] == {}
    assert "SECRET" not in json.dumps(saved["voice_imports"])
    assert saved["voice_imports"][0]["engagements"] == 20
    assert saved["voice_imports"][1]["engagements"] is None
    assert studio(saved, "okay")["voice_desk"]["imports"] == 0
    try:
        import_voice_csv(saved, "misfit-mindset", "likes,day\n1,2026-10-01\n", path)
    except DraftError as exc:
        assert "text" in str(exc).lower()
    else:
        raise AssertionError("a csv without text was accepted")


def test_manual_example_and_restore(tmp_path: Path):
    path = tmp_path / "state.json"
    first = save_voice(empty_state(), "blunt", {"tone": "Plain."}, path)
    assert first["tone"] == "Plain."
    save_voice(load(path), "blunt", {"tone": "Warmer."}, path)
    version_id = load(path)["voice_versions"]["blunt"][0]["id"]
    restored = restore_voice(load(path), "blunt", version_id, path)
    assert restored["tone"] == "Plain."
    assert load(path)["voice_versions"]["blunt"][-1]["note"] == "restored"
    added = add_voice_post(
        load(path),
        "blunt",
        {"text": "Send a file access_token=SECRET and let it expire.", "kind": "off", "engagements": 3},
        path,
    )
    assert added["voice"]["examples"][-1]["kind"] == "off"
    assert added["voice"]["examples"][-1]["source"] == "saved"
    assert "SECRET" not in json.dumps(load(path))


def test_rewrite_hears_the_profile_and_the_misses():
    guide = guide_for(
        "misfit-mindset",
        {"preferred": ["Open with a short first sentence."], "differentiation": "Not a gratitude journal."},
    )

    def complete(messages):
        system = messages[0]["content"]
        assert "Preferred language: Open with a short first sentence." in system
        assert "Not a gratitude journal." in system
        assert "Fix these misses: idea: Use a preferred line" in system
        return json.dumps({"text": "Open with a short first sentence. You felt the dread."})

    result = assist(guide, "rewrite", "The week was long.", complete=complete, misses=("idea: Use a preferred line",))
    assert "you" in result["text"].lower()
    assert result["options"][0]["voice"]["checks"]
