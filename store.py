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
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from adapt import DraftError, issues, shape
from brands import FORMATS, PLATFORMS, SECTIONS, Brand, Channel, brand_dict, brand_removable, preferred_format, seed_brand


_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
STATUSES = ("draft", "planned", "ready", "pending", "approved", "scheduled", "failed", "published")


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
        "hidden_brands": [],
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
        "hashtag_sets": [],
        "trends": [],
        "inbox": [],
        "inbox_errors": {},
        "reports": [],
        "voice_versions": {},
        "voice_imports": [],
        "history": [],
        "goals": [],
        "recurrences": [],
        "studio_reads": {},
        "ingest_log": [],
        "ingest_maps": {},
        "memory_marks": {},
        "memory_log": [],
        "predictions": [],
        "prediction_hidden": {},
        "series": [],
        "feedback": [],
        "sites": {},
        "cross_enabled": {},
        "cross_accepted": [],
        "modes": {},
        "mode_batches": [],
        "mode_log": [],
        "mode_limits": {},
        "mail_prefs": {},
        "mix_targets": {},
        "pauses": {},
        "adapt_rules": {},
        "previews": [],
        "series_paused": {},
        "todo_notes": {},
        "todo_notes_log": [],
        "todo_held": [],
        "apps": {},
        "oauth_pending": [],
        "publishing": {"on": False, "brands": {}},
        "test_posts": [],
        "mail": {},
        "approval_emails": {},
        "boost_minimums": {},
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
    hidden = raw.get("hidden_brands")
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
    hashtag_sets = raw.get("hashtag_sets")
    trends = raw.get("trends")
    inbox = raw.get("inbox")
    inbox_errors = raw.get("inbox_errors")
    reports = raw.get("reports")
    voice_versions = raw.get("voice_versions")
    voice_imports = raw.get("voice_imports")
    history = raw.get("history")
    goals = raw.get("goals")
    recurrences = raw.get("recurrences")
    studio_reads = raw.get("studio_reads")
    ingest_log = raw.get("ingest_log")
    ingest_maps = raw.get("ingest_maps")
    memory_marks = raw.get("memory_marks")
    memory_log = raw.get("memory_log")
    predictions = raw.get("predictions")
    prediction_hidden = raw.get("prediction_hidden")
    series = raw.get("series")
    feedback = raw.get("feedback")
    sites = raw.get("sites")
    cross_enabled = raw.get("cross_enabled")
    cross_accepted = raw.get("cross_accepted")
    modes = raw.get("modes")
    mode_batches = raw.get("mode_batches")
    mode_log = raw.get("mode_log")
    mode_limits = raw.get("mode_limits")
    mail_prefs = raw.get("mail_prefs")
    mix_targets = raw.get("mix_targets")
    pauses = raw.get("pauses")
    adapt_rules = raw.get("adapt_rules")
    previews = raw.get("previews")
    series_paused = raw.get("series_paused")
    todo_notes = raw.get("todo_notes")
    todo_notes_log = raw.get("todo_notes_log")
    todo_held = raw.get("todo_held")
    apps = raw.get("apps")
    oauth_pending = raw.get("oauth_pending")
    publishing = raw.get("publishing")
    test_posts = raw.get("test_posts")
    mail = raw.get("mail")
    approval_emails = raw.get("approval_emails")
    boost_minimums = raw.get("boost_minimums")
    return {
        "version": 1,
        "channels": channels if isinstance(channels, dict) else {},
        "custom_brands": custom if isinstance(custom, list) else [],
        "hidden_brands": [str(item) for item in hidden if str(item).strip()] if isinstance(hidden, list) else [],
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
        "hashtag_sets": hashtag_sets if isinstance(hashtag_sets, list) else [],
        "trends": trends if isinstance(trends, list) else [],
        "inbox": inbox if isinstance(inbox, list) else [],
        "inbox_errors": inbox_errors if isinstance(inbox_errors, dict) else {},
        "reports": reports if isinstance(reports, list) else [],
        "voice_versions": voice_versions if isinstance(voice_versions, dict) else {},
        "voice_imports": voice_imports if isinstance(voice_imports, list) else [],
        "history": history if isinstance(history, list) else [],
        "goals": goals if isinstance(goals, list) else [],
        "recurrences": recurrences if isinstance(recurrences, list) else [],
        "studio_reads": studio_reads if isinstance(studio_reads, dict) else {},
        "ingest_log": ingest_log if isinstance(ingest_log, list) else [],
        "ingest_maps": ingest_maps if isinstance(ingest_maps, dict) else {},
        "memory_marks": memory_marks if isinstance(memory_marks, dict) else {},
        "memory_log": memory_log if isinstance(memory_log, list) else [],
        "predictions": predictions if isinstance(predictions, list) else [],
        "prediction_hidden": prediction_hidden if isinstance(prediction_hidden, dict) else {},
        "series": series if isinstance(series, list) else [],
        "feedback": feedback if isinstance(feedback, list) else [],
        "sites": sites if isinstance(sites, dict) else {},
        "cross_enabled": cross_enabled if isinstance(cross_enabled, dict) else {},
        "cross_accepted": cross_accepted if isinstance(cross_accepted, list) else [],
        "modes": modes if isinstance(modes, dict) else {},
        "mode_batches": mode_batches if isinstance(mode_batches, list) else [],
        "mode_log": mode_log if isinstance(mode_log, list) else [],
        "mode_limits": mode_limits if isinstance(mode_limits, dict) else {},
        "mail_prefs": mail_prefs if isinstance(mail_prefs, dict) else {},
        "mix_targets": mix_targets if isinstance(mix_targets, dict) else {},
        "pauses": pauses if isinstance(pauses, dict) else {},
        "adapt_rules": adapt_rules if isinstance(adapt_rules, dict) else {},
        "previews": previews if isinstance(previews, list) else [],
        "series_paused": series_paused if isinstance(series_paused, dict) else {},
        "todo_notes": todo_notes if isinstance(todo_notes, dict) else {},
        "todo_notes_log": todo_notes_log if isinstance(todo_notes_log, list) else [],
        "todo_held": todo_held if isinstance(todo_held, list) else [],
        "apps": apps if isinstance(apps, dict) else {},
        "oauth_pending": oauth_pending if isinstance(oauth_pending, list) else [],
        "publishing": publishing if isinstance(publishing, dict) else {"on": False, "brands": {}},
        "test_posts": test_posts if isinstance(test_posts, list) else [],
        "mail": mail if isinstance(mail, dict) else {},
        "approval_emails": approval_emails if isinstance(approval_emails, dict) else {},
        "boost_minimums": boost_minimums if isinstance(boost_minimums, dict) else {},
    }


