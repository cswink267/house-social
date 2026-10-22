"""Brand voice for House Social.

Seeds are only the rules already written down. A saved guide replaces
those fields. The score is a checklist, not a grade of the writing.
"""

from __future__ import annotations

import copy
import re


def _blank() -> dict:
    return {
        "tone": "",
        "personality": "",
        "dos": [],
        "donts": [],
        "visual": "",
        "banned": [],
        "required": [],
        "second_person": False,
        "examples": [],
    }


def _guide(**kwargs) -> dict:
    guide = _blank()
    guide.update(kwargs)
    return guide


SEEDS = {
    "misfit-mindset": _guide(
        tone="Second person. Short paragraphs. Name the hard thing, then tell them it is not their fault.",
        personality="In it with them, not above them. Direct, warm, and unwilling to paste cheer on a wound.",
        dos=[
            "Write you, not people or one.",
            "Validate the feeling before any reframe.",
            "End with something they can actually do.",
            "Bold the line that has to land.",
        ],
        donts=[
            "Toxic positivity. No good vibes only, no just stay positive.",
            "Cheerful for the sake of cheerful.",
            "Clinical distance.",
            "A generic description where a specific moment would land.",
        ],
        visual="Obsidian and ember. Built for a phone scroll. Line breaks do the work.",
        banned=["good vibes only", "just stay positive", "we're excited", "rise and grind"],
        second_person=True,
        examples=[
            {
                "title": "The line that lands",
                "text": "That dread you feel? It's not weakness. It's data.",
            }
        ],
    ),
    "josie-blackthorn": _guide(
        tone="Human, often lowercase, one concrete scene. The Facebook line is the quote on the card.",
        personality="The person. Not a campaign, and not a mascot for the other brands.",
        dos=[
            "One scene a person could be standing in.",
            "The card line has to stand alone.",
        ],
        donts=[
            "Don't write her as software, a bot, or an assistant.",
            "Don't put JamHaul, the shop, or another page's promo in her mouth.",
            "Don't open with There's a.",
        ],
        visual="A 1080 square quote card. Obsidian and ember. The caption is not the post.",
        banned=["there's a", "we're excited", "good vibes only"],
        examples=[
            {
                "title": "A card line",
                "text": "Some CDs hid a song behind ten minutes of silence. You only got it if you were still there.",
            }
        ],
    ),
    "jamhaul": _guide(
        tone="Plain English. One problem, one fix, then a question.",
        personality="The product. Honest about the price. Two dollars, not ten.",
        dos=[
            "Say jamhaul.com.",
            "Ask a question you actually mean.",
            "Talk about the screenshot.",
        ],
        donts=[
            "No metalcore voice.",
            "No private life.",
            "No launch-announcement voice.",
        ],
        visual="A live screenshot of jamhaul.com. Not a mood board.",
        banned=["we're excited", "unleash", "game-changer"],
        required=["jamhaul.com", "?"],
    ),
    "rowan-blackthorn": _guide(
        tone="The songs. Synthwave and darkwave. Seventeen is the year between sixteen and eighteen.",
        personality="Her. Not Josie speaking through her.",
        dos=["Stay with the music and that year."],
        donts=["Don't write her in Josie's mouth."],
        visual="A night drive. Not the merch grid.",
    ),
    "the-oracle": _guide(
        tone="The Unlifting. Blackened deathcore. A Misfit Mindset release, not the shop grid.",
        personality="The record.",
        visual="The record's room. Dark, not a product tile.",
    ),
    "okay": _guide(
        tone="Spend, said plainly. A number, not a finance costume.",
        personality="The livelihood app. Not the private ledger.",
        donts=["Don't talk about the private money books."],
        visual="Plain type. The number is the picture.",
    ),
}


def guide_for(brand_id: str, override: dict | None = None) -> dict:
    guide = copy.deepcopy(SEEDS.get(brand_id) or _blank())
    if not isinstance(override, dict):
        return guide
    for key in ("tone", "personality", "visual"):
        if key in override:
            guide[key] = str(override.get(key) or "").strip()
    for key in ("dos", "donts", "banned", "required"):
        if key in override and isinstance(override.get(key), list):
            guide[key] = _lines(override.get(key))
    if "second_person" in override:
        guide["second_person"] = bool(override.get("second_person"))
    if "examples" in override and isinstance(override.get("examples"), list):
        guide["examples"] = _examples(override.get("examples"))
    return guide


def voice_report(guide: dict, fields: dict) -> dict:
    reports = []
    for key in ("idea", "facebook", "instagram", "threads"):
        text = str((fields or {}).get(key) or "")
        if not text.strip():
            continue
        reports.append({"field": key, **voice_check(guide, text)})
    if not reports:
        return {"passed": 0, "total": 0, "label": "Write something first.", "fields": []}
    passed = sum(item["passed"] for item in reports)
    total = sum(item["total"] for item in reports)
    label = f"Voice {passed}/{total}" if total else "No voice rules yet."
    return {"passed": passed, "total": total, "label": label, "fields": reports}


def voice_check(guide: dict, text: str) -> dict:
    checks = []
    body = text.strip()
    lowered = body.lower()
    for phrase in guide.get("banned") or []:
        checks.append({"id": f"banned:{phrase}", "label": f"Leave out “{phrase}”", "ok": phrase.lower() not in lowered})
    for phrase in guide.get("required") or []:
        present = phrase in body if phrase == "?" else phrase.lower() in lowered
        checks.append({"id": f"need:{phrase}", "label": f"Include {phrase}", "ok": present})
    if guide.get("second_person") and len(body) >= 40:
        checks.append({"id": "second-person", "label": "Speak to you", "ok": bool(re.search(r"\byou\b", lowered))})
    if not checks:
        return {"passed": 0, "total": 0, "checks": [{"id": "empty", "label": "No voice rules yet.", "ok": True}]}
    passed = sum(1 for item in checks if item["ok"])
    return {"passed": passed, "total": len(checks), "checks": checks}


def _lines(values) -> list[str]:
    rows = []
    for value in values:
        text = str(value or "").strip()
        if text and text.lower() not in {row.lower() for row in rows}:
            rows.append(text)
    return rows[:12]


def _examples(values) -> list[dict]:
    rows = []
    for value in values:
        if not isinstance(value, dict):
            continue
        text = str(value.get("text") or "").strip()
        if not text:
            continue
        rows.append({"title": str(value.get("title") or "").strip()[:80], "text": text[:500]})
    return rows[:3]
