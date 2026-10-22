"""Brand voice for House Social.

Seeds are only the rules already written down. A saved guide replaces
those fields. The score is a checklist, not a grade of the writing.

A suggestion is kept only when both sides have three posts and the gap
is real. A percent is never invented.
"""

from __future__ import annotations

import copy
import csv
import re
from io import StringIO

from adapt import DraftError
from brands import pillars_for
from meta import redact


_FORMALITY = {"casual", "plain", "formal"}
_STOP = {
    "that", "this", "with", "from", "your", "you", "they", "them", "have", "just",
    "what", "when", "were", "been", "about", "into", "than", "then", "there",
    "their", "would", "could", "should", "because", "which", "while", "where",
    "after", "before", "those", "these", "only", "some", "more", "most", "very",
    "really", "like", "know", "want", "going", "still", "even", "over", "under",
    "such", "each", "other", "also", "will", "does", "didn", "dont", "wasn",
    "isn", "aren", "been", "being", "here", "back", "down", "away", "once",
}


def _blank() -> dict:
    return {
        "tone": "",
        "personality": "",
        "formality": "",
        "humor": "",
        "point_of_view": "",
        "dos": [],
        "donts": [],
        "visual": "",
        "banned": [],
        "preferred": [],
        "required": [],
        "differentiation": "",
        "second_person": False,
        "pillars": [],
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
        formality="casual",
        humor="Dry. Not a joke at the wound.",
        point_of_view="Second person.",
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
        formality="casual",
        humor="Rare, and never cute.",
        point_of_view="Her scene.",
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
        formality="plain",
        humor="None.",
        point_of_view="The product.",
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
        formality="casual",
        humor="None. The songs carry it.",
        point_of_view="Her songs.",
        dos=["Stay with the music and that year."],
        donts=["Don't write her in Josie's mouth."],
        visual="A night drive. Not the merch grid.",
    ),
    "the-oracle": _guide(
        tone="The Unlifting. Blackened deathcore. A Misfit Mindset release, not the shop grid.",
        personality="The record.",
        formality="plain",
        humor="None.",
        point_of_view="The record.",
        visual="The record's room. Dark, not a product tile.",
    ),
    "okay": _guide(
        tone="Spend, said plainly. A number, not a finance costume.",
        personality="The livelihood app. Not the private ledger.",
        formality="plain",
        humor="None.",
        point_of_view="The number.",
        donts=["Don't talk about the private money books."],
        visual="Plain type. The number is the picture.",
    ),
}


def guide_for(brand_id: str, override: dict | None = None) -> dict:
    guide = copy.deepcopy(SEEDS.get(brand_id) or _blank())
    guide["examples"] = _examples(guide.get("examples") or [])
    guide["pillars"] = _pillars(brand_id, None)
    for key in ("formality", "humor", "point_of_view", "differentiation", "preferred"):
        guide.setdefault(key, [] if key == "preferred" else "")
    if not isinstance(override, dict):
        return guide
    for key in ("tone", "personality", "visual", "differentiation"):
        if key in override:
            guide[key] = str(override.get(key) or "").strip()
    for key in ("humor", "point_of_view"):
        if key in override:
            guide[key] = str(override.get(key) or "").strip()[:160]
    if "formality" in override:
        guide["formality"] = _formality(override.get("formality"))
    for key in ("dos", "donts", "banned", "required", "preferred"):
        if key in override and isinstance(override.get(key), list):
            guide[key] = _lines(override.get(key))
    if "second_person" in override:
        guide["second_person"] = bool(override.get("second_person"))
    if "pillars" in override and isinstance(override.get("pillars"), list):
        guide["pillars"] = _pillars(brand_id, override.get("pillars"))
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
    preferred = [phrase for phrase in guide.get("preferred") or [] if phrase]
    if preferred and len(body) >= 40:
        hit = any(phrase.lower() in lowered for phrase in preferred)
        checks.append({"id": "preferred", "label": "Use a preferred line", "ok": hit})
    for index, example in enumerate(guide.get("examples") or []):
        if example.get("kind") != "off":
            continue
        needle = _off_needle(str(example.get("text") or ""))
        if needle and needle.lower() in lowered:
            checks.append({"id": f"off:{index}", "label": "This repeats an off-brand line", "ok": False})
    if not checks:
        return {"passed": 0, "total": 0, "checks": [{"id": "empty", "label": "No voice rules yet.", "ok": True}]}
    passed = sum(1 for item in checks if item["ok"])
    return {"passed": passed, "total": len(checks), "checks": checks}