def save(state: dict, path: Path | None = None) -> None:
    target = path or state_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(target)


def roster(state: dict) -> list[dict]:
    hidden = set(state.get("hidden_brands") or [])
    rows = [
        _with_site(state, brand_dict(brand, _merged_channels(brand.id, brand.channels, state)))
        for brand in _seeds()
        if brand.id not in hidden
    ]
    rows.extend(_with_site(state, _custom_row(custom, state)) for custom in state["custom_brands"])
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
    if piece.get("status") == "published" and (status is not None or scheduled_for is not None or clear_schedule):
        raise DraftError("This piece already posted. Start a new draft to post it again.")
    if variants:
        next_piece["variants"] = _merge_variants(next_piece["variants"], variants)
        # Words someone wrote replace the desk's placeholder.
        next_piece.pop("placeholder", None)
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
        if status == "published":
            raise DraftError("A piece is marked posted only when it posts.")
        if status == "scheduled" and not (next_piece.get("approval") or {}).get("complete"):
            raise DraftError("Schedule waits until the piece is approved.")
        if status == "scheduled" and not next_piece.get("scheduled_for"):
            raise DraftError("A scheduled piece needs a time.")
        next_piece["status"] = status
        next_piece["failure"] = _label(failure or "It did not pass the schedule rules.", 300) if status == "failed" else ""
    next_piece["posted"] = bool(next_piece.get("published"))
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
    if seed_brand(brand_id) and brand_id in set(state.get("hidden_brands") or []):
        updated = _copy(state)
        updated["hidden_brands"] = [item for item in updated.get("hidden_brands") or [] if item != brand_id]
        save(updated, path)
        seed = seed_brand(brand_id)
        return {"id": seed.id, "name": seed.name}
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


def set_site(state: dict, brand_id: str, site: str, path: Path | None = None) -> dict:
    brand = resolve_brand(state, brand_id)
    clean = _site_url(site)
    updated = _copy(state)
    custom = next((item for item in updated.get("custom_brands") or [] if item.get("id") == brand.id), None)
    sites = dict(updated.get("sites") or {})
    if custom is not None:
        custom["site"] = clean
        sites.pop(brand.id, None)
    elif clean:
        sites[brand.id] = clean
    else:
        sites.pop(brand.id, None)
    updated["sites"] = sites
    save(updated, path)
    shown = sites.get(brand.id, custom.get("site") if custom is not None else brand.site)
    return {"id": brand.id, "site": shown}


def _site_url(site: str) -> str:
    text = str(site or "").strip()
    if not text:
        return ""
    if len(text) > 200 or any(char.isspace() for char in text):
        raise DraftError("The site needs to start with https://.")
    if not text.startswith(("https://", "http://")) or text in {"https://", "http://"}:
        raise DraftError("The site needs to start with https://.")
    return text


