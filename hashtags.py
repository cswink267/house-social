"""Saved hashtag sets and the tags posts actually used.

A set can name a pillar or a campaign. A tag is suggested only when
this brand's posts already show it ahead. A trend note is not a live chart.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from adapt import DraftError
from brands import pillars_for
from learn import MIN_SAMPLE, format_table
from store import _find, _label, resolve_brand, save, update_piece


_TAG = re.compile(r"(?<!\w)#([A-Za-z0-9_]+)")
_KINDS = ("topic", "sound", "format")
_SET_LIMIT = 5


def hashtags_for(state: dict, brand_id: str, posts: list[dict] | None = None) -> dict:
    brand = resolve_brand(state, brand_id)
    owned = [item for item in posts or [] if _belongs(item, brand.id, state)]
    pieces = [piece for piece in state.get("pieces") or [] if piece.get("brand_id") == brand.id]
    stored_sets = [item for item in state.get("hashtag_sets") or [] if item.get("brand_id") == brand.id]
    sets = [_set_view(item, owned, pieces) for item in stored_sets]
    tags = _tag_rows(owned, pieces)
    formats = _formats(owned)
    trends = [
        _trend_view(item, owned, pieces, formats)
        for item in state.get("trends") or []
        if item.get("brand_id") == brand.id
    ]
    words = _niche_words(brand)
    feed = [item for item in trends if _in_niche(item, words)]
    outside = [item for item in trends if item not in feed]
    blocked = _banned_words(brand.id, state)
    from feedback import apply_tags

    return {
        "sets": sets,
        "tags": tags,
        "formats": formats,
        "trends": trends,
        "feed": feed,
        "outside": outside,
        "niche": _niche_line(words),
        "suggestion": apply_tags(_suggestion(tags, blocked, "brand"), state, brand.id),
        "by_pillar": _by_pillar(brand.id, sets, tags, blocked),
        "pillars": pillars_for(brand.id),
        "campaigns": [
            item.get("name") or ""
            for item in state.get("campaigns") or []
            if item.get("brand_id") == brand.id and item.get("name")
        ],
        "kinds": list(_KINDS),
    }


def save_set(state: dict, brand_id: str, spec: dict, path: Path | None = None) -> dict:
    brand = resolve_brand(state, brand_id)
    if not isinstance(spec, dict):
        raise DraftError("The set needs a name and tags.")
    name = _label(spec.get("name") or "", 40)
    tags = _clean_tags(spec.get("tags") or [])
    if not name or not tags:
        raise DraftError("The set needs a name and tags.")
    if any(
        str(item.get("name") or "").lower() == name.lower()
        for item in state.get("hashtag_sets") or []
        if item.get("brand_id") == brand.id
    ):
        raise DraftError("This brand already has that set.")
    row = {
        "id": str(uuid.uuid4()),
        "brand_id": brand.id,
        "name": name,
        "tags": tags,
        "pillar": _label(spec.get("pillar") or "", 40),
        "campaign": _label(spec.get("campaign") or "", 48),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    save({**state, "hashtag_sets": [row, *(state.get("hashtag_sets") or [])]}, path)
    return _set_public(row)


def save_trend(state: dict, brand_id: str, spec: dict, path: Path | None = None) -> dict:
    brand = resolve_brand(state, brand_id)
    if not isinstance(spec, dict):
        raise DraftError("The note needs a name.")
    kind = str(spec.get("kind") or "").strip().lower()
    if kind not in _KINDS:
        raise DraftError("A trend note is a topic, a sound, or a format.")
    name = _label(spec.get("name") or "", 80)
    if not name:
        raise DraftError("The note needs a name.")
    row = {
        "id": str(uuid.uuid4()),
        "brand_id": brand.id,
        "kind": kind,
        "name": name,
        "note": _label(spec.get("note") or "", 240),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    save({**state, "trends": [row, *(state.get("trends") or [])]}, path)
    return _trend_public(row)


def apply_set(state: dict, set_id: str, piece_id: str, path: Path | None = None) -> dict:
    row = next((item for item in state.get("hashtag_sets") or [] if item.get("id") == set_id), None)
    if row is None:
        raise DraftError("That set is not on this brand.")
    _index, piece = _find(state, piece_id)
    if piece.get("brand_id") != row.get("brand_id"):
        raise DraftError("That piece belongs to another brand.")
    update_piece(state, piece_id, variants={"instagram": {"hashtags": list(row.get("tags") or [])}}, path=path)
    return {"piece_id": piece_id, "tags": list(row.get("tags") or [])}


def use_ahead(
    state: dict,
    brand_id: str,
    piece_id: str,
    posts: list[dict] | None = None,
    pillar: str = "",
    path: Path | None = None,
) -> dict:
    resolve_brand(state, brand_id)
    view = hashtags_for(state, brand_id, posts)
    named = str(pillar or "").strip()
    if named:
        chosen = next((item for item in view["by_pillar"] if item["pillar"] == named), None)
        tags = list((chosen or {}).get("tags") or [])
        if not tags:
            raise DraftError("No hashtag is clearly ahead for this pillar.")
    else:
        tags = list(view["suggestion"]["tags"])
        if not tags:
            raise DraftError("No hashtag is clearly ahead for this brand.")
    _index, piece = _find(state, piece_id)
    if piece.get("brand_id") != brand_id:
        raise DraftError("That piece belongs to another brand.")
    update_piece(state, piece_id, variants={"instagram": {"hashtags": tags}}, path=path)
    return {"piece_id": piece_id, "tags": tags, "detail": view["suggestion"]["detail"]}


def _tag_rows(posts: list[dict], pieces: list[dict]) -> list[dict]:
    tagged = [(post, _post_tags(post, pieces)) for post in posts]
    names: list[str] = []
    for _post, tags in tagged:
        for tag in tags:
            if tag.lower() not in {item.lower() for item in names}:
                names.append(tag)
    rows = []
    for tag in names:
        yes = [post for post, tags in tagged if tag.lower() in {item.lower() for item in tags}]
        no = [post for post, tags in tagged if tag.lower() not in {item.lower() for item in tags}]
        mean_yes = _mean(yes)
        mean_no = _mean(no)
        clear = (
            len(yes) >= MIN_SAMPLE
            and len(no) >= MIN_SAMPLE
            and abs(mean_yes - mean_no) >= 3
            and max(mean_yes, mean_no) >= min(mean_yes, mean_no) * 1.5
        )
        if len(yes) < MIN_SAMPLE or len(no) < MIN_SAMPLE:
            detail = f"#{tag} is on {len(yes)} posts. A comparison waits for {MIN_SAMPLE} with it and {MIN_SAMPLE} without it."
        elif not clear:
            detail = f"#{tag} is too close to call. {mean_yes:.1f} (n={len(yes)}) against {mean_no:.1f} without it (n={len(no)})."
        elif mean_yes > mean_no:
            detail = f"#{tag} averaged {mean_yes:.1f} engagements (n={len(yes)}). Without it, {mean_no:.1f} (n={len(no)})."
        else:
            detail = f"#{tag} averaged less: {mean_yes:.1f} (n={len(yes)}) against {mean_no:.1f} without it (n={len(no)})."
        rows.append({
            "tag": tag,
            "n": len(yes),
            "mean": round(mean_yes, 1),
            "clear": clear,
            "ahead": clear and mean_yes > mean_no,
            "detail": detail,
        })
    rows.sort(key=lambda item: (not item["clear"], -item["mean"], item["tag"].lower()))
    return rows


def _formats(posts: list[dict]) -> dict:
    known = [post for post in posts if post.get("format") not in (None, "", "unknown")]
    rows = format_table(known)
    ready = [row for row in rows if row["n"] >= MIN_SAMPLE]
    clear = False
    leader = ""
    detail = "No format in these posts has enough uses to compare."
    if len(ready) >= 2:
        best = max(ready, key=lambda row: row["mean"])
        others = [row for row in ready if row["id"] != best["id"]]
        rest = sum(row["mean"] for row in others) / len(others)
        clear = best["mean"] >= rest * 1.5 and best["mean"] - rest >= 3
        if clear:
            leader = best["label"]
            detail = f"{best['label']} leads at {best['mean']} (n={best['n']}). The other measured formats sit near {round(rest, 1)}."
        else:
            detail = f"No format is clearly ahead. {best['label']} is highest at {best['mean']} (n={best['n']})."
    elif len(ready) == 1:
        detail = f"Only {ready[0]['label']} has {ready[0]['n']} posts. That is not a comparison."
    return {"rows": rows, "clear": clear, "leader": leader, "detail": detail}


def _post_tags(post: dict, pieces: list[dict]) -> list[str]:
    found = _clean_tags(post.get("hashtags") or [])
    found.extend(_TAG.findall(str(post.get("preview") or "")))
    piece_id = str(post.get("piece_id") or "")
    if piece_id:
        piece = next((item for item in pieces if item.get("id") == piece_id), None)
        instagram = ((piece or {}).get("variants") or {}).get("instagram") or {}
        found.extend(_clean_tags(instagram.get("hashtags") or []))
    return _clean_tags(found)


def _clean_tags(values) -> list[str]:
    if isinstance(values, str):
        values = values.replace("#", " ").split(",")
        if len(values) == 1:
            values = values[0].split()
    rows = []
    for value in values or []:
        text = str(value or "").strip().lstrip("#")
        if text and text.lower() not in {row.lower() for row in rows}:
            rows.append(text[:40])
    return rows[:_SET_LIMIT]


def _belongs(post: dict, brand_id: str, state: dict) -> bool:
    posted_brand = post.get("brand_id")
    if posted_brand:
        return posted_brand == brand_id
    piece_id = str(post.get("piece_id") or "")
    if not piece_id:
        return True
    piece = next((item for item in state.get("pieces") or [] if item.get("id") == piece_id), None)
    return bool(piece and piece.get("brand_id") == brand_id)


def _mean(posts: list[dict]) -> float:
    if not posts:
        return 0.0
    return sum(int(post.get("engagements") or 0) for post in posts) / len(posts)


def _set_public(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "name": row.get("name") or "",
        "tags": list(row.get("tags") or []),
        "pillar": row.get("pillar") or "",
        "campaign": row.get("campaign") or "",
    }


def _set_view(row: dict, posts: list[dict], pieces: list[dict]) -> dict:
    public = _set_public(row)
    public["performance"] = _set_gap(list(row.get("tags") or []), posts, pieces)
    return public


def _set_gap(tags: list[str], posts: list[dict], pieces: list[dict]) -> dict:
    wanted = {tag.lower() for tag in tags}
    if not wanted:
        return {"clear": False, "ahead": False, "detail": "This set has no tags."}
    yes = []
    no = []
    for post in posts:
        found = {tag.lower() for tag in _post_tags(post, pieces)}
        if wanted <= found:
            yes.append(post)
        elif not wanted & found:
            no.append(post)
    return _gap(f"This set", yes, no, "with every tag", "with none of them")


def _gap(name: str, yes: list[dict], no: list[dict], yes_label: str, no_label: str) -> dict:
    mean_yes = _mean(yes)
    mean_no = _mean(no)
    clear = (
        len(yes) >= MIN_SAMPLE
        and len(no) >= MIN_SAMPLE
        and abs(mean_yes - mean_no) >= 3
        and max(mean_yes, mean_no) >= min(mean_yes, mean_no) * 1.5
        and mean_yes != mean_no
    )
    if len(yes) < MIN_SAMPLE or len(no) < MIN_SAMPLE:
        detail = f"{name} is on {len(yes)} posts. A comparison waits for {MIN_SAMPLE} {yes_label} and {MIN_SAMPLE} {no_label}."
        return {"clear": False, "ahead": False, "detail": detail}
    if not clear:
        detail = f"{name} is too close to call. {mean_yes:.1f} (n={len(yes)}) against {mean_no:.1f} (n={len(no)})."
        return {"clear": False, "ahead": False, "detail": detail}
    if mean_yes > mean_no:
        detail = f"{name} averaged {mean_yes:.1f} engagements (n={len(yes)}). The other side averaged {mean_no:.1f} (n={len(no)})."
        return {"clear": True, "ahead": True, "detail": detail}
    detail = f"{name} averaged less: {mean_yes:.1f} (n={len(yes)}) against {mean_no:.1f} (n={len(no)})."
    return {"clear": True, "ahead": False, "detail": detail}


def _suggestion(tags: list[dict], blocked: set[str], scope: str) -> dict:
    chosen = [item["tag"] for item in tags if item.get("ahead") and item["tag"].lower() not in blocked][:_SET_LIMIT]
    if not chosen:
        who = "this pillar" if scope == "pillar" else "this brand"
        return {"tags": [], "detail": f"No hashtag is clearly ahead for {who}."}
    return {"tags": chosen, "detail": "These tags are ahead on this brand's posts. This is not a popularity chart."}


def _by_pillar(brand_id: str, sets: list[dict], tags: list[dict], blocked: set[str]) -> list[dict]:
    ahead = {item["tag"].lower(): item["tag"] for item in tags if item.get("ahead")}
    rows = []
    for pillar in pillars_for(brand_id):
        allowed = set()
        for item in sets:
            if item.get("pillar") == pillar["id"]:
                allowed.update(tag.lower() for tag in item.get("tags") or [])
        chosen = [ahead[key] for key in ahead if key in allowed and key not in blocked][:_SET_LIMIT]
        suggestion = _suggestion(
            [{"tag": tag, "ahead": True} for tag in chosen],
            set(),
            "pillar",
        )
        rows.append({"pillar": pillar["id"], "name": pillar["name"], "tags": suggestion["tags"], "detail": suggestion["detail"]})
    return rows


def _niche_words(brand) -> set[str]:
    words = set()
    for tag in brand.tags:
        for word in str(tag).lower().replace("-", " ").split():
            if len(word) >= 4:
                words.add(word)
    for pillar in pillars_for(brand.id):
        for source in (pillar.get("id") or "", pillar.get("name") or ""):
            for word in str(source).lower().replace("-", " ").split():
                if len(word) >= 4:
                    words.add(word)
    return words


def _niche_line(words: set[str]) -> str:
    if not words:
        return "This brand has no pillar or tag words to filter on."
    shown = ", ".join(sorted(words)[:12])
    return f"Niche words from this brand: {shown}."


def _in_niche(trend: dict, words: set[str]) -> bool:
    text = f"{trend.get('name') or ''} {trend.get('note') or ''}".lower()
    return any(re.search(rf"\b{re.escape(word)}\b", text) for word in words)


def _trend_view(row: dict, posts: list[dict], pieces: list[dict], formats: dict) -> dict:
    public = _trend_public(row)
    public["result"] = _trend_result(row, posts, pieces, formats)
    return public


def _trend_result(row: dict, posts: list[dict], pieces: list[dict], formats: dict) -> str:
    if row.get("kind") == "format":
        leader = str(formats.get("leader") or "")
        if formats.get("clear") and str(row.get("name") or "").lower() == leader.lower():
            return f"{leader} is ahead on this brand's posts. This is not a popularity chart."
        return "This note is saved. The posts do not show this format ahead."
    name = str(row.get("name") or "").strip().lower()
    if len(name) < 4 or not posts:
        return "This note is saved. It is not a popularity chart."
    yes = [post for post in posts if name in str(post.get("preview") or "").lower()]
    no = [post for post in posts if name not in str(post.get("preview") or "").lower()]
    compared = _gap(row.get("name") or "This note", yes, no, "that mention it", "that do not")
    if compared["ahead"]:
        return f"{compared['detail']} This is not a popularity chart."
    return "This note is saved. The posts do not show it ahead."


def _banned_words(brand_id: str, state: dict) -> set[str]:
    from voice import guide_for

    guide = guide_for(brand_id, (state.get("voices") or {}).get(brand_id))
    words = set()
    for phrase in guide.get("banned") or []:
        for word in str(phrase).lower().split():
            token = word.strip(".,'\"")
            if len(token) >= 3:
                words.add(token)
    return words


def _trend_public(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "kind": row.get("kind") or "topic",
        "name": row.get("name") or "",
        "note": row.get("note") or "",
        "rising": False,
        "result": "This note is saved. It is not a popularity chart.",
    }
