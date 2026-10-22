"""Queue and channel book for House Social.

State lives in ~/.hermes/plugin-data/house-social/state.json so a Hermes
update cannot take the drafts with the checkout. Nothing in this file
talks to Facebook, Instagram, or Threads.
"""

from __future__ import annotations

import copy
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from adapt import DraftError, issues, shape
from brands import FORMATS, PLATFORMS, SECTIONS, Brand, Channel, brand_dict, preferred_format, seed_brand


_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
STATUSES = ("draft", "planned", "ready", "pending", "approved", "scheduled", "failed")


def state_path() -> Path:
    override = os.environ.get("HOUSE_SOCIAL_STATE", "").strip()
    if override:
        return Path(override)
    return Path.home() / ".hermes" / "plugin-data" / "house-social" / "state.json"


def ledger_dir() -> Path:
    override = os.environ.get("HOUSE_SOCIAL_LEDGER", "").strip()
    if override:
        return Path(override)
    return state_path().parent / "ledger"


def empty_state() -> dict:
    return {
        "version": 1,
        "channels": {},
        "custom_brands": [],
        "pieces": [],
        "stats": [],
        "connections": [],
        "pulls": {},
        "voices": {},
        "assets": [],
        "campaigns": [],
        "ideas": [],
        "notices": [],
        "approval_steps": {},
    }


def load(path: Path | None = None) -> dict:
    target = path or state_path()
    if not target.exists():
        return empty_state()
    raw = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise DraftError("The house social queue is not a version 1 file.")
    channels = raw.get("channels")
    custom = raw.get("custom_brands")
    pieces = raw.get("pieces")
    stats = raw.get("stats")
    connections = raw.get("connections")
    pulls = raw.get("pulls")
    voices = raw.get("voices")
    assets = raw.get("assets")
    campaigns = raw.get("campaigns")
    ideas = raw.get("ideas")
    notices = raw.get("notices")
    approval_steps = raw.get("approval_steps")
    return {
        "version": 1,
        "channels": channels if isinstance(channels, dict) else {},
        "custom_brands": custom if isinstance(custom, list) else [],
        "pieces": pieces if isinstance(pieces, list) else [],
        "stats": stats if isinstance(stats, list) else [],
        "connections": connections if isinstance(connections, list) else [],
        "pulls": pulls if isinstance(pulls, dict) else {},
        "voices": voices if isinstance(voices, dict) else {},
        "assets": assets if isinstance(assets, list) else [],
        "campaigns": campaigns if isinstance(campaigns, list) else [],
        "ideas": ideas if isinstance(ideas, list) else [],
        "notices": notices if isinstance(notices, list) else [],
        "approval_steps": approval_steps if isinstance(approval_steps, dict) else {},
    }


def save(state: dict, path: Path | None = None) -> None:
    target = path or state_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(target)


def roster(state: dict) -> list[dict]:
    rows = [
        brand_dict(brand, _merged_channels(brand.id, brand.channels, state))
        for brand in _seeds()
    ]
    rows.extend(_custom_row(custom, state) for custom in state["custom_brands"])
    return rows


def create_piece(
    state: dict,
    brand_id: str,
    idea: str,
    path: Path | None = None,
    pillar: str = "",
    format_name: str = "",
    hypothesis: str = "",
    campaign: str = "",
    scheduled_for: str | None = None,
    status: str = "draft",
) -> dict:
    brand = resolve_brand(state, brand_id)
    status_name = (status or "draft").strip() or "draft"
    if status_name not in {"draft", "planned"}:
        raise DraftError("A new piece starts as a draft or a plan.")
    piece = {
        "id": str(uuid.uuid4()),
        "brand_id": brand.id,
        "idea": idea.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status_name,
        "scheduled_for": _parse_when(scheduled_for) if scheduled_for else None,
        "posted": False,
        "pillar": _label(pillar, 40),
        "format": _format_name(brand.id, format_name),
        "hypothesis": _label(hypothesis, 240),
        "campaign": _label(campaign, 48),
        "variants": shape(brand, idea),
    }
    updated = _copy(state)
    updated["pieces"] = [piece, *updated["pieces"]]
    save(updated, path)
    return piece