def _with_site(state: dict, row: dict) -> dict:
    sites = state.get("sites") or {}
    if row.get("id") in sites:
        row = {**row, "site": str(sites[row["id"]] or "")}
    return {**row, "cross_enabled": bool((state.get("cross_enabled") or {}).get(row.get("id")))}


def remove_brand(state: dict, brand_id: str, path: Path | None = None, root: Path | None = None) -> dict:
    name = str(brand_id or "").strip()
    if not brand_removable(name):
        raise DraftError("Josie and Misfit stay on the roster.")
    seed = seed_brand(name)
    is_custom = any(item.get("id") == name for item in state.get("custom_brands") or [])
    hidden = set(state.get("hidden_brands") or [])
    if name in hidden or (seed is None and not is_custom):
        raise DraftError("That brand is not on the roster.")
    updated = _copy(state)
    updated["custom_brands"] = [item for item in updated["custom_brands"] if item.get("id") != name]
    for key in (
        "pieces",
        "stats",
        "connections",
        "assets",
        "campaigns",
        "ideas",
        "notices",
        "hashtag_sets",
        "trends",
        "inbox",
        "reports",
        "voice_imports",
        "history",
        "goals",
        "recurrences",
        "ingest_log",
        "memory_log",
        "predictions",
        "series",
        "feedback",
        "cross_accepted",
        "mode_batches",
        "mode_log",
        "previews",
    ):
        updated[key] = [item for item in updated.get(key) or [] if item.get("brand_id") != name]
    for key in ("channels", "pulls", "voices", "approval_steps", "inbox_errors", "voice_versions", "ingest_maps", "memory_marks", "studio_reads", "prediction_hidden", "sites", "cross_enabled", "modes", "mode_limits", "mail_prefs", "mix_targets", "pauses", "adapt_rules", "series_paused"):
        current = dict(updated.get(key) or {})
        current.pop(name, None)
        updated[key] = current
    if seed is not None:
        updated["hidden_brands"] = [item for item in updated.get("hidden_brands") or [] if item != name] + [name]
    save(updated, path)
    _drop_asset_dir(name, root)
    return {"id": name, "removed": True}


def _drop_asset_dir(brand_id: str, root: Path | None) -> None:
    if not _ID.fullmatch(brand_id):
        return
    from library import assets_root

    base = (root or assets_root()).resolve()
    target = (base / brand_id).resolve()
    if target.parent != base or target.is_symlink() or not target.is_dir():
        return
    shutil.rmtree(target)


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
    from predict import apply_grades

    updated = apply_grades(updated, brand.id)
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
    posts = combine_posts(ledger_posts, recorded)
    return _with_history(state, brand_id, posts), page_days


def import_history(state: dict, brand_id: str, csv_text: str, path: Path | None = None) -> dict:
    from analytics_desk import parse_history_csv

    resolve_brand(state, brand_id)
    rows, undated = parse_history_csv(csv_text)
    updated = _copy(state)
    current = list(updated.get("history") or [])
    others = [row for row in current if row.get("brand_id") != brand_id]
    mine = [row for row in current if row.get("brand_id") == brand_id]
    added = [_history_post(brand_id, item) for item in rows]
    updated["history"] = others + (mine + added)[-500:]
    save(updated, path)
    used = len([row for row in added if row.get("published_at") and row.get("engagements") is not None])
    return {"imported": len(added), "undated": undated, "used": used}


def save_goal(state: dict, brand_id: str, spec: dict, path: Path | None = None) -> dict:
    from analytics_desk import metric_allowed

    resolve_brand(state, brand_id)
    if not isinstance(spec, dict):
        raise DraftError("A goal needs a metric and dates.")
    metric = str(spec.get("metric") or "")
    if not metric_allowed(metric):
        raise DraftError("Goals cover engagements, shares, saves, reach, and follows.")
    change = _goal_percent(spec.get("change"))
    start = str(spec.get("start") or "")
    end = str(spec.get("end") or "")
    try:
        start_day = datetime.strptime(start, "%Y-%m-%d").date()
        end_day = datetime.strptime(end, "%Y-%m-%d").date()
    except ValueError as exc:
        raise DraftError("Goal dates are YYYY-MM-DD.") from exc
    if end_day < start_day:
        raise DraftError("The goal ends before it starts.")
    goal = {"id": str(uuid.uuid4()), "brand_id": brand_id, "metric": metric, "change": change, "start": start, "end": end}
    updated = _copy(state)
    current = list(updated.get("goals") or [])
    others = [row for row in current if row.get("brand_id") != brand_id]
    mine = [goal, *[row for row in current if row.get("brand_id") == brand_id]][:12]
    updated["goals"] = mine + others
    save(updated, path)
    return goal


def mark_assisted(state: dict, piece_id: str, path: Path | None = None) -> dict:
    updated = _copy(state)
    index, piece = _find(updated, piece_id)
    if piece.get("assisted"):
        return piece
    next_piece = {**piece, "assisted": True}
    updated["pieces"][index] = next_piece
    save(updated, path)
    return next_piece