def voice_lessons(guide: dict, posts: list[dict]) -> dict:
    usable = _usable(posts)
    if len(usable) < 6:
        return {
            "ready": False,
            "count": len(usable),
            "detail": (
                f"{len(usable)} posts have text and an engagement count. "
                "A pattern waits for 6, so each side can have 3."
            ),
            "suggestions": [],
        }
    suggestions: list[dict] = []
    _opener_suggestion(suggestions, usable, guide)
    _trait_suggestion(
        suggestions,
        usable,
        guide,
        "address:you",
        lambda post: bool(re.search(r"\byou\b", post["preview"].lower())),
        "Speak to you.",
        "second_person",
        "Posts that speak to you",
        skip=bool(guide.get("second_person")),
    )
    _trait_suggestion(
        suggestions,
        usable,
        guide,
        "question:ask",
        lambda post: "?" in post["preview"],
        "Ask a real question.",
        "preferred",
        "Posts that ask a question",
        skip=any(phrase == "?" or "question" in phrase.lower() for phrase in (guide.get("required") or []) + (guide.get("preferred") or [])),
    )
    suggestions.extend(_word_suggestions(usable, guide))
    low, high = _halves(usable)
    won = _win(high, low)
    if won:
        mean_high, mean_low = won
        detail = (
            f"The stronger half averaged {mean_high:.1f} engagements (n={len(high)}). "
            f"The quieter half averaged {mean_low:.1f} (n={len(low)})."
        )
        suggestions.extend(_example_suggestions(high, low, guide))
    else:
        detail = (
            f"{len(usable)} posts are in the pool. The stronger half and the quieter half "
            "are too close to call, so no post is marked on-brand or off-brand from the numbers."
        )
    for item in suggestions:
        if "%" in item.get("detail", ""):
            item["detail"] = item["detail"].replace("%", " percent")
    return {"ready": True, "count": len(usable), "detail": detail, "suggestions": suggestions[:12]}


def parse_voice_csv(text: str) -> list[dict]:
    raw = str(text or "")
    if len(raw) > 200_000:
        raise DraftError("That file is too big.")
    reader = csv.DictReader(StringIO(raw))
    if not reader.fieldnames:
        raise DraftError("The CSV needs a header row.")
    fields = {str(name or "").strip().lower(): name for name in reader.fieldnames}
    text_key = next((fields[name] for name in ("text", "message", "caption", "body", "post", "content") if name in fields), None)
    if text_key is None:
        raise DraftError("The CSV needs a text, message, caption, or body column.")
    eng_key = fields.get("engagements") or fields.get("engagement")
    share_key = fields.get("shares") or fields.get("share")
    date_key = fields.get("date") or fields.get("published_at") or fields.get("published")
    platform_key = fields.get("platform")
    rows = []
    for record in reader:
        body = str(record.get(text_key) or "").strip()
        if not body:
            continue
        published = str(record.get(date_key) or "").strip() if date_key else ""
        if not re.match(r"\d{4}-\d{2}-\d{2}", published):
            published = ""
        platform = str(record.get(platform_key) or "").strip().lower() if platform_key else ""
        if platform not in {"facebook", "instagram", "threads"}:
            platform = ""
        rows.append(
            {
                "text": redact(body)[:500],
                "engagements": _optional_int(record.get(eng_key)) if eng_key else None,
                "shares": _optional_int(record.get(share_key)) if share_key else 0,
                "published_at": published[:40],
                "platform": platform,
            }
        )
        if len(rows) >= 200:
            break
    if not rows:
        raise DraftError("No posts were in that file.")
    return rows