def update_piece(
    state: dict,
    piece_id: str,
    *,
    variants: dict | None = None,
    status: str | None = None,
    scheduled_for: str | None = None,
    clear_schedule: bool = False,
    pillar: str | None = None,
    format_name: str | None = None,
    hypothesis: str | None = None,
    campaign: str | None = None,
    failure: str | None = None,
    path: Path | None = None,
) -> dict:
    updated = _copy(state)
    index, piece = _find(updated, piece_id)
    brand = resolve_brand(updated, piece["brand_id"])
    next_piece = copy.deepcopy(piece)
    if variants:
        next_piece["variants"] = _merge_variants(next_piece["variants"], variants)
    if clear_schedule:
        next_piece["scheduled_for"] = None
        if next_piece.get("status") == "scheduled":
            problems = issues(brand, next_piece["variants"])
            next_piece["status"] = "draft" if problems else "ready"
    elif scheduled_for is not None:
        next_piece["scheduled_for"] = _parse_when(scheduled_for, previous=str(piece.get("scheduled_for") or ""))
    if pillar is not None:
        next_piece["pillar"] = _label(pillar, 40)
    if format_name is not None:
        next_piece["format"] = _format_name(piece["brand_id"], format_name)
    if hypothesis is not None:
        next_piece["hypothesis"] = _label(hypothesis, 240)
    if campaign is not None:
        next_piece["campaign"] = _label(campaign, 48)
        match = next(
            (
                item for item in updated.get("campaigns") or []
                if item.get("brand_id") == brand.id and str(item.get("name") or "").lower() == next_piece["campaign"].lower()
            ),
            None,
        )
        next_piece["campaign_id"] = match["id"] if match and next_piece["campaign"] else ""
    if status is not None:
        if status not in STATUSES:
            raise DraftError("Status must be draft, planned, ready, pending, approved, scheduled, or failed.")
        if status in {"ready", "pending", "approved", "scheduled"}:
            problems = issues(brand, next_piece["variants"])
            if problems:
                raise DraftError(" ".join(problems))
        if status == "scheduled" and not (next_piece.get("approval") or {}).get("complete"):
            raise DraftError("Schedule waits until the piece is approved.")
        if status == "scheduled" and not next_piece.get("scheduled_for"):
            raise DraftError("A scheduled piece needs a time.")
        next_piece["status"] = status
        next_piece["failure"] = _label(failure or "It did not pass the schedule rules.", 300) if status == "failed" else ""
    next_piece["posted"] = False
    updated["pieces"][index] = next_piece
    save(updated, path)
    return next_piece


def delete_piece(state: dict, piece_id: str, path: Path | None = None) -> None:
    updated = _copy(state)
    updated["pieces"] = [piece for piece in updated["pieces"] if piece.get("id") != piece_id]
    if len(updated["pieces"]) == len(state["pieces"]):
        raise DraftError("That piece is not in the queue.")
    save(updated, path)


def set_channels(state: dict, brand_id: str, updates: dict, path: Path | None = None) -> list[dict]:
    updated = _copy(state)
    brand = resolve_brand(state, brand_id)
    seeds = {channel.platform: channel for channel in brand.channels}
    current = dict(updated["channels"].get(brand_id, {}))
    for platform, payload in updates.items():
        if platform not in PLATFORMS or not isinstance(payload, dict):
            raise DraftError("Channels are facebook, instagram, and threads.")
        previous = current.get(platform, {})
        handle = str(payload.get("handle", "")).strip().lstrip("@")
        external_id = str(payload.get("external_id", "")).strip()
        if not external_id:
            external_id = str(previous.get("external_id") or getattr(seeds.get(platform), "external_id", "") or "")
        if len(handle) > 80 or len(external_id) > 40:
            raise DraftError("That handle is too long.")
        current[platform] = {
            "handle": handle,
            "external_id": external_id,
            "known": bool(handle or external_id),
        }
    updated["channels"][brand_id] = current
    save(updated, path)
    return _channels_for(updated, brand_id)