def _history_post(brand_id: str, item: dict) -> dict:
    return {
        "id": "history:" + str(uuid.uuid4()),
        "brand_id": brand_id,
        "preview": item.get("text") or "",
        "published_at": item.get("published_at") or "",
        "local_hour": item.get("local_hour"),
        "engagements": item.get("engagements"),
        "impressions": item.get("impressions"),
        "comments": item.get("comments"),
        "shares": int(item.get("shares") or 0) if item.get("shares") is not None else 0,
        "saves": item.get("saves"),
        "clicks": item.get("clicks"),
        "video_completion": item.get("video_completion"),
        "platform": item.get("platform") or "",
        "format": item.get("format") or "unknown",
        "pillar": item.get("pillar") or "",
        "source": "history",
    }


def _with_history(state: dict, brand_id: str, posts: list[dict]) -> list[dict]:
    seen = {str(post.get("id") or "") for post in posts}
    extra = []
    for item in state.get("history") or []:
        if item.get("brand_id") != brand_id or not item.get("published_at") or item.get("engagements") is None:
            continue
        row_id = str(item.get("id") or "")
        if not row_id or row_id in seen:
            continue
        seen.add(row_id)
        extra.append(item)
    for item in state.get("voice_imports") or []:
        if item.get("brand_id") != brand_id or not item.get("published_at") or item.get("engagements") is None:
            continue
        row_id = str(item.get("id") or "")
        if not row_id or row_id in seen:
            continue
        seen.add(row_id)
        extra.append(
            {
                "id": row_id,
                "preview": item.get("preview") or "",
                "published_at": item.get("published_at") or "",
                "engagements": int(item.get("engagements") or 0),
                "shares": int(item.get("shares") or 0),
                "format": "unknown",
                "source": "voice",
            }
        )
    return list(posts) + extra


def _boost_view(state: dict, brand_id: str, posts: list[dict]) -> dict:
    from boost import boost_for

    return boost_for(state, brand_id, posts)


def _goal_view(state: dict, brand_id: str, posts: list[dict], page_days: list[dict], today) -> list[dict]:
    from analytics_desk import goal_line

    rows = [goal for goal in state.get("goals") or [] if goal.get("brand_id") == brand_id]
    return [goal_line(goal, posts, page_days, today) for goal in rows]


def _imported_count(state: dict, brand_id: str) -> int:
    return len(
        [
            row
            for row in state.get("history") or []
            if row.get("brand_id") == brand_id and row.get("published_at") and row.get("engagements") is not None
        ]
    )


def _goal_percent(value: object) -> int:
    if isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
        value = int(value.strip())
    if isinstance(value, bool) or not isinstance(value, int) or value == 0 or value < -90 or value > 500:
        raise DraftError("The goal percent is a whole number from -90 to 500, and not zero.")
    return value


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
    desk = performance(posts, page_days, pieces, when)
    desk = {
        **desk,
        "goals": _goal_view(state, brand_id, posts, page_days, when),
        "imported": _imported_count(state, brand_id),
    }
    from publish import is_live, posting_view

    return {
        "posting": is_live(state, brand_id),
        "publishing": posting_view(state, brand_id),
        "brand": row,
        "calendar": _calendar_view(state, brand_id, pieces, posts, when),
        "performance": desk,
        "boost": _boost_view(state, brand_id, posts),
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
        "voice_desk": _voice_desk(state, brand_id, posts),
        "queue": _queue_view(state, brand_id, posts),
        "campaigns": _campaigns_view(state, brand_id, posts, when),
        "ideas": _ideas_view(state, brand_id, posts),
        "approval": _approval_view(state, brand_id),
        "hashtags": _hashtags_view(state, brand_id, posts),
        "inbox": _inbox_view(state, brand_id, posts),
        "reports": _reports_view(state, brand_id),
        "studio_read": _studio_read_view(state, brand_id),
        "ingest": _ingest_view(state, brand_id),
        "memory": _memory_view(state, brand_id, posts, pieces),
        "series": _series_view(state, brand_id, posts),
        "cross": _cross_view(state, brand_id),
        "modes": _modes_view(state, brand_id, posts),
        "support": _support_view(state, brand_id, posts),
        "map": _map_view(posts, page_days),
        "todo_notes": _todo_notes_view(state, brand_id),
        "apps": apps_view(state),
    }


_HOUSE_APPS = {
    "meta": "house-social.meta.app_secret",
    "threads": "house-social.threads.app_secret",
}


def apps_view(state: dict) -> dict:
    raw = state.get("apps") if isinstance(state.get("apps"), dict) else {}
    view: dict = {"publishing": False}
    for kind in _HOUSE_APPS:
        row = raw.get(kind) if isinstance(raw.get(kind), dict) else {}
        view[kind] = {"app_id": str(row.get("app_id") or ""), "secret_saved": bool(row.get("secret_vault"))}
    return view


