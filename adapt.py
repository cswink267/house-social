"""Shape one idea into three platform drafts.

The words stay the author's. The shape changes so Facebook, Instagram,
and Threads are not the same post in three costumes.
"""

from __future__ import annotations

import re

from brands import PLATFORMS, Brand


class DraftError(ValueError):
    """The idea cannot be shaped."""


_HASHTAG = re.compile(r"(?<!\w)#([A-Za-z0-9_]+)")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_SPACE = re.compile(r"[ \t]{2,}")
_BLANKS = re.compile(r"\n{3,}")

LIMITS = {"facebook": 5000, "instagram": 2200, "threads": 500}
JOSIE_CARD = 240


def shape(brand: Brand, idea: str) -> dict[str, dict]:
    """Return facebook, instagram, and threads variants for one idea."""
    body, pulled = _prepare(idea)
    tags = _tags(pulled, brand.tags)
    variants = {
        "facebook": _facebook(brand, body),
        "instagram": _instagram(brand, body, tags),
        "threads": _threads(body),
    }
    _mark_matching_threads(variants)
    return variants


def issues(brand: Brand, variants: dict[str, dict]) -> list[str]:
    """Reasons a piece is not ready to leave the queue."""
    found: list[str] = []
    bodies = [_body(variants, platform) for platform in PLATFORMS]
    if len(set(bodies)) < len(PLATFORMS):
        found.append(
            "Facebook, Instagram, and Threads still share the same words. Change one before this is ready."
        )
    if any(len(body) > LIMITS[platform] for platform, body in zip(PLATFORMS, bodies)):
        found.append("One of the posts is over its platform limit.")
    if "#" in _body(variants, "instagram"):
        found.append("Move Instagram hashtags out of the caption.")
    joined = "\n".join(bodies).lower()
    if brand.id != "jamhaul" and "jamhaul.com" in joined:
        found.append("JamHaul does not ride on this brand.")
    if brand.id == "jamhaul":
        facebook = _body(variants, "facebook")
        if "jamhaul.com" not in facebook.lower():
            found.append("JamHaul posts include jamhaul.com.")
        if "?" not in facebook:
            found.append("JamHaul posts end on a question you wrote.")
    if brand.id == "josie-blackthorn" and not variants.get("facebook", {}).get("image_ready"):
        found.append("Josie Facebook needs the quote image before it is ready.")
    return found


def _prepare(idea: str) -> tuple[str, list[str]]:
    text = (idea or "").strip()
    if not text:
        raise DraftError("Write the idea first.")
    if len(text) > 8000:
        raise DraftError("The idea is too long to shape in one pass.")
    pulled = _HASHTAG.findall(text)
    body = _HASHTAG.sub("", text)
    body = _SPACE.sub(" ", body)
    body = _BLANKS.sub("\n\n", body).strip()
    if not body:
        raise DraftError("The idea was only hashtags. Write the sentence.")
    return body, pulled


def _tags(pulled: list[str], brand_tags: tuple[str, ...]) -> list[str]:
    seen: list[str] = []
    for tag in [*pulled, *brand_tags]:
        clean = tag.strip().lstrip("#")
        if clean and clean.lower() not in {item.lower() for item in seen}:
            seen.append(clean)
    return seen[:5]


def _facebook(brand: Brand, body: str) -> dict:
    note = ""
    needs_image = False
    text = body
    if brand.id == "josie-blackthorn":
        needs_image = True
        note = "Josie Facebook ships as a quote image. This line is the card, not a text post."
        text = _clip(_sentences(body)[0], JOSIE_CARD)[0]
    elif brand.id == "jamhaul":
        note = "Plain product voice. Keep jamhaul.com, and end on a question you wrote."
        if "jamhaul.com" not in text.lower():
            text = text.rstrip() + "\n\njamhaul.com"
    return _variant(text, [], needs_image, note)


def _instagram(brand: Brand, body: str, tags: list[str]) -> dict:
    text, _trimmed = _clip(body.rstrip() + "\n\n" + brand.name, LIMITS["instagram"])
    return _variant(text, tags, False, "Hashtags stay in their own field.")


def _threads(body: str) -> dict:
    sentences = _sentences(body)
    text = sentences[0] if len(sentences) >= 2 else body
    text, trimmed = _clip(text, LIMITS["threads"])
    note = ""
    if text != body:
        note = "Threads carries the first thought. The rest stays on Facebook."
    if trimmed and not note:
        note = "Threads was cut to 500 characters."
    return _variant(text, [], False, note)


def _variant(body: str, hashtags: list[str], needs_image: bool, note: str) -> dict:
    return {
        "body": body,
        "hashtags": list(hashtags),
        "needs_image": needs_image,
        "image_ready": False,
        "note": note,
    }


def _sentences(text: str) -> list[str]:
    parts = [part.strip() for part in _SENTENCE.split(text.strip()) if part.strip()]
    return parts or [text.strip()]


def _clip(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    cut = text[:limit].rsplit(" ", 1)[0].rstrip()
    if len(cut) < limit // 2:
        cut = text[:limit].rstrip()
    return cut, True


def _body(variants: dict, platform: str) -> str:
    variant = variants.get(platform) or {}
    body = variant.get("body", "")
    return body.strip() if isinstance(body, str) else ""


def _mark_matching_threads(variants: dict[str, dict]) -> None:
    """A one-line idea can still match Facebook and Threads. Say so."""
    if _body(variants, "facebook") != _body(variants, "threads"):
        return
    note = variants["threads"]["note"]
    extra = "Threads still matches Facebook. Rewrite this one before it is ready."
    variants["threads"]["note"] = f"{note} {extra}".strip() if note else extra