def add_brand(state: dict, spec: dict, path: Path | None = None) -> dict:
    brand_id = str(spec.get("id", "")).strip()
    name = str(spec.get("name", "")).strip()
    if not _ID.fullmatch(brand_id) or len(brand_id) > 40:
        raise DraftError("Brand id is lowercase words separated by hyphens.")
    if not name or len(name) > 80:
        raise DraftError("The brand needs a name.")
    if seed_brand(brand_id) or any(item.get("id") == brand_id for item in state["custom_brands"]):
        raise DraftError("That brand is already on the roster.")
    tags = []
    for tag in spec.get("tags") or []:
        clean = str(tag).strip().lstrip("#")
        if clean and clean.lower() not in {item.lower() for item in tags}:
            tags.append(clean)
    custom = {
        "id": brand_id,
        "name": name,
        "site": str(spec.get("site", "")).strip(),
        "voice": str(spec.get("voice", "")).strip(),
        "tags": tags[:5],
        "guards": [],
    }
    updated = _copy(state)
    updated["custom_brands"] = [*updated["custom_brands"], custom]
    save(updated, path)
    return custom


def record_stat(state: dict, spec: dict, path: Path | None = None) -> dict:
    brand = resolve_brand(state, str(spec.get("brand_id", "")))
    platform = str(spec.get("platform", "")).strip()
    if platform not in PLATFORMS:
        raise DraftError("Channels are facebook, instagram, and threads.")
    payload = spec.get("metrics") if isinstance(spec.get("metrics"), dict) else spec
    metrics = _metrics(payload)
    if not metrics:
        raise DraftError("Record at least one number.")
    hour = spec.get("local_hour")
    if hour is not None and hour != "":
        if isinstance(hour, bool) or not isinstance(hour, int) or not 0 <= hour <= 23:
            raise DraftError("local_hour is 0 through 23.")
    else:
        hour = None
    piece_id = str(spec.get("piece_id") or "")
    if piece_id and not any(piece.get("id") == piece_id for piece in state["pieces"]):
        raise DraftError("That piece is not in the queue.")
    stat = {
        "id": str(uuid.uuid4()),
        "brand_id": brand.id,
        "platform": platform,
        "piece_id": piece_id,
        "format": _format_name(brand.id, str(spec.get("format") or "unknown")),
        "pillar": _label(spec.get("pillar") or "", 40),
        "external_id": _label(spec.get("external_id") or "", 80),
        "published_at": _parse_when(spec["published_at"]) if spec.get("published_at") else None,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "local_hour": hour,
        "metrics": metrics,
        "note": _label(spec.get("note") or "", 240),
        "preview": _label(spec.get("preview") or spec.get("note") or "", 140),
        "permalink": _label(spec.get("permalink") or "", 300),
    }
    updated = _copy(state)
    updated["stats"] = [stat, *updated.get("stats", [])]
    save(updated, path)
    return stat


def brand_history(state: dict, brand_id: str, ledger: dict | None = None) -> tuple[list[dict], list[dict]]:
    from learn import combine_posts, manual_posts

    pulled = (state.get("pulls") or {}).get(brand_id) or {}
    pulled_posts = list(pulled.get("posts") or [])
    if pulled_posts:
        ledger_posts: list[dict] = pulled_posts
        page_days: list[dict] = []
    else:
        if brand_id != "josie-blackthorn":
            ledger = {"posts": [], "days": []}
        ledger = ledger or {"posts": [], "days": []}
        ledger_posts = list(ledger.get("posts") or [])
        page_days = list(ledger.get("days") or [])
    recorded = manual_posts([stat for stat in state.get("stats", []) if stat.get("brand_id") == brand_id])
    return combine_posts(ledger_posts, recorded), page_days