def save_apps(state: dict, spec: dict, path: Path | None = None, vault_write=None) -> dict:
    if not isinstance(spec, dict):
        raise DraftError("The house apps need an id.")
    updated = _copy(state)
    book = {}
    for kind, row in (updated.get("apps") or {}).items():
        if kind in _HOUSE_APPS and isinstance(row, dict):
            book[kind] = {key: row.get(key) for key in ("app_id", "secret_vault") if row.get(key)}
    writer = vault_write or _write_vault
    pending = []
    for kind, vault_name in _HOUSE_APPS.items():
        if kind not in spec:
            continue
        row_spec = spec.get(kind)
        if not isinstance(row_spec, dict):
            raise DraftError("A house app needs an id.")
        current = dict(book.get(kind) or {})
        if "app_id" in row_spec:
            current["app_id"] = _app_id(row_spec.get("app_id"))
        secret = str(row_spec.get("secret") or "").strip()
        if secret:
            if len(secret) < 8 or len(secret) > 200:
                raise DraftError("That app secret does not look usable.")
            pending.append((kind, vault_name, secret))
        book[kind] = {key: value for key, value in current.items() if key in {"app_id", "secret_vault"} and value}
    for kind, vault_name, secret in pending:
        if not writer(vault_name, secret):
            raise DraftError("The app secret did not reach the vault. Nothing was saved.")
        book[kind] = {**book.get(kind, {}), "secret_vault": f"vault:{vault_name}"}
    updated["apps"] = book
    save(updated, path)
    return apps_view(updated)


def _house_app_id(state: dict, platform: str) -> str:
    kind = "threads" if platform == "threads" else "meta"
    raw = state.get("apps") if isinstance(state.get("apps"), dict) else {}
    row = raw.get(kind) if isinstance(raw.get(kind), dict) else {}
    return str(row.get("app_id") or "").strip()


def _app_id(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if not text.isdigit() or not 5 <= len(text) <= 32:
        raise DraftError("An app id is digits.")
    return text


def save_connection(state: dict, spec: dict, path: Path | None = None, vault_write=None) -> dict:
    brand = resolve_brand(state, str(spec.get("brand_id", "")))
    platform = str(spec.get("platform", "")).strip()
    if platform not in PLATFORMS:
        raise DraftError("Channels are facebook, instagram, and threads.")
    external_id = _label(spec.get("external_id") or "", 64)
    app_id = _house_app_id(state, platform) or _label(spec.get("app_id") or "", 32)
    if not external_id:
        raise DraftError("A connection needs the page or account id.")
    if not app_id:
        if platform == "threads":
            raise DraftError("Set the house Threads app before connecting an account.")
        raise DraftError("Set the house Meta app before connecting a Page.")
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
        raise DraftError("Connect this brand's Facebook Page, Instagram, or Threads account under Accounts first.")
    read = reader or _read_vault
    fetch = fetcher or pull_platform
    find_instagram = lookup_instagram if discover is None else discover
    # An Instagram account picked on Accounts wins over the one the Page names.
    chosen_instagram = any(item.get("platform") == "instagram" and item.get("via") != "facebook" for item in mine)
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
        if connection.get("platform") != "facebook" or chosen_instagram or connection.get("skip_instagram"):
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
            if not (item.get("brand_id") == brand_id and item.get("platform") == "instagram" and item.get("via") == "facebook")
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
        "name": connection.get("name") or "",
        "page_id": connection.get("page_id") or "",
        "via": connection.get("via") or "",
        "connected_at": connection.get("connected_at") or "",
        "expires_at": connection.get("expires_at") or "",
        "connected": bool(connection.get("token_vault")),
    }