def _opener_suggestion(suggestions: list[dict], posts: list[dict], guide: dict) -> None:
    short = [post for post in posts if 0 < _opener_words(post["preview"]) <= 8]
    long = [post for post in posts if _opener_words(post["preview"]) > 8]
    won = _win(short, long)
    if not won:
        return
    line = "Open with a short first sentence."
    if _already(guide, line):
        return
    mean_yes, mean_no = won
    suggestions.append(
        {
            "id": "opener:short",
            "clear": True,
            "kind": "preferred",
            "line": line,
            "detail": (
                f"Posts with a short first sentence averaged {mean_yes:.1f} engagements (n={len(short)}). "
                f"The others averaged {mean_no:.1f} (n={len(long)})."
            ),
            "example": None,
        }
    )


def _trait_suggestion(suggestions, posts, guide, suggestion_id, holds, line, kind, label, skip: bool) -> None:
    if skip or _already(guide, line):
        return
    yes = [post for post in posts if holds(post)]
    no = [post for post in posts if not holds(post)]
    won = _win(yes, no)
    if not won:
        return
    mean_yes, mean_no = won
    suggestions.append(
        {
            "id": suggestion_id,
            "clear": True,
            "kind": kind,
            "line": line,
            "detail": (
                f"{label} averaged {mean_yes:.1f} engagements (n={len(yes)}). "
                f"The others averaged {mean_no:.1f} (n={len(no)})."
            ),
            "example": None,
        }
    )


def _word_suggestions(posts: list[dict], guide: dict) -> list[dict]:
    known = {phrase.lower() for phrase in (guide.get("preferred") or []) + (guide.get("banned") or [])}
    counts: dict[str, list[dict]] = {}
    for post in posts:
        for word in set(_tokens(post["preview"])):
            counts.setdefault(word, []).append(post)
    ranked = []
    for word, yes in counts.items():
        if word in known or len(yes) < 3:
            continue
        no = [post for post in posts if post not in yes]
        won = _win(yes, no)
        if not won:
            continue
        mean_yes, mean_no = won
        ranked.append((mean_yes - mean_no, word, yes, no, mean_yes, mean_no))
    ranked.sort(key=lambda item: item[0], reverse=True)
    rows = []
    for _gap, word, yes, no, mean_yes, mean_no in ranked[:3]:
        rows.append(
            {
                "id": f"word:{word}",
                "clear": True,
                "kind": "preferred",
                "line": word,
                "detail": (
                    f"Posts that say “{word}” averaged {mean_yes:.1f} engagements (n={len(yes)}). "
                    f"The others averaged {mean_no:.1f} (n={len(no)})."
                ),
                "example": None,
            }
        )
    return rows


def _example_suggestions(high: list[dict], low: list[dict], guide: dict) -> list[dict]:
    known = {str(item.get("text") or "").strip().lower() for item in guide.get("examples") or []}
    rows = []
    for kind, pool in (("on", sorted(high, key=lambda post: int(post["engagements"]), reverse=True)), ("off", sorted(low, key=lambda post: int(post["engagements"])))):
        for post in pool:
            text = post["preview"].strip()
            if text.lower() in known or not post.get("id"):
                continue
            rows.append(
                {
                    "id": f"example:{kind}:{post['id']}",
                    "clear": True,
                    "kind": "example",
                    "line": "",
                    "detail": f"{int(post['engagements'])} engagements. Kept as an {kind}-brand example from the posts, not from a guess.",
                    "example": {
                        "title": f"{int(post['engagements'])} engagements",
                        "text": text[:500],
                        "kind": kind,
                        "source": "pulled",
                    },
                }
            )
            if sum(1 for item in rows if item["example"]["kind"] == kind) >= 3:
                break
    return rows