def studio(state: dict, brand_id: str, ledger: dict | None = None, today=None) -> dict:
    from learn import lessons, manual_posts, next_step, performance

    resolve_brand(state, brand_id)
    posts, page_days = brand_history(state, brand_id, ledger)
    recorded = manual_posts([stat for stat in state.get("stats", []) if stat.get("brand_id") == brand_id])
    found = lessons(posts, page_days, recorded)
    pieces = [piece for piece in state["pieces"] if piece.get("brand_id") == brand_id]
    unscheduled = [piece for piece in pieces if not piece.get("scheduled_for")]
    open_experiments = [
        {
            "id": piece["id"],
            "idea": str(piece.get("idea") or "")[:120],
            "hypothesis": piece.get("hypothesis") or "",
        }
        for piece in pieces
        if piece.get("hypothesis") and not any(stat.get("piece_id") == piece["id"] for stat in state.get("stats", []))
    ]
    if open_experiments:
        found.append(
            {
                "id": "experiments",
                "title": "Open experiments",
                "detail": f"{len(open_experiments)} pieces have a hypothesis and no result yet.",
                "clear": False,
            }
        )
    found.append(next_step(found, len(unscheduled)))
    when = today or datetime.now(ZoneInfo("America/New_York")).date()
    row = next(item for item in roster(state) if item["id"] == brand_id)
    return {
        "posting": False,
        "brand": row,
        "calendar": _calendar(pieces, posts, when),
        "performance": performance(posts, page_days, pieces, when),
        "feed": sorted(posts, key=lambda post: str(post.get("published_at") or ""), reverse=True)[:50],
        "lessons": found,
        "experiments": open_experiments,
        "connections": [_public_connection(item) for item in state.get("connections", []) if item.get("brand_id") == brand_id],
        "pull": {
            "pulled_at": ((state.get("pulls") or {}).get(brand_id) or {}).get("pulled_at"),
            "count": len(((state.get("pulls") or {}).get(brand_id) or {}).get("posts") or []),
            "errors": list(((state.get("pulls") or {}).get(brand_id) or {}).get("errors") or []),
        },
        "voice": _voice_view(state, brand_id),
        "queue": _queue_view(state, brand_id, posts),
        "campaigns": _campaigns_view(state, brand_id, posts, when),
        "ideas": _ideas_view(state, brand_id),
        "approval": _approval_view(state, brand_id),
    }


def save_connection(state: dict, spec: dict, path: Path | None = None, vault_write=None) -> dict:
    brand = resolve_brand(state, str(spec.get("brand_id", "")))
    platform = str(spec.get("platform", "")).strip()
    if platform not in PLATFORMS:
        raise DraftError("Channels are facebook, instagram, and threads.")
    external_id = _label(spec.get("external_id") or "", 64)
    app_id = _label(spec.get("app_id") or "", 32)
    if not external_id or not app_id:
        raise DraftError("A connection needs the Meta app id and the page or account id.")
    token = str(spec.get("token") or "").strip()
    vault_name = f"house-social.{brand.id}.{platform}.token"
    existing = next(
        (
            item for item in state.get("connections", [])
            if item.get("brand_id") == brand.id and item.get("platform") == platform
        ),
        None,
    )
    if token:
        writer = vault_write or _write_vault
        if not writer(vault_name, token):
            raise DraftError("The token did not reach the vault. Nothing was saved.")
        vault_ref = f"vault:{vault_name}"
    elif existing and existing.get("token_vault"):
        vault_ref = existing["token_vault"]
    else:
        raise DraftError("Paste the page token once. It is stored in the vault, not in the dashboard.")
    connection = {
        "id": f"{brand.id}:{platform}",
        "brand_id": brand.id,
        "platform": platform,
        "external_id": external_id,
        "app_id": app_id,
        "token_vault": vault_ref,
    }
    updated = _copy(state)
    others = [
        item for item in updated.get("connections", [])
        if not (item.get("brand_id") == brand.id and item.get("platform") == platform)
    ]
    updated["connections"] = [*others, connection]
    save(updated, path)
    return _public_connection(connection)


