"""The assistant stays inside the brand voice and stays quiet when offline."""

from __future__ import annotations

import json
import io
import sys
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapt import DraftError, suggest_hashtags  # noqa: E402
from assist import assist, ollama_complete  # noqa: E402
from store import create_piece, empty_state, load, update_piece  # noqa: E402
from voice import guide_for  # noqa: E402


def test_rewrite_drops_a_banned_line_and_caption_needs_an_image():
    guide = guide_for("misfit-mindset")

    def complete(messages):
        assert "just stay positive" in messages[0]["content"].lower()
        return json.dumps({"text": "Just stay positive. You felt the dread, and it is data."})

    result = assist(guide, "rewrite", "Sunday dread.", complete=complete)
    assert "just stay positive" not in result["text"].lower()
    assert "you" in result["text"].lower()
    assert result["options"][0]["voice"]["total"] >= 1

    with pytest.raises(DraftError, match="image"):
        assist(guide, "caption", "", complete=complete)

    seen = {}

    def see(messages):
        seen["image"] = any(isinstance(message.get("content"), list) for message in messages)
        return json.dumps({"text": "You can see the mark."})

    caption = assist(guide, "caption", "", complete=see, image=b"\x89PNG\r\n\x1a\nxxxx", mime="image/png")
    assert seen["image"] is True
    assert caption["text"] == "You can see the mark."


def test_variations_hashtags_first_comment_and_offline(tmp_path, monkeypatch):
    guide = guide_for("misfit-mindset")

    def complete(messages):
        return json.dumps({"options": ["You felt it.", "You can name it.", "You already know.", "You felt it."]})

    variations = assist(guide, "variations", "Sunday dread.", complete=complete)
    assert [item["text"] for item in variations["options"]] == ["You felt it.", "You can name it.", "You already know."]
    tags = suggest_hashtags("Hello #Ember", ("misfitmindset",))
    assert tags[0] == "Ember"
    assert "misfitmindset" in tags
    hashed = assist(guide, "hashtags", "Hello #Ember", complete=complete, brand_tags=("misfitmindset",))
    assert hashed["source"] == "brand"
    assert hashed["options"][0]["text"] == "Ember"

    path = tmp_path / "state.json"
    piece = create_piece(empty_state(), "misfit-mindset", "The fire held. The night did not.", path=path)
    saved = update_piece(
        load(path),
        piece["id"],
        variants={"facebook": {"first_comment": "Say it back if it landed."}},
        path=path,
    )
    assert saved["variants"]["facebook"]["first_comment"] == "Say it back if it landed."

    def down(*_args, **_kwargs):
        raise urllib.error.URLError("down")

    monkeypatch.setattr("urllib.request.urlopen", down)
    with pytest.raises(DraftError, match="offline"):
        ollama_complete([{"role": "user", "content": "hi"}])

    def limited(*_args, **_kwargs):
        raise urllib.error.HTTPError(
            "http://127.0.0.1:11434/v1/chat/completions", 429, "limit", None, io.BytesIO(b"{}"),
        )

    monkeypatch.setattr("urllib.request.urlopen", limited)
    monkeypatch.setenv("HOUSE_SOCIAL_AI_MODEL", "glm-5.3:cloud")
    with pytest.raises(DraftError, match="session limit"):
        ollama_complete([{"role": "user", "content": "hi"}])


def test_a_slow_endpoint_is_not_an_offline_one(monkeypatch):
    seen = {}

    def down(*_args, **kwargs):
        seen["timeout"] = kwargs.get("timeout")
        raise urllib.error.URLError("down")

    monkeypatch.setattr("urllib.request.urlopen", down)
    monkeypatch.setenv("HOUSE_SOCIAL_AI_TIMEOUT", "180")
    with pytest.raises(DraftError, match="offline"):
        ollama_complete([{"role": "user", "content": "hi"}])
    assert seen["timeout"] == 180

    monkeypatch.setenv("HOUSE_SOCIAL_AI_TIMEOUT", "slow")
    with pytest.raises(DraftError, match="offline"):
        ollama_complete([{"role": "user", "content": "hi"}])
    assert seen["timeout"] == 60

    monkeypatch.setenv("HOUSE_SOCIAL_AI_TIMEOUT", "")
    with pytest.raises(DraftError, match="offline"):
        ollama_complete([{"role": "user", "content": "hi"}])
    assert seen["timeout"] == 60
