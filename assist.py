"""Voice-bound assistant for the composer.

The model is optional and local. A missing endpoint is an offline
assistant, not a made-up caption. Banned lines from the brand guide
are removed before anything is returned.
"""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request

from adapt import DraftError, suggest_hashtags
from voice import voice_check


ACTIONS = ("rewrite", "shorten", "expand", "variations", "hooks", "caption", "hashtags")
_COUNTS = {"variations": 3, "hooks": 5}
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)
_NUMBERED = re.compile(r"^\s*\d+[\).\]]\s*")


def assist(
    guide: dict,
    action: str,
    text: str,
    *,
    complete,
    image: bytes | None = None,
    mime: str = "",
    brand_tags: tuple[str, ...] = (),
) -> dict:
    name = (action or "").strip().lower()
    if name not in ACTIONS:
        raise DraftError("Ask for a rewrite, a shorter line, a longer line, variations, hooks, a caption, or hashtags.")
    body = (text or "").strip()
    if name == "hashtags":
        options = suggest_hashtags(body, brand_tags)
        return {"action": name, "text": "", "options": [_option(guide, item) for item in options], "source": "brand"}
    if name == "caption":
        if not image:
            raise DraftError("Attach an image before asking for a caption.")
        if mime.startswith("video/"):
            raise DraftError("Caption runs on a still image. Save a frame as an image.")
        if mime and not mime.startswith("image/"):
            raise DraftError("Caption runs on an image.")
    elif not body:
        raise DraftError("Write something first.")
    raw = complete(_messages(guide, name, body, image, mime))
    parsed = _parse(str(raw or ""))
    if name in _COUNTS:
        options = []
        for item in parsed.get("options") or []:
            cleaned = _without_banned(guide, str(item))
            if cleaned and cleaned not in {row["text"] for row in options}:
                options.append(_option(guide, cleaned))
        if not options:
            raise DraftError("The assistant used a banned line. Nothing usable was left.")
        return {"action": name, "text": "", "options": options[: _COUNTS[name]], "source": "assistant"}
    cleaned = _without_banned(guide, str(parsed.get("text") or raw or ""))
    if not cleaned:
        raise DraftError("The assistant used a banned line. Nothing usable was left.")
    return {"action": name, "text": cleaned, "options": [_option(guide, cleaned)], "source": "assistant"}


def ollama_complete(messages: list) -> str:
    url = os.environ.get("HOUSE_SOCIAL_AI_URL", "http://127.0.0.1:11434/v1/chat/completions").strip()
    model = os.environ.get("HOUSE_SOCIAL_AI_MODEL", "qwen3.5:9b").strip()
    if _has_image(messages):
        model = os.environ.get("HOUSE_SOCIAL_VISION_MODEL", "moondream").strip()
    payload = json.dumps({"model": model, "messages": messages, "stream": False, "temperature": 0.4}).encode()
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise DraftError("The assistant is offline.") from exc
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise DraftError("The assistant returned nothing usable.") from exc
    if isinstance(content, list):
        content = " ".join(str(part.get("text") or "") for part in content if isinstance(part, dict))
    text = str(content or "").strip()
    if not text:
        raise DraftError("The assistant returned nothing usable.")
    return text


def _messages(guide: dict, action: str, text: str, image: bytes | None, mime: str) -> list[dict]:
    prompts = {
        "rewrite": "Rewrite this in the brand voice.\n\n{text}",
        "shorten": "Shorten this. Keep the brand voice and the point.\n\n{text}",
        "expand": "Expand this a little. Keep the brand voice. Do not add a new claim.\n\n{text}",
        "variations": "Write three variations in the brand voice. They must not be the same sentence.\n\n{text}",
        "hooks": "Write five opening hooks in the brand voice for this idea.\n\n{text}",
        "caption": "Write a caption for the attached image in the brand voice. Describe only what is visible.\n\n{text}",
    }
    prompt = prompts[action].format(text=text or "Use the image.")
    if action in _COUNTS:
        prompt += '\n\nReturn JSON {"options": ["...", "..."]} and nothing else.'
    else:
        prompt += '\n\nReturn JSON {"text": "..."} and nothing else.'
    content: str | list = prompt
    if image:
        encoded = base64.b64encode(image).decode()
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mime or 'image/png'};base64,{encoded}"}},
        ]
    return [
        {"role": "system", "content": _system(guide)},
        {"role": "user", "content": content},
    ]


def _system(guide: dict) -> str:
    lines = [
        "You write for one brand. The voice guide is the rule. Do not sound like a generic campaign.",
        f"Tone: {guide.get('tone') or 'Plain and specific.'}",
        f"Personality: {guide.get('personality') or ''}",
    ]
    if guide.get("dos"):
        lines.append("Do: " + " ".join(guide["dos"]))
    if guide.get("donts"):
        lines.append("Don't: " + " ".join(guide["donts"]))
    banned = guide.get("banned") or []
    lines.append("Never use these phrases: " + (", ".join(banned) if banned else "none given."))
    if guide.get("required"):
        lines.append("Include: " + ", ".join(guide["required"]))
    if guide.get("second_person"):
        lines.append("Speak to you.")
    for example in (guide.get("examples") or [])[:2]:
        if example.get("text"):
            lines.append("A line that nails it: " + example["text"])
    return "\n".join(lines)


def _parse(raw: str) -> dict:
    text = raw.strip()
    fence = _FENCE.search(text)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        lines = [_NUMBERED.sub("", line).strip(" -") for line in raw.splitlines() if line.strip()]
        return {"text": raw.strip(), "options": lines}
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        return {"options": data}
    return {"text": raw.strip()}


def _without_banned(guide: dict, text: str) -> str:
    cleaned = _NUMBERED.sub("", str(text or "")).strip()
    for phrase in guide.get("banned") or []:
        if phrase.lower() in cleaned.lower():
            parts = re.split(r"(?<=[.!?])\s+", cleaned)
            kept = [part for part in parts if phrase.lower() not in part.lower()]
            cleaned = " ".join(kept).strip()
    return cleaned


def _option(guide: dict, text: str) -> dict:
    return {"text": text, "voice": voice_check(guide, text)}


def _has_image(messages: list) -> bool:
    for message in messages:
        content = message.get("content")
        if isinstance(content, list) and any(isinstance(part, dict) and part.get("type") == "image_url" for part in content):
            return True
    return False