def pull_brand(
    state: dict,
    brand_id: str,
    path: Path | None = None,
    reader=None,
    fetcher=None,
    discover=None,
) -> dict:
    from meta import MetaError, lookup_instagram, pull_platform

    resolve_brand(state, brand_id)
    mine = [item for item in state.get("connections", []) if item.get("brand_id") == brand_id]
    if not mine:
        raise DraftError("Add a Meta app for this brand first.")
    read = reader or _read_vault
    fetch = fetcher or pull_platform
    find_instagram = lookup_instagram if discover is None else discover
    posts: list[dict] = []
    errors: list[str] = []
    discovered: list[dict] = []
    seen: set[tuple[str, str]] = set()
    ordered = sorted(mine, key=lambda item: 0 if item.get("platform") == "facebook" else 1)
    for connection in ordered:
        if connection.get("platform") == "instagram" and connection.get("via") == "facebook":
            continue
        vault_name = str(connection.get("token_vault") or "").removeprefix("vault:")
        token = read(vault_name)
        if not token:
            errors.append(f"{connection['platform']}: no token in vault:{vault_name}")
            continue
        _pull_one(fetch, posts, seen, errors, connection["platform"], connection["external_id"], token)
        if connection.get("platform") != "facebook":
            continue
        try:
            instagram = find_instagram(connection["external_id"], token)
        except MetaError as exc:
            errors.append(f"instagram: {exc}")
            continue
        if not instagram:
            errors.append("instagram: this Page has no linked Instagram account.")
            continue
        _pull_one(fetch, posts, seen, errors, "instagram", instagram["id"], token)
        discovered.append(
            {
                "id": f"{brand_id}:instagram",
                "brand_id": brand_id,
                "platform": "instagram",
                "external_id": instagram["id"],
                "username": instagram.get("username") or "",
                "app_id": connection.get("app_id") or "",
                "token_vault": connection.get("token_vault"),
                "via": "facebook",
            }
        )
    updated = _copy(state)
    if discovered:
        others = [
            item for item in updated.get("connections", [])
            if not (item.get("brand_id") == brand_id and item.get("platform") == "instagram")
        ]
        updated["connections"] = [*others, *discovered]
    previous = dict((updated.get("pulls") or {}).get(brand_id) or {})
    kept = posts if posts else list(previous.get("posts") or [])
    updated.setdefault("pulls", {})
    updated["pulls"][brand_id] = {
        "pulled_at": datetime.now(timezone.utc).isoformat(),
        "posts": kept,
        "errors": errors,
    }
    save(updated, path)
    return {"count": len(kept), "errors": errors, "pulled_at": updated["pulls"][brand_id]["pulled_at"]}


def _pull_one(fetch, posts: list[dict], seen: set[tuple[str, str]], errors: list[str], platform: str, external_id: str, token: str) -> None:
    from meta import MetaError

    key = (platform, external_id)
    if key in seen:
        return
    seen.add(key)
    try:
        posts.extend(fetch(platform, external_id, token))
    except MetaError as exc:
        errors.append(f"{platform}: {exc}")


def _public_connection(connection: dict) -> dict:
    stored = json.dumps(connection)
    if "token" in connection and connection.get("token"):
        raise DraftError("A connection must not keep a token.")
    if "access_token" in stored:
        raise DraftError("A connection must not keep a token.")
    return {
        "id": connection.get("id"),
        "brand_id": connection.get("brand_id"),
        "platform": connection.get("platform"),
        "external_id": connection.get("external_id"),
        "app_id": connection.get("app_id"),
        "token_vault": connection.get("token_vault"),
        "username": connection.get("username") or "",
        "via": connection.get("via") or "",
        "connected": bool(connection.get("token_vault")),
    }