def _usable(posts: list[dict]) -> list[dict]:
    rows = []
    seen = set()
    for post in posts or []:
        text = redact(str(post.get("preview") or post.get("text") or "")).strip()
        if not text or post.get("engagements") is None:
            continue
        key = str(post.get("id") or text)
        if key in seen:
            continue
        seen.add(key)
        rows.append({**post, "id": key, "preview": text[:500], "engagements": int(post.get("engagements") or 0)})
    return rows


def _halves(posts: list[dict]) -> tuple[list[dict], list[dict]]:
    ordered = sorted(posts, key=lambda post: int(post["engagements"]))
    mid = len(ordered) // 2
    return ordered[:mid], ordered[mid:]


def _win(yes: list[dict], no: list[dict]) -> tuple[float, float] | None:
    if len(yes) < 3 or len(no) < 3:
        return None
    mean_yes = sum(int(post["engagements"]) for post in yes) / len(yes)
    mean_no = sum(int(post["engagements"]) for post in no) / len(no)
    if mean_yes <= mean_no:
        return None
    if mean_yes < mean_no * 1.5 or (mean_yes - mean_no) < 3:
        return None
    return mean_yes, mean_no


def _already(guide: dict, line: str) -> bool:
    return line.lower() in {phrase.lower() for phrase in guide.get("preferred") or []}


def _opener_words(text: str) -> int:
    sentence = re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)[0]
    return len(re.findall(r"[A-Za-z0-9']+", sentence))


def _tokens(text: str) -> list[str]:
    return [word for word in re.findall(r"[a-z']{4,}", text.lower()) if word not in _STOP and "'" not in word]


def _off_needle(text: str) -> str:
    sentence = re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)[0]
    if len(re.findall(r"[A-Za-z0-9']+", sentence)) < 4:
        return ""
    return sentence[:80]


def _formality(value: object) -> str:
    text = str(value or "").strip().lower()
    return text if text in _FORMALITY else ""


def _optional_int(value: object) -> int | None:
    text = str(value or "").strip().replace(",", "")
    if not re.fullmatch(r"\d+", text):
        return None
    number = int(text)
    if number > 10_000_000:
        return None
    return number


def _lines(values) -> list[str]:
    rows = []
    for value in values:
        text = str(value or "").strip()
        if text and text.lower() not in {row.lower() for row in rows}:
            rows.append(text[:160] if len(text) > 160 else text)
    return rows[:12]


def _examples(values) -> list[dict]:
    rows = []
    for value in values:
        if not isinstance(value, dict):
            continue
        text = redact(str(value.get("text") or "")).strip()
        if not text:
            continue
        kind = value.get("kind") if value.get("kind") in {"on", "off"} else "on"
        source = value.get("source") if value.get("source") in {"written", "saved", "pulled"} else "written"
        rows.append(
            {
                "title": str(value.get("title") or "").strip()[:80],
                "text": text[:500],
                "kind": kind,
                "source": source,
            }
        )
    return rows[:12]


def _pillars(brand_id: str, saved) -> list[dict]:
    known = {item["id"]: item for item in pillars_for(brand_id)}
    if not isinstance(saved, list):
        return [{"id": item["id"], "name": item["name"], "angles": []} for item in pillars_for(brand_id)]
    rows = []
    for item in saved:
        if not isinstance(item, dict):
            continue
        pillar_id = str(item.get("id") or "").strip()[:40]
        name = str(item.get("name") or "").strip()[:80]
        if pillar_id in known:
            name = known[pillar_id]["name"]
        if not name:
            continue
        angles = []
        for line in _lines(item.get("angles") or []):
            angles.append(line[:160])
            if len(angles) == 3:
                break
        rows.append({"id": pillar_id or _slug(name), "name": name, "angles": angles})
        if len(rows) == 6:
            break
    return rows


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:40] or "pillar"