def _vault_env(base: dict | None = None, env_file: Path | None = None) -> dict:
    env = dict(os.environ if base is None else base)
    if env.get("AGENT_VAULT_TOKEN") and env.get("AGENT_VAULT_URL"):
        return env
    path = env_file or (Path.home() / ".config" / "agent-vault" / "env")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return env
    for line in lines:
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.removeprefix("export").strip()
        value = value.strip().strip("'").strip('"')
        if key in {"AGENT_VAULT_URL", "AGENT_VAULT_TOKEN"} and value and not env.get(key):
            env[key] = value
    return env


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
            env=_vault_env(),
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
        result = subprocess.run(
            [binary, name],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
            env=_vault_env(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    value = (result.stdout or "").strip()
    return value or None


def save_voice(state: dict, brand_id: str, spec: dict, path: Path | None = None, note: str = "saved") -> dict:
    from voice import guide_for

    resolve_brand(state, brand_id)
    if not isinstance(spec, dict):
        raise DraftError("The voice guide needs fields.")
    guide = guide_for(brand_id, spec)
    for key in ("tone", "personality", "visual", "differentiation"):
        if len(guide[key]) > 600:
            raise DraftError("That voice field is too long.")
    updated = _copy(state)
    updated.setdefault("voices", {})
    previous = updated["voices"].get(brand_id)
    updated["voices"][brand_id] = guide
    if previous != guide or note != "saved":
        versions = dict(updated.get("voice_versions") or {})
        history = list(versions.get(brand_id) or [])
        history.append(
            {
                "id": str(uuid.uuid4()),
                "at": datetime.now(ZoneInfo("America/New_York")).isoformat(),
                "note": _label(note or "saved", 80),
                "guide": copy.deepcopy(guide),
            }
        )
        versions[brand_id] = history[-20:]
        updated["voice_versions"] = versions
    save(updated, path)
    return guide


def import_voice_csv(state: dict, brand_id: str, csv_text: str, path: Path | None = None) -> dict:
    from voice import parse_voice_csv

    resolve_brand(state, brand_id)
    rows = parse_voice_csv(csv_text)
    updated, count = _add_voice_rows(state, brand_id, rows, "csv")
    save(updated, path)
    return {"imported": count, "imports": _import_count(updated, brand_id)}


def add_voice_post(state: dict, brand_id: str, spec: dict, path: Path | None = None) -> dict:
    from meta import redact
    from voice import guide_for

    resolve_brand(state, brand_id)
    if not isinstance(spec, dict):
        raise DraftError("Write the post.")
    text = redact(_label(spec.get("text") or "", 500))
    if not text:
        raise DraftError("Write the post.")
    engagements = _optional_count(spec.get("engagements"))
    kind = spec.get("kind") if spec.get("kind") in {"on", "off"} else ""
    updated, _count = _add_voice_rows(
        state,
        brand_id,
        [{"text": text, "engagements": engagements, "shares": 0, "published_at": "", "platform": ""}],
        "manual",
    )
    if not kind:
        save(updated, path)
        return {"imported": 1, "imports": _import_count(updated, brand_id)}
    guide = guide_for(brand_id, updated.get("voices", {}).get(brand_id))
    examples = list(guide.get("examples") or []) + [
        {"title": _label(spec.get("title") or "", 80), "text": text, "kind": kind, "source": "saved"}
    ]
    saved = save_voice(updated, brand_id, {**guide, "examples": examples}, path, note="saved an example")
    return {"imported": 1, "voice": saved}


def accept_voice_suggestion(state: dict, brand_id: str, suggestion_id: str, path: Path | None = None, posts: list[dict] | None = None) -> dict:
    from voice import guide_for, voice_lessons

    resolve_brand(state, brand_id)
    guide = guide_for(brand_id, (state.get("voices") or {}).get(brand_id))
    history = list(posts) if posts is not None else list(brand_history(state, brand_id)[0])
    imports = [row for row in state.get("voice_imports") or [] if row.get("brand_id") == brand_id]
    lessons = voice_lessons(guide, history + imports)
    found = next((item for item in lessons["suggestions"] if item.get("id") == suggestion_id), None)
    if found is None:
        raise DraftError("That suggestion is not supported by these posts.")
    spec = copy.deepcopy(guide)
    if found["kind"] == "preferred":
        spec["preferred"] = list(spec.get("preferred") or []) + [found.get("line") or ""]
    elif found["kind"] == "second_person":
        spec["second_person"] = True
    elif found["kind"] == "example" and found.get("example"):
        spec["examples"] = list(spec.get("examples") or []) + [found["example"]]
    else:
        raise DraftError("That suggestion cannot be saved.")
    return save_voice(state, brand_id, spec, path, note=f"accepted {suggestion_id}"[:80])


def restore_voice(state: dict, brand_id: str, version_id: str, path: Path | None = None) -> dict:
    resolve_brand(state, brand_id)
    history = list(((state.get("voice_versions") or {}).get(brand_id) or []))
    found = next((item for item in history if item.get("id") == version_id), None)
    if found is None:
        raise DraftError("That voice version is not on this brand.")
    return save_voice(state, brand_id, found.get("guide") or {}, path, note="restored")


def voice_check_brand(state: dict, brand_id: str, fields: dict) -> dict:
    from voice import guide_for, voice_report

    resolve_brand(state, brand_id)
    guide = guide_for(brand_id, (state.get("voices") or {}).get(brand_id))
    return voice_report(guide, fields)


def _voice_view(state: dict, brand_id: str) -> dict:
    from voice import guide_for

    return guide_for(brand_id, (state.get("voices") or {}).get(brand_id))


def _voice_desk(state: dict, brand_id: str, posts: list[dict]) -> dict:
    from voice import guide_for, voice_lessons

    guide = guide_for(brand_id, (state.get("voices") or {}).get(brand_id))
    imports = [row for row in state.get("voice_imports") or [] if row.get("brand_id") == brand_id]
    versions = list((state.get("voice_versions") or {}).get(brand_id) or [])
    return {
        "versions": [
            {
                "id": item.get("id"),
                "at": item.get("at") or "",
                "note": item.get("note") or "",
                "tone": str((item.get("guide") or {}).get("tone") or ""),
                "formality": str((item.get("guide") or {}).get("formality") or ""),
                "preferred": list((item.get("guide") or {}).get("preferred") or []),
            }
            for item in versions
        ][::-1],
        "lessons": voice_lessons(guide, list(posts) + imports),
        "imports": len(imports),
    }


def _add_voice_rows(state: dict, brand_id: str, rows: list[dict], source: str) -> tuple[dict, int]:
    updated = _copy(state)
    current = list(updated.get("voice_imports") or [])
    mine = [row for row in current if row.get("brand_id") == brand_id]
    others = [row for row in current if row.get("brand_id") != brand_id]
    added = []
    for item in rows:
        added.append(
            {
                "id": "import:" + str(uuid.uuid4()),
                "brand_id": brand_id,
                "preview": str(item.get("text") or "")[:500],
                "engagements": item.get("engagements"),
                "shares": int(item.get("shares") or 0),
                "published_at": item.get("published_at") or "",
                "platform": item.get("platform") or "",
                "source": source,
            }
        )
    updated["voice_imports"] = others + (mine + added)[-200:]
    return updated, len(added)


def _import_count(state: dict, brand_id: str) -> int:
    return len([row for row in state.get("voice_imports") or [] if row.get("brand_id") == brand_id])


def _optional_count(value: object) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        text = str(value).strip()
        if not text.isdigit():
            raise DraftError("Engagements need a whole number, or they can be left blank.")
        value = int(text)
    if value < 0 or value > 10_000_000:
        raise DraftError("That engagement count is out of range.")
    return int(value)


def _queue_view(state: dict, brand_id: str, posts: list[dict]) -> dict:
    from queue_desk import queue_for

    return queue_for(state, brand_id, posts)


def _campaigns_view(state: dict, brand_id: str, posts: list[dict], today) -> dict:
    from campaigns import campaigns_for

    return campaigns_for(state, brand_id, posts, today)


def _ideas_view(state: dict, brand_id: str, posts: list[dict] | None = None) -> dict:
    from ideas import ideas_for

    return ideas_for(state, brand_id, posts)


def _approval_view(state: dict, brand_id: str) -> dict:
    from approval import approval_for

    return approval_for(state, brand_id)


def _hashtags_view(state: dict, brand_id: str, posts: list[dict]) -> dict:
    from hashtags import hashtags_for

    return hashtags_for(state, brand_id, posts)


def _inbox_view(state: dict, brand_id: str, posts: list[dict] | None = None) -> dict:
    from inbox import inbox_for

    return inbox_for(state, brand_id, posts)


def _reports_view(state: dict, brand_id: str) -> dict:
    from reports import reports_for

    return reports_for(state, brand_id)


def _studio_read_view(state: dict, brand_id: str) -> dict:
    from studio_read import studio_view

    return studio_view(state, brand_id)


def _ingest_view(state: dict, brand_id: str) -> dict:
    from ingest import ingest_for

    return ingest_for(state, brand_id)


def resolve_brand(state: dict, brand_id: str) -> Brand:
    seed = seed_brand(brand_id)
    if seed is not None:
        if brand_id in set(state.get("hidden_brands") or []):
            raise DraftError(f"Unknown brand: {brand_id}")
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
    keys = ("impressions", "engagements", "likes", "comments", "shares", "saves", "follows", "clicks", "video_completion")
    metrics = {}
    for key in keys:
        if key not in payload or payload[key] in ("", None):
            continue
        value = payload[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise DraftError("Metrics are whole numbers, zero or more.")
        if key == "video_completion" and value > 100:
            raise DraftError("Video completion is 0 through 100.")
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


def _todo_notes_view(state: dict, brand_id: str) -> dict:
    from todo_notes import notes_view

    return notes_view(state, brand_id)


def _map_view(posts: list[dict], page_days: list[dict]) -> dict:
    from engagement_map import map_for

    return map_for(posts, page_days)


def _support_view(state: dict, brand_id: str, posts: list[dict]) -> dict:
    from support import support_view

    return support_view(state, brand_id, posts)


def _modes_view(state: dict, brand_id: str, posts: list[dict]) -> dict:
    from modes import mode_view

    return mode_view(state, brand_id, posts)


def _cross_view(state: dict, brand_id: str) -> dict:
    from cross_brand import cross_for

    return cross_for(state, brand_id)


def _series_view(state: dict, brand_id: str, posts: list[dict]) -> dict:
    from series import series_for

    return series_for(state, brand_id, posts)


def _memory_view(state: dict, brand_id: str, posts: list[dict], pieces: list[dict]) -> dict:
    from memory import memory_for

    return memory_for(state, brand_id, posts, pieces)


def _calendar_view(state: dict, brand_id: str, pieces: list[dict], posts: list[dict], today) -> dict:
    from calendar_desk import advise
    from memory import marks_for

    desk = _calendar(pieces, posts, today)
    pillars = next((item.get("pillars") or [] for item in roster(state) if item["id"] == brand_id), [])
    desk["advice"] = advise(desk["entries"], pillars, posts, today, marks=marks_for(state, brand_id))
    desk["recurrences"] = [
        {
            "id": item.get("id"),
            "name": item.get("name") or "",
            "weekday": item.get("weekday"),
            "weeks": item.get("weeks"),
            "idea": item.get("idea") or "",
            "pillar": item.get("pillar") or "",
            "format": item.get("format") or "",
        }
        for item in state.get("recurrences") or []
        if item.get("brand_id") == brand_id
    ]
    return desk


def save_recurrence(state: dict, brand_id: str, spec: dict, path: Path | None = None) -> dict:
    resolve_brand(state, brand_id)
    if not isinstance(spec, dict):
        raise DraftError("A recurrence needs a name and a weekday.")
    name = _label(spec.get("name") or "", 80)
    idea = _label(spec.get("idea") or "", 500)
    if not name or not idea:
        raise DraftError("Name the recurrence and give it the words.")
    weekday = spec.get("weekday")
    if isinstance(weekday, str) and weekday.isdigit():
        weekday = int(weekday)
    if isinstance(weekday, bool) or not isinstance(weekday, int) or not 0 <= weekday <= 6:
        raise DraftError("Weekday is 0 for Monday through 6 for Sunday.")
    weeks = spec.get("weeks") if spec.get("weeks") not in (None, "") else 4
    if isinstance(weeks, str) and weeks.isdigit():
        weeks = int(weeks)
    if isinstance(weeks, bool) or not isinstance(weeks, int) or not 1 <= weeks <= 8:
        raise DraftError("A recurrence covers 1 to 8 weeks.")
    row = {
        "id": str(uuid.uuid4()),
        "brand_id": brand_id,
        "name": name,
        "weekday": weekday,
        "weeks": weeks,
        "idea": idea,
        "pillar": _label(spec.get("pillar") or "", 40),
        "format": _format_name(brand_id, str(spec.get("format") or "")),
    }
    updated = _copy(state)
    current = list(updated.get("recurrences") or [])
    others = [item for item in current if item.get("brand_id") != brand_id]
    mine = [row, *[item for item in current if item.get("brand_id") == brand_id]][:12]
    updated["recurrences"] = mine + others
    save(updated, path)
    return row


def apply_recurrence(state: dict, brand_id: str, recurrence_id: str, path: Path | None = None, today=None) -> dict:
    from calendar_desk import next_dates, slot_when
    from learn import suggest_hour

    resolve_brand(state, brand_id)
    row = next((item for item in state.get("recurrences") or [] if item.get("id") == recurrence_id and item.get("brand_id") == brand_id), None)
    if row is None:
        raise DraftError("That recurrence is not on this brand.")
    when = today or datetime.now(ZoneInfo("America/New_York")).date()
    posts, _days = brand_history(state, brand_id)
    hour = suggest_hour(posts)
    clock = hour.get("hour") if hour.get("clear") else None
    current = state
    created = 0
    for day in next_dates(when, int(row["weekday"]), int(row["weeks"])):
        already = any(
            piece.get("recurrence_id") == row["id"] and str(piece.get("scheduled_for") or "").startswith(day.isoformat())
            for piece in current.get("pieces") or []
        )
        if already:
            continue
        piece = create_piece(
            current,
            brand_id,
            row.get("idea") or row.get("name") or "Recurring",
            path=path,
            pillar=row.get("pillar") or "",
            format_name=row.get("format") or "",
            scheduled_for=slot_when(day, clock),
            status="planned",
        )
        current = load(path)
        index, saved = _find(current, piece["id"])
        pieces = list(current.get("pieces") or [])
        pieces[index] = {**saved, "recurrence_id": row["id"]}
        current = {**current, "pieces": pieces}
        save(current, path)
        created += 1
    return {"created": created, "id": row["id"]}


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
        "draggable": status != "published",
        "permalink": next((row.get("permalink") for row in (piece.get("published") or {}).values() if row.get("permalink")), ""),
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
    from publish import is_live

    overrides = state["channels"].get(brand_id, {})
    live = is_live(state, brand_id)
    connected = {
        item.get("platform") for item in state.get("connections") or []
        if item.get("brand_id") == brand_id and item.get("token_vault")
    }
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
                "posting": live and seed.platform in connected,
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
        "removable": True,
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