def _write_vault(name: str, value: str) -> bool:
    import shutil
    import subprocess

    binary = shutil.which("vault") or ""
    home = Path.home() / "bin" / "vault"
    if not binary and home.is_file():
        binary = str(home)
    if not binary:
        return False
    try:
        result = subprocess.run(
            [binary, "set", "-name", name, "-type", "token", "-secret", value],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _read_vault(name: str) -> str | None:
    import shutil
    import subprocess

    binary = shutil.which("vault-secret") or ""
    home = Path.home() / "bin" / "vault-secret"
    if not binary and home.is_file():
        binary = str(home)
    if not binary:
        return None
    try:
        result = subprocess.run([binary, name], capture_output=True, text=True, timeout=8, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    value = (result.stdout or "").strip()
    return value or None


def save_voice(state: dict, brand_id: str, spec: dict, path: Path | None = None) -> dict:
    from voice import guide_for

    resolve_brand(state, brand_id)
    if not isinstance(spec, dict):
        raise DraftError("The voice guide needs fields.")
    guide = guide_for(brand_id, spec)
    for key in ("tone", "personality", "visual"):
        if len(guide[key]) > 600:
            raise DraftError("That voice field is too long.")
    updated = _copy(state)
    updated.setdefault("voices", {})
    updated["voices"][brand_id] = guide
    save(updated, path)
    return guide


def voice_check_brand(state: dict, brand_id: str, fields: dict) -> dict:
    from voice import guide_for, voice_report

    resolve_brand(state, brand_id)
    guide = guide_for(brand_id, (state.get("voices") or {}).get(brand_id))
    return voice_report(guide, fields)


def _voice_view(state: dict, brand_id: str) -> dict:
    from voice import guide_for

    return guide_for(brand_id, (state.get("voices") or {}).get(brand_id))


def _queue_view(state: dict, brand_id: str, posts: list[dict]) -> dict:
    from queue_desk import queue_for

    return queue_for(state, brand_id, posts)


def _campaigns_view(state: dict, brand_id: str, posts: list[dict], today) -> dict:
    from campaigns import campaigns_for

    return campaigns_for(state, brand_id, posts, today)


def _ideas_view(state: dict, brand_id: str) -> dict:
    from ideas import ideas_for

    return ideas_for(state, brand_id)


def _approval_view(state: dict, brand_id: str) -> dict:
    from approval import approval_for

    return approval_for(state, brand_id)


def resolve_brand(state: dict, brand_id: str) -> Brand:
    seed = seed_brand(brand_id)
    if seed is not None:
        return seed
    for custom in state["custom_brands"]:
        if custom.get("id") == brand_id:
            return Brand(
                id=custom["id"],
                name=custom["name"],
                site=custom.get("site", ""),
                voice=custom.get("voice", ""),
                tags=tuple(custom.get("tags") or ()),
                channels=tuple(Channel(platform) for platform in PLATFORMS),
                guards=tuple(custom.get("guards") or ()),
            )
    raise DraftError(f"Unknown brand: {brand_id}")


def _label(value: object, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) > limit:
        raise DraftError("That field is too long.")
    return text


def _format_name(brand_id: str, format_name: str) -> str:
    name = (format_name or preferred_format(brand_id)).strip() or "feed"
    if name == "unknown":
        return name
    if name not in FORMATS:
        raise DraftError("Unknown format.")
    return name


def _metrics(payload: dict) -> dict:
    keys = ("impressions", "engagements", "likes", "comments", "shares", "saves", "follows", "clicks")
    metrics = {}
    for key in keys:
        if key not in payload or payload[key] in ("", None):
            continue
        value = payload[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise DraftError("Metrics are whole numbers, zero or more.")
        metrics[key] = value
    return metrics


def _calendar(pieces: list[dict], posts: list[dict], today) -> dict:
    entries = calendar_entries(pieces, posts)
    days = []
    for offset in range(7):
        day = today + timedelta(days=offset)
        key = day.isoformat()
        items = [item for item in entries if item.get("date") == key]
        days.append({"date": key, "label": f"{day.strftime('%a')} {day.day}", "pieces": items})
    unscheduled = [item for item in entries if item.get("kind") == "piece" and not item.get("date")]
    return {"days": days, "unscheduled": unscheduled, "entries": entries}


def calendar_entries(pieces: list[dict], posts: list[dict]) -> list[dict]:
    rows = [_piece_entry(piece) for piece in pieces]
    for post in posts:
        entry = _published_entry(post)
        if entry:
            rows.append(entry)
    return rows


def calendar_span(entries: list[dict], dates: list[str]) -> dict:
    wanted = set(dates)
    lanes = {"planned": 0, "drafted": 0, "scheduled": 0, "published": 0}
    occupied = set()
    for item in entries:
        day = item.get("date") or ""
        if day not in wanted:
            continue
        occupied.add(day)
        lane = item.get("lane") or "drafted"
        if lane in lanes:
            lanes[lane] += 1
    return {"lanes": lanes, "open_days": sum(1 for day in dates if day not in occupied)}


def _piece_entry(piece: dict) -> dict:
    day, clock = _local_date_time(str(piece.get("scheduled_for") or ""))
    variants = piece.get("variants") or {}
    platforms = [
        platform for platform in PLATFORMS
        if str((variants.get(platform) or {}).get("body") or "").strip()
    ]
    status = piece.get("status") or "draft"
    return {
        "id": piece.get("id"),
        "kind": "piece",
        "status": status,
        "lane": _lane(status),
        "date": day,
        "time": clock,
        "title": str(piece.get("idea") or "")[:80],
        "pillar": piece.get("pillar") or "",
        "format": piece.get("format") or "",
        "campaign": piece.get("campaign") or "",
        "platforms": platforms,
        "draggable": True,
        "permalink": "",
    }


def _published_entry(post: dict) -> dict | None:
    day, clock = _local_date_time(str(post.get("published_at") or ""))
    if not day:
        return None
    platform = post.get("platform") or ("facebook" if post.get("source") == "ledger" else "")
    return {
        "id": f"live:{platform}:{post.get('id')}",
        "kind": "published",
        "status": "published",
        "lane": "published",
        "date": day,
        "time": clock,
        "title": str(post.get("preview") or "")[:80],
        "pillar": "",
        "format": post.get("format") or "",
        "campaign": "",
        "platforms": [platform] if platform in PLATFORMS else [],
        "draggable": False,
        "permalink": str(post.get("permalink") or ""),
    }


def _lane(status: str) -> str:
    if status == "planned":
        return "planned"
    if status == "scheduled":
        return "scheduled"
    if status == "published":
        return "published"
    return "drafted"


def _seeds():
    from brands import BRANDS

    return BRANDS


def _copy(state: dict) -> dict:
    return copy.deepcopy(state)


def _find(state: dict, piece_id: str) -> tuple[int, dict]:
    for index, piece in enumerate(state["pieces"]):
        if piece.get("id") == piece_id:
            return index, piece
    raise DraftError("That piece is not in the queue.")


def _merge_variants(current: dict, updates: dict) -> dict:
    merged = copy.deepcopy(current)
    for platform, payload in updates.items():
        if platform not in PLATFORMS or not isinstance(payload, dict):
            raise DraftError("Channels are facebook, instagram, and threads.")
        variant = dict(merged.get(platform) or {})
        if "body" in payload:
            body = str(payload["body"])
            if len(body) > 8000:
                raise DraftError("That draft is too long.")
            variant["body"] = body
        if "hashtags" in payload:
            if not isinstance(payload["hashtags"], list):
                raise DraftError("Hashtags are a list.")
            variant["hashtags"] = [str(tag).strip().lstrip("#") for tag in payload["hashtags"] if str(tag).strip()][:5]
        if "image_ready" in payload:
            variant["image_ready"] = bool(payload["image_ready"])
        if "first_comment" in payload:
            comment = str(payload["first_comment"])
            if len(comment) > 1000:
                raise DraftError("That first comment is too long.")
            variant["first_comment"] = comment
        merged[platform] = variant
    return merged


def _parse_when(value: str, previous: str = "") -> str:
    text = str(value).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        year, month, day = (int(part) for part in text.split("-"))
        hour, minute = 12, 0
        _, clock = _local_date_time(previous)
        if clock:
            hour, minute = (int(part) for part in clock.split(":"))
        local = datetime(year, month, day, hour, minute, tzinfo=ZoneInfo("America/New_York"))
        return local.isoformat()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise DraftError("scheduled_for must be an ISO-8601 time.") from exc
    if parsed.tzinfo is None:
        raise DraftError("scheduled_for needs a timezone.")
    return parsed.isoformat()


def _local_date_time(value: str) -> tuple[str, str]:
    text = str(value or "").strip()
    if not text:
        return "", ""
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return "", ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    local = parsed.astimezone(ZoneInfo("America/New_York"))
    return local.date().isoformat(), local.strftime("%H:%M")


def _merged_channels(brand_id: str, seeds: tuple[Channel, ...], state: dict) -> list[dict]:
    overrides = state["channels"].get(brand_id, {})
    rows = []
    for seed in seeds:
        over = overrides.get(seed.platform)
        if isinstance(over, dict) and ("handle" in over or "external_id" in over):
            handle = str(over.get("handle", "")).strip()
            external_id = str(over.get("external_id", "")).strip()
            known = bool(handle or external_id)
        else:
            handle, external_id, known = seed.handle, seed.external_id, seed.known
        rows.append(
            {
                "platform": seed.platform,
                "handle": handle,
                "external_id": external_id,
                "known": known,
                "posting": False,
            }
        )
    return rows


def _custom_row(custom: dict, state: dict) -> dict:
    channels = _merged_channels(
        custom["id"],
        tuple(Channel(platform) for platform in PLATFORMS),
        state,
    )
    return {
        "id": custom["id"],
        "name": custom["name"],
        "site": custom.get("site", ""),
        "voice": custom.get("voice", ""),
        "tags": list(custom.get("tags") or []),
        "guards": list(custom.get("guards") or []),
        "channels": channels,
        "custom": True,
        "audience": "",
        "pillars": [],
        "preferred_format": "feed",
        "sections": [dict(section) for section in SECTIONS],
    }


def _channels_for(state: dict, brand_id: str) -> list[dict]:
    for row in roster(state):
        if row["id"] == brand_id:
            return row["channels"]
    return []
