"""Named campaigns for one brand.

A campaign groups the pieces and assets that belong to it, plus a goal
and the dates. A kind is called ahead only when both sides have three
posts and the gap is real. Nothing here is sent.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from pathlib import Path

from adapt import DraftError
from learn import analytics
from store import _find, _label, resolve_brand, save


KINDS = ("launch", "seasonal", "evergreen")
_MAKING = {"draft", "planned", "ready"}
_OUT = {"pending", "scheduled", "failed"}


def campaigns_for(state: dict, brand_id: str, posts: list[dict] | None = None, today: date | None = None) -> dict:
    brand = resolve_brand(state, brand_id)
    when = today or datetime.now().date()
    history = list(posts or [])
    lessons = kind_lessons(state, brand.id, history)
    rows = [
        _view(state, campaign, history, when, lessons)
        for campaign in state.get("campaigns") or []
        if campaign.get("brand_id") == brand.id
    ]
    rows.sort(key=lambda item: (item.get("start") or "9999", item.get("name") or ""))
    return {"campaigns": rows, "kinds": list(KINDS), "lessons": lessons}


def save_campaign(state: dict, brand_id: str, spec: dict, path: Path | None = None) -> dict:
    brand = resolve_brand(state, brand_id)
    campaign = _new(brand.id, spec, state)
    updated = {**state, "campaigns": [campaign, *(state.get("campaigns") or [])]}
    updated = _claim_named_pieces(updated, campaign)
    save(updated, path)
    return _view(updated, campaign, [], datetime.now().date())


def revise_campaign(state: dict, campaign_id: str, spec: dict, path: Path | None = None) -> dict:
    index, current = _campaign(state, campaign_id)
    revised = _new(
        current["brand_id"],
        {**current, **spec, "kind": spec.get("kind") or current["kind"]},
        state,
        campaign_id=current["id"],
    )
    revised["created_at"] = current.get("created_at")
    campaigns = list(state.get("campaigns") or [])
    campaigns[index] = revised
    updated = _rename_links({**state, "campaigns": campaigns}, current, revised)
    save(updated, path)
    return _view(updated, revised, [], datetime.now().date())


def attach_campaign(state: dict, campaign_id: str, spec: dict, path: Path | None = None) -> dict:
    if not isinstance(spec, dict):
        raise DraftError("Say which pieces or assets belong to the campaign.")
    _index, campaign = _campaign(state, campaign_id)
    piece_ids = [str(item) for item in spec.get("piece_ids") or [] if str(item).strip()]
    asset_ids = [str(item) for item in spec.get("asset_ids") or [] if str(item).strip()]
    if not piece_ids and not asset_ids:
        raise DraftError("Say which pieces or assets belong to the campaign.")
    pieces = list(state.get("pieces") or [])
    for piece_id in piece_ids:
        index, piece = _find(state, piece_id)
        if piece.get("brand_id") != campaign["brand_id"]:
            raise DraftError("That piece belongs to another brand.")
        pieces[index] = {**piece, "campaign": campaign["name"], "campaign_id": campaign["id"]}
    assets = list(state.get("assets") or [])
    for asset_id in asset_ids:
        found = next((i for i, asset in enumerate(assets) if asset.get("id") == asset_id), None)
        if found is None:
            raise DraftError("That asset is not in the library.")
        if assets[found].get("brand_id") != campaign["brand_id"]:
            raise DraftError("That asset belongs to another brand.")
        assets[found] = {**assets[found], "campaign_id": campaign["id"]}
    updated = {**state, "pieces": pieces, "assets": assets}
    save(updated, path)
    return _view(updated, campaign, [], datetime.now().date())


def _new(brand_id: str, spec: dict, state: dict, campaign_id: str = "") -> dict:
    if not isinstance(spec, dict):
        raise DraftError("The campaign needs a name.")
    name = _label(spec.get("name") or "", 48)
    if not name:
        raise DraftError("The campaign needs a name.")
    kind = str(spec.get("kind") or "").strip().lower()
    if kind not in KINDS:
        raise DraftError("Kind is launch, seasonal, or evergreen.")
    start = _day(spec.get("start") or "")
    end = _day(spec.get("end") or "")
    if start and end and end < start:
        raise DraftError("The end date is before the start.")
    others = [
        item for item in state.get("campaigns") or []
        if item.get("brand_id") == brand_id and item.get("id") != campaign_id and str(item.get("name") or "").lower() == name.lower()
    ]
    if others:
        raise DraftError("This brand already has that campaign.")
    return {
        "id": campaign_id or str(uuid.uuid4()),
        "brand_id": brand_id,
        "name": name,
        "kind": kind,
        "goal": _label(spec.get("goal") or "", 240),
        "goal_posts": _goal_posts(spec.get("goal_posts")),
        "start": start,
        "end": end,
        "note": _label(spec.get("note") or "", 240),
        "template": spec.get("template") is True,
        "created_at": datetime.now().isoformat(),
    }


def clone_campaign(state: dict, campaign_id: str, path: Path | None = None) -> dict:
    _index, current = _campaign(state, campaign_id)
    return save_campaign(
        state,
        current["brand_id"],
        {
            "name": _clone_name(current, state),
            "kind": current.get("kind") or "",
            "goal": current.get("goal") or "",
            "goal_posts": current.get("goal_posts") or "",
            "start": "",
            "end": "",
            "note": current.get("note") or "",
            "template": False,
        },
        path,
    )


def keep_retrospective(state: dict, campaign_id: str, posts: list[dict] | None, path: Path | None = None) -> dict:
    from ideas import save_idea
    from store import add_voice_post, load

    _index, campaign = _campaign(state, campaign_id)
    history = list(posts or [])
    view = _view(state, campaign, history, datetime.now().date(), kind_lessons(state, campaign["brand_id"], history))
    retro = view["retrospective"]
    if not retro["ready"]:
        raise DraftError(retro["detail"])
    if not retro["ahead"]:
        raise DraftError("Nothing in this retrospective is clear enough to keep.")
    piece_ids = {piece.get("id") for piece in view["pieces"]}
    measured = [post for post in history if str(post.get("piece_id") or "") in piece_ids and str(post.get("preview") or "").strip()]
    if not measured:
        raise DraftError("No post tied to this campaign has words to keep.")
    best = max(measured, key=lambda post: int(post.get("engagements") or 0))
    voiced = add_voice_post(
        state,
        campaign["brand_id"],
        {
            "text": str(best.get("preview") or ""),
            "kind": "on",
            "title": campaign["name"],
            "engagements": int(best.get("engagements") or 0),
        },
        path,
    )
    fresh = load(path) if path else load()
    saved = save_idea(
        fresh,
        campaign["brand_id"],
        {"text": retro["lesson"], "source": "spark", "note": f"Kept from the {campaign['name']} retrospective."},
        path,
    )
    return {"voice": voiced["voice"], "idea": saved}


def kind_lessons(state: dict, brand_id: str, posts: list[dict]) -> list[dict]:
    brand = resolve_brand(state, brand_id)
    campaigns = [item for item in state.get("campaigns") or [] if item.get("brand_id") == brand.id]
    pieces = [item for item in state.get("pieces") or [] if item.get("brand_id") == brand.id]
    grouped = {kind: [] for kind in KINDS}
    for post in posts:
        kind = _kind_of(post, pieces, campaigns)
        if kind in grouped:
            grouped[kind].append(post)
    present = [kind for kind, rows in grouped.items() if rows]
    if len(present) < 2:
        return [{
            "kind": "",
            "clear": False,
            "ahead": False,
            "detail": "Not enough posts are tied to campaign kinds to compare them.",
            "approach": "",
        }]
    found = []
    for kind in present:
        inside = grouped[kind]
        outside = [post for other, rows in grouped.items() if other != kind for post in rows]
        compared = _compare(kind, inside, outside)
        approach = f"A similar approach is another {kind} campaign." if compared["ahead"] else ""
        found.append({"kind": kind, **compared, "approach": approach})
    return found


def _view(state: dict, campaign: dict, posts: list[dict], today: date, lessons: list[dict] | None = None) -> dict:
    pieces = _linked_pieces(state, campaign)
    assets = [
        asset for asset in state.get("assets") or []
        if asset.get("brand_id") == campaign["brand_id"] and asset.get("campaign_id") == campaign["id"]
    ]
    piece_ids = {piece.get("id") for piece in pieces}
    measured = [post for post in posts if str(post.get("piece_id") or "") in piece_ids]
    save_values = [post.get("saves") for post in measured if post.get("saves") is not None]
    report = analytics(posts, [], state.get("pieces") or [], today=today, days=None)
    compared = next((item for item in report["campaigns"] if item.get("name") == campaign["name"]), None)
    return {
        "id": campaign["id"],
        "name": campaign["name"],
        "kind": campaign["kind"],
        "goal": campaign.get("goal") or "",
        "goal_posts": campaign.get("goal_posts"),
        "start": campaign.get("start") or "",
        "end": campaign.get("end") or "",
        "note": campaign.get("note") or "",
        "template": campaign.get("template") is True,
        "pieces": [
            {"id": piece.get("id"), "idea": str(piece.get("idea") or "")[:120], "status": piece.get("status") or "draft"}
            for piece in pieces
        ],
        "assets": [
            {"id": asset.get("id"), "name": asset.get("name") or "", "kind": asset.get("kind") or ""}
            for asset in assets
        ],
        "progress": {
            "posts": len(pieces),
            "goal_posts": campaign.get("goal_posts"),
            "making": sum(1 for piece in pieces if (piece.get("status") or "draft") in _MAKING),
            "out": sum(1 for piece in pieces if piece.get("status") in _OUT),
            "assets": len(assets),
            "phase": _phase(campaign, today),
        },
        "performance": {
            "posts": len(measured),
            "engagements": sum(int(post.get("engagements") or 0) for post in measured),
            "shares": sum(int(post.get("shares") or 0) for post in measured),
            "saves": sum(int(value) for value in save_values) if save_values else None,
            "clear": bool(compared and compared.get("clear")),
            "detail": (compared or {}).get("detail") or "No measured posts for this campaign yet.",
        },
        "retrospective": _retrospective(campaign, (compared or {}), today, lessons or [], campaign.get("kind") or ""),
    }


def _retrospective(campaign: dict, compared: dict, today: date, lessons: list[dict], kind: str) -> dict:
    detail = compared.get("detail") or "No measured posts for this campaign yet."
    if not campaign.get("end"):
        return {"ready": False, "ahead": False, "detail": "Set an end date before a retrospective.", "lesson": ""}
    if _phase(campaign, today) != "Closed":
        return {"ready": False, "ahead": False, "detail": "The retrospective waits until the end date has passed.", "lesson": ""}
    ahead = bool(compared.get("clear")) and "averaged less" not in detail and "too close" not in detail and "waits for" not in detail
    match = next((item for item in lessons if item.get("kind") == kind and item.get("ahead")), None)
    lesson = f"{detail} {match['approach']}" if ahead and match and match.get("approach") else detail
    return {"ready": True, "ahead": ahead, "detail": detail, "lesson": lesson}


def _compare(name: str, inside: list[dict], outside: list[dict]) -> dict:
    from learn import MIN_SAMPLE, _mean

    mean_in = _mean(inside)
    mean_out = _mean(outside)
    clear = (
        len(inside) >= MIN_SAMPLE
        and len(outside) >= MIN_SAMPLE
        and abs(mean_in - mean_out) >= 3
        and max(mean_in, mean_out) >= min(mean_in, mean_out) * 1.5
        and mean_in != mean_out
    )
    if len(inside) < MIN_SAMPLE or len(outside) < MIN_SAMPLE:
        return {
            "clear": False,
            "ahead": False,
            "detail": (
                f"{name} has {len(inside)} posts. "
                f"A comparison waits for {MIN_SAMPLE} of this kind and {MIN_SAMPLE} of the other kinds."
            ),
        }
    if not clear:
        return {
            "clear": False,
            "ahead": False,
            "detail": (
                f"{name} is too close to call. {mean_in:.1f} engagements (n={len(inside)}) "
                f"against {mean_out:.1f} on the other kinds (n={len(outside)})."
            ),
        }
    if mean_in > mean_out:
        return {
            "clear": True,
            "ahead": True,
            "detail": (
                f"{name} averaged {mean_in:.1f} engagements (n={len(inside)}). "
                f"The other kinds averaged {mean_out:.1f} (n={len(outside)})."
            ),
        }
    return {
        "clear": True,
        "ahead": False,
        "detail": (
            f"{name} averaged less: {mean_in:.1f} (n={len(inside)}) "
            f"against {mean_out:.1f} on the other kinds (n={len(outside)})."
        ),
    }


def _kind_of(post: dict, pieces: list[dict], campaigns: list[dict]) -> str:
    from learn import _campaign_name

    name = _campaign_name(post, pieces).lower()
    if not name:
        return ""
    found = next((item for item in campaigns if str(item.get("name") or "").lower() == name), None)
    return str((found or {}).get("kind") or "")


def _clone_name(campaign: dict, state: dict) -> str:
    base = str(campaign.get("name") or "").strip()
    taken = {
        str(item.get("name") or "").lower()
        for item in state.get("campaigns") or []
        if item.get("brand_id") == campaign.get("brand_id")
    }
    for number in range(1, 21):
        suffix = " copy" if number == 1 else f" copy {number}"
        stem = base[: 48 - len(suffix)].rstrip()
        candidate = f"{stem}{suffix}"
        if candidate.lower() not in taken:
            return candidate
    raise DraftError("That campaign has too many copies.")


def _linked_pieces(state: dict, campaign: dict) -> list[dict]:
    name = str(campaign.get("name") or "").lower()
    return [
        piece for piece in state.get("pieces") or []
        if piece.get("brand_id") == campaign.get("brand_id")
        and (
            piece.get("campaign_id") == campaign.get("id")
            or str(piece.get("campaign") or "").lower() == name
        )
    ]


def _claim_named_pieces(state: dict, campaign: dict) -> dict:
    pieces = []
    for piece in state.get("pieces") or []:
        if piece.get("brand_id") == campaign["brand_id"] and str(piece.get("campaign") or "").lower() == campaign["name"].lower():
            pieces.append({**piece, "campaign": campaign["name"], "campaign_id": campaign["id"]})
        else:
            pieces.append(piece)
    return {**state, "pieces": pieces}


def _rename_links(state: dict, previous: dict, campaign: dict) -> dict:
    pieces = []
    for piece in state.get("pieces") or []:
        linked = piece.get("campaign_id") == campaign["id"] or (
            piece.get("brand_id") == campaign["brand_id"]
            and str(piece.get("campaign") or "").lower() == str(previous.get("name") or "").lower()
        )
        if linked:
            pieces.append({**piece, "campaign": campaign["name"], "campaign_id": campaign["id"]})
        else:
            pieces.append(piece)
    return {**state, "pieces": pieces}


def _phase(campaign: dict, today: date) -> str:
    start = _as_date(campaign.get("start") or "")
    end = _as_date(campaign.get("end") or "")
    if start and today < start:
        return "Not started"
    if end and today > end:
        return "Closed"
    if start or end:
        return "In its dates"
    return "Open"


def _goal_posts(value) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 100:
        raise DraftError("The post goal is a whole number from 1 to 100.")
    return value


def _day(value) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise DraftError("Campaign dates are YYYY-MM-DD.") from exc


def _as_date(value: str) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _campaign(state: dict, campaign_id: str) -> tuple[int, dict]:
    for index, campaign in enumerate(state.get("campaigns") or []):
        if campaign.get("id") == campaign_id:
            return index, campaign
    raise DraftError("That campaign is not on this brand.")
