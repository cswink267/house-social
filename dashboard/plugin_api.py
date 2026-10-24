"""Dashboard routes for House Social, mounted at /api/plugins/house-social/."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics_desk import read_draft, remix_source
from adapt import DraftError, LIMITS, JOSIE_CARD
from approval import add_comment, decide, mark_notice, save_steps, submit_review
from assist import assist, ollama_complete
from brands import PLATFORMS
from library import library_for, open_asset_file, read_asset_tags, record_use, revise_asset, save_asset
from store import (
    accept_voice_suggestion,
    add_brand,
    remove_brand,
    add_voice_post,
    apply_recurrence,
    create_piece,
    delete_piece,
    import_history,
    import_voice_csv,
    ledger_dir,
    load,
    mark_assisted,
    pull_brand,
    record_stat,
    resolve_brand,
    restore_voice,
    roster,
    save_connection,
    save_goal,
    save_recurrence,
    save_voice,
    set_channels,
    studio,
    update_piece,
    voice_check_brand,
    brand_history,
)
from campaigns import attach_campaign, clone_campaign, keep_retrospective, kind_lessons, revise_campaign, save_campaign
from queue_desk import bulk_queue
from voice import guide_for
from hashtags import apply_set, save_set, save_trend, use_ahead
from inbox import keep_inbox_idea, keep_inbox_voice, refresh_inbox, save_inbox_reply, suggest_inbox_reply
from reports import generate_report, report_export, write_insight
from ideas import draft_idea, idea_brief, keep_shape, revise_idea, save_idea
from ingest import commit_ingest, preview_ingest
from learn import read_ledger
from studio_read import pull_studio

router = APIRouter()


def _fail(exc: DraftError) -> None:
    raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/roster")
def get_roster() -> dict:
    return {"posting": False, "platforms": list(PLATFORMS), "limits": LIMITS, "card_limit": JOSIE_CARD, "brands": roster(load())}


@router.post("/brands")
def post_brand(body: dict) -> dict:
    try:
        return add_brand(load(), body)
    except DraftError as exc:
        _fail(exc)


@router.delete("/brands/{brand_id}")
def delete_brand(brand_id: str) -> dict:
    try:
        return remove_brand(load(), brand_id)
    except DraftError as exc:
        _fail(exc)


@router.put("/brands/{brand_id}/channels")
def put_channels(brand_id: str, body: dict) -> dict:
    try:
        return {"channels": set_channels(load(), brand_id, body)}
    except DraftError as exc:
        _fail(exc)


@router.get("/pieces")
def get_pieces() -> dict:
    return {"posting": False, "pieces": load()["pieces"]}


@router.post("/connections")
def post_connection(body: dict) -> dict:
    try:
        return save_connection(load(), body)
    except DraftError as exc:
        _fail(exc)


@router.post("/brands/{brand_id}/pull")
def post_pull(brand_id: str) -> dict:
    try:
        return pull_brand(load(), brand_id)
    except DraftError as exc:
        _fail(exc)


@router.get("/brands/{brand_id}/studio")
def get_studio(brand_id: str) -> dict:
    ledger = {"posts": [], "days": []}
    if brand_id == "josie-blackthorn":
        ledger = read_ledger(ledger_dir())
    try:
        return studio(load(), brand_id, ledger)
    except DraftError as exc:
        _fail(exc)


@router.post("/brands/{brand_id}/studio-read")
def post_studio_read(brand_id: str) -> dict:
    try:
        return pull_studio(load(), brand_id)
    except DraftError as exc:
        _fail(exc)


@router.post("/brands/{brand_id}/voice")
def post_voice(brand_id: str, body: dict) -> dict:
    try:
        return save_voice(load(), brand_id, body)
    except DraftError as exc:
        _fail(exc)


@router.post("/brands/{brand_id}/voice-check")
def post_voice_check(brand_id: str, body: dict) -> dict:
    try:
        return voice_check_brand(load(), brand_id, body)
    except DraftError as exc:
        _fail(exc)


@router.post("/brands/{brand_id}/voice/import")
def post_voice_import(brand_id: str, body: dict) -> dict:
    try:
        if str((body or {}).get("csv") or "").strip():
            return import_voice_csv(load(), brand_id, str(body.get("csv") or ""))
        return add_voice_post(load(), brand_id, body or {})
    except DraftError as exc:
        _fail(exc)


@router.post("/brands/{brand_id}/voice/accept")
def post_voice_accept(brand_id: str, body: dict) -> dict:
    state = load()
    ledger = {"posts": [], "days": []}
    if brand_id == "josie-blackthorn":
        ledger = read_ledger(ledger_dir())
    posts, _days = brand_history(state, brand_id, ledger)
    try:
        return accept_voice_suggestion(state, brand_id, str((body or {}).get("id") or ""), posts=posts)
    except DraftError as exc:
        _fail(exc)


@router.post("/brands/{brand_id}/voice/restore")
def post_voice_restore(brand_id: str, body: dict) -> dict:
    try:
        return restore_voice(load(), brand_id, str((body or {}).get("id") or ""))
    except DraftError as exc:
        _fail(exc)


@router.get("/brands/{brand_id}/library")
def get_library(brand_id: str, q: str = "", kind: str = "", folder: str = "", tag: str = "") -> dict:
    try:
        return library_for(load(), brand_id, q=q, kind=kind, folder=folder, tag=tag)
    except DraftError as exc:
        _fail(exc)


@router.post("/brands/{brand_id}/assets")
def post_asset(brand_id: str, body: dict) -> dict:
    try:
        return save_asset(load(), brand_id, body)
    except DraftError as exc:
        _fail(exc)


@router.patch("/assets/{asset_id}")
def patch_asset(asset_id: str, body: dict) -> dict:
    try:
        return revise_asset(load(), asset_id, body)
    except DraftError as exc:
        _fail(exc)


@router.post("/assets/{asset_id}/tags")
def post_asset_tags(asset_id: str) -> dict:
    state = load()
    try:
        return read_asset_tags(state, asset_id, ollama_complete)
    except DraftError as exc:
        _fail(exc)


@router.post("/assets/{asset_id}/use")
def post_asset_use(asset_id: str, body: dict) -> dict:
    try:
        return record_use(load(), asset_id, body)
    except DraftError as exc:
        _fail(exc)


@router.get("/assets/{asset_id}/file")
def get_asset_file(asset_id: str, version: str = "", frame: int | None = None):
    try:
        found = open_asset_file(load(), asset_id, version, frame)
    except DraftError as exc:
        _fail(exc)
    return FileResponse(found["path"], media_type=found["mime"], filename=found["name"])


@router.post("/brands/{brand_id}/draft-read")
def post_draft_read(brand_id: str, body: dict) -> dict:
    state = load()
    try:
        brand = resolve_brand(state, brand_id)
    except DraftError as exc:
        _fail(exc)
    ledger = {"posts": [], "days": []}
    if brand.id == "josie-blackthorn":
        ledger = read_ledger(ledger_dir())
    posts, _days = brand_history(state, brand.id, ledger)
    from memory import marks_for
    from predict import is_hidden, predict_range, remember_prediction

    reading = read_draft(str((body or {}).get("text") or ""), posts, marks=marks_for(state, brand.id))
    found = predict_range(
        str((body or {}).get("text") or ""),
        posts,
        fmt=str((body or {}).get("format") or ""),
        pillar=str((body or {}).get("pillar") or ""),
        marks=marks_for(state, brand.id),
        hidden=is_hidden(state, brand.id),
    )
    piece_id = str((body or {}).get("piece_id") or "")
    owned = next((item for item in state.get("pieces") or [] if item.get("id") == piece_id and item.get("brand_id") == brand.id), None)
    if owned and not found.get("hidden"):
        remember_prediction(state, brand.id, piece_id, found)
    reading["range"] = found
    return reading


@router.post("/brands/{brand_id}/prediction-hide")
def post_prediction_hide(brand_id: str, body: dict) -> dict:
    from predict import set_prediction_hidden

    try:
        return set_prediction_hidden(
            load(),
            brand_id,
            bool((body or {}).get("hidden")),
            str((body or {}).get("scope") or "brand"),
        )
    except DraftError as exc:
        _fail(exc)


@router.post("/brands/{brand_id}/assist")
def post_assist(brand_id: str, body: dict) -> dict:
    if not isinstance(body, dict):
        _fail(DraftError("The assistant needs a request."))
    state = load()
    try:
        brand = resolve_brand(state, brand_id)
        guide = guide_for(brand.id, (state.get("voices") or {}).get(brand.id))
        image = None
        mime = ""
        asset_id = str(body.get("asset_id") or "")
        if asset_id:
            owned = next((item for item in state.get("assets") or [] if item.get("id") == asset_id), None)
            if not owned or owned.get("brand_id") != brand.id:
                raise DraftError("That asset belongs to another brand.")
            found = open_asset_file(state, asset_id)
            image = Path(found["path"]).read_bytes()
            mime = found["mime"]
        piece_id = str(body.get("piece_id") or "")
        if piece_id:
            owned = next((item for item in state.get("pieces") or [] if item.get("id") == piece_id), None)
            if not owned or owned.get("brand_id") != brand.id:
                raise DraftError("That piece is not on this brand.")
        misses = body.get("misses") if isinstance(body.get("misses"), list) else []
        action = str(body.get("action") or "").strip().lower()
        ledger = {"posts": [], "days": []}
        if brand.id == "josie-blackthorn":
            ledger = read_ledger(ledger_dir())
        posts, _days = brand_history(state, brand.id, ledger)
        if action == "remix":
            remix_source(posts, str(body.get("text") or ""))
        result = assist(
            guide,
            action,
            str(body.get("text") or ""),
            complete=ollama_complete,
            image=image,
            mime=mime,
            brand_tags=tuple(brand.tags),
            misses=tuple(str(item) for item in misses[:6]),
        )
        for option in result.get("options") or []:
            option["reading"] = read_draft(str(option.get("text") or ""), posts)
        result["reading"] = read_draft(str(result.get("text") or body.get("text") or ""), posts)
        if piece_id:
            mark_assisted(state, piece_id)
        return result
    except DraftError as exc:
        _fail(exc)


@router.post("/brands/{brand_id}/queue")
def post_queue(brand_id: str, body: dict) -> dict:
    if not isinstance(body, dict):
        _fail(DraftError("The queue needs an action."))
    state = load()
    ledger = {"posts": [], "days": []}
    if brand_id == "josie-blackthorn":
        ledger = read_ledger(ledger_dir())
    posts, _days = brand_history(state, brand_id, ledger)
    try:
        return bulk_queue(
            state,
            brand_id,
            body.get("ids") or [],
            str(body.get("action") or ""),
            scheduled_for=str(body.get("scheduled_for") or ""),
            posts=posts,
        )
    except DraftError as exc:
        _fail(exc)


@router.post("/brands/{brand_id}/campaigns")
def post_campaign(brand_id: str, body: dict) -> dict:
    try:
        return save_campaign(load(), brand_id, body)
    except DraftError as exc:
        _fail(exc)


@router.patch("/campaigns/{campaign_id}")
def patch_campaign(campaign_id: str, body: dict) -> dict:
    try:
        return revise_campaign(load(), campaign_id, body)
    except DraftError as exc:
        _fail(exc)


@router.post("/campaigns/{campaign_id}/clone")
def post_campaign_clone(campaign_id: str) -> dict:
    try:
        return clone_campaign(load(), campaign_id)
    except DraftError as exc:
        _fail(exc)


@router.post("/campaigns/{campaign_id}/retrospective")
def post_campaign_retrospective(campaign_id: str) -> dict:
    state = load()
    try:
        _index, campaign = next(
            ((index, item) for index, item in enumerate(state.get("campaigns") or []) if item.get("id") == campaign_id),
            (None, None),
        )
        if campaign is None:
            raise DraftError("That campaign is not on this brand.")
        brand_id = campaign["brand_id"]
        ledger = {"posts": [], "days": []}
        if brand_id == "josie-blackthorn":
            ledger = read_ledger(ledger_dir())
        posts, _days = brand_history(state, brand_id, ledger)
        return keep_retrospective(state, campaign_id, posts)
    except DraftError as exc:
        _fail(exc)


@router.post("/campaigns/{campaign_id}/attach")
def post_campaign_attach(campaign_id: str, body: dict) -> dict:
    try:
        return attach_campaign(load(), campaign_id, body)
    except DraftError as exc:
        _fail(exc)


@router.post("/brands/{brand_id}/ideas/suggest")
def post_idea_suggest(brand_id: str) -> dict:
    state = load()
    try:
        brand = resolve_brand(state, brand_id)
    except DraftError as exc:
        _fail(exc)
    ledger = {"posts": [], "days": []}
    if brand.id == "josie-blackthorn":
        ledger = read_ledger(ledger_dir())
    posts, _days = brand_history(state, brand.id, ledger)
    pillars = next((item.get("pillars") or [] for item in roster(state) if item["id"] == brand.id), [])
    trends = [item for item in state.get("trends") or [] if item.get("brand_id") == brand.id]
    guide = guide_for(brand.id, (state.get("voices") or {}).get(brand.id))
    try:
        result = assist(
            guide,
            "ideas",
            idea_brief(pillars, posts, trends, kind_lessons(state, brand.id, posts)),
            complete=ollama_complete,
            brand_tags=tuple(brand.tags),
        )
    except DraftError as exc:
        _fail(exc)
    return {"ideas": [item.get("text") or "" for item in result.get("options") or [] if item.get("text")]}


@router.post("/brands/{brand_id}/ideas/shapes/{post_id}")
def post_keep_shape(brand_id: str, post_id: str) -> dict:
    try:
        return keep_shape(load(), brand_id, post_id)
    except DraftError as exc:
        _fail(exc)


@router.post("/brands/{brand_id}/ideas")
def post_idea(brand_id: str, body: dict) -> dict:
    try:
        return save_idea(load(), brand_id, body)
    except DraftError as exc:
        _fail(exc)


@router.patch("/ideas/{idea_id}")
def patch_idea(idea_id: str, body: dict) -> dict:
    try:
        return revise_idea(load(), idea_id, body)
    except DraftError as exc:
        _fail(exc)


@router.post("/ideas/{idea_id}/draft")
def post_idea_draft(idea_id: str) -> dict:
    try:
        return draft_idea(load(), idea_id)
    except DraftError as exc:
        _fail(exc)


@router.post("/brands/{brand_id}/approval-steps")
def post_approval_steps(brand_id: str, body: dict) -> dict:
    try:
        return save_steps(load(), brand_id, (body or {}).get("steps") or [])
    except DraftError as exc:
        _fail(exc)


@router.post("/pieces/{piece_id}/review")
def post_review(piece_id: str) -> dict:
    try:
        submit_review(load(), piece_id)
        return {"ok": True}
    except DraftError as exc:
        _fail(exc)


@router.post("/pieces/{piece_id}/decision")
def post_decision(piece_id: str, body: dict) -> dict:
    try:
        return decide(load(), piece_id, body)
    except DraftError as exc:
        _fail(exc)


@router.post("/pieces/{piece_id}/comments")
def post_comment(piece_id: str, body: dict) -> dict:
    try:
        return add_comment(load(), piece_id, body)
    except DraftError as exc:
        _fail(exc)


@router.post("/notices/{notice_id}/read")
def post_notice_read(notice_id: str) -> dict:
    try:
        return mark_notice(load(), notice_id)
    except DraftError as exc:
        _fail(exc)


@router.post("/brands/{brand_id}/hashtag-sets")
def post_hashtag_set(brand_id: str, body: dict) -> dict:
    try:
        return save_set(load(), brand_id, body)
    except DraftError as exc:
        _fail(exc)


@router.post("/hashtag-sets/{set_id}/apply")
def post_apply_set(set_id: str, body: dict) -> dict:
    try:
        return apply_set(load(), set_id, str((body or {}).get("piece_id") or ""))
    except DraftError as exc:
        _fail(exc)


@router.post("/brands/{brand_id}/hashtags/use")
def post_use_hashtags(brand_id: str, body: dict) -> dict:
    state = load()
    ledger = {"posts": [], "days": []}
    if brand_id == "josie-blackthorn":
        ledger = read_ledger(ledger_dir())
    posts, _days = brand_history(state, brand_id, ledger)
    try:
        return use_ahead(
            state,
            brand_id,
            str((body or {}).get("piece_id") or ""),
            posts,
            pillar=str((body or {}).get("pillar") or ""),
        )
    except DraftError as exc:
        _fail(exc)


@router.post("/brands/{brand_id}/trends")
def post_trend(brand_id: str, body: dict) -> dict:
    try:
        return save_trend(load(), brand_id, body)
    except DraftError as exc:
        _fail(exc)


@router.post("/brands/{brand_id}/inbox")
def post_inbox(brand_id: str) -> dict:
    try:
        return refresh_inbox(load(), brand_id)
    except DraftError as exc:
        _fail(exc)


@router.post("/inbox/{item_id}/reply")
def post_inbox_reply(item_id: str, body: dict) -> dict:
    try:
        return save_inbox_reply(load(), item_id, body)
    except DraftError as exc:
        _fail(exc)


@router.post("/brands/{brand_id}/recurrences")
def post_recurrence(brand_id: str, body: dict) -> dict:
    try:
        return save_recurrence(load(), brand_id, body or {})
    except DraftError as exc:
        _fail(exc)


@router.post("/recurrences/{recurrence_id}/apply")
def post_apply_recurrence(recurrence_id: str) -> dict:
    state = load()
    row = next((item for item in state.get("recurrences") or [] if item.get("id") == recurrence_id), None)
    if row is None:
        _fail(DraftError("That recurrence is not on this brand."))
    try:
        return apply_recurrence(state, str(row.get("brand_id") or ""), recurrence_id)
    except DraftError as exc:
        _fail(exc)


@router.post("/brands/{brand_id}/reports")
def post_report(brand_id: str, body: dict) -> dict:
    try:
        return generate_report(load(), brand_id, str((body or {}).get("period") or ""), str((body or {}).get("note") or ""))
    except DraftError as exc:
        _fail(exc)


@router.post("/reports/{report_id}/insight")
def post_report_insight(report_id: str) -> dict:
    try:
        return write_insight(load(), report_id, ollama_complete)
    except DraftError as exc:
        _fail(exc)


@router.get("/reports/{report_id}/export")
def get_report_export(report_id: str, fmt: str = "md") -> Response:
    try:
        text, media, name = report_export(load(), report_id, fmt)
    except DraftError as exc:
        _fail(exc)
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in name).strip("-") or "report.md"
    return Response(content=text, media_type=media, headers={"Content-Disposition": f'attachment; filename="{safe[:80]}"'})


@router.post("/inbox/{item_id}/suggest")
def post_inbox_suggest(item_id: str) -> dict:
    state = load()
    item = next((row for row in state.get("inbox") or [] if row.get("id") == item_id), None)
    if item is None:
        _fail(DraftError("That note is not in the inbox."))
    try:
        brand_id = str(item.get("brand_id") or "")
        guide = guide_for(brand_id, (state.get("voices") or {}).get(brand_id))
        return suggest_inbox_reply(state, item_id, guide, ollama_complete)
    except DraftError as exc:
        _fail(exc)


@router.post("/inbox/{item_id}/idea")
def post_inbox_idea(item_id: str) -> dict:
    state = load()
    item = next((row for row in state.get("inbox") or [] if row.get("id") == item_id), None)
    if item is None:
        _fail(DraftError("That note is not in the inbox."))
    brand_id = str(item.get("brand_id") or "")
    ledger = {"posts": [], "days": []}
    if brand_id == "josie-blackthorn":
        ledger = read_ledger(ledger_dir())
    posts, _days = brand_history(state, brand_id, ledger)
    try:
        return keep_inbox_idea(state, item_id, posts)
    except DraftError as exc:
        _fail(exc)


@router.post("/inbox/{item_id}/voice")
def post_inbox_voice(item_id: str, body: dict) -> dict:
    try:
        return keep_inbox_voice(load(), item_id, reply=str((body or {}).get("reply") or ""))
    except DraftError as exc:
        _fail(exc)


@router.post("/brands/{brand_id}/history")
def post_history(brand_id: str, body: dict) -> dict:
    try:
        return import_history(load(), brand_id, str((body or {}).get("csv") or ""))
    except DraftError as exc:
        _fail(exc)


@router.post("/brands/{brand_id}/ingest/preview")
def post_ingest_preview(brand_id: str, body: dict) -> dict:
    from store import resolve_brand

    state = load()
    try:
        resolve_brand(state, brand_id)
        spec = body if isinstance(body, dict) else {}
        spec = {**spec, "saved": (state.get("ingest_maps") or {}).get(brand_id) or {}}
        return preview_ingest(spec)
    except DraftError as exc:
        _fail(exc)


@router.post("/brands/{brand_id}/ingest")
def post_ingest(brand_id: str, body: dict) -> dict:
    try:
        return commit_ingest(load(), brand_id, body if isinstance(body, dict) else {})
    except DraftError as exc:
        _fail(exc)


@router.post("/brands/{brand_id}/memory")
def post_memory(brand_id: str, body: dict) -> dict:
    from memory import correct_memory, reset_memory, sync_memory

    state = load()
    action = str((body or {}).get("action") or "").strip().lower()
    try:
        if action == "reset":
            return reset_memory(state, brand_id)
        if action == "sync":
            return sync_memory(state, brand_id)
        return correct_memory(state, brand_id, str((body or {}).get("pattern_id") or ""), action)
    except DraftError as exc:
        _fail(exc)


@router.get("/brands/{brand_id}/memory/export")
def get_memory_export(brand_id: str, kind: str = "markdown") -> dict:
    from memory import export_memory

    try:
        return export_memory(load(), brand_id, kind)
    except DraftError as exc:
        _fail(exc)


@router.post("/brands/{brand_id}/goals")
def post_goal(brand_id: str, body: dict) -> dict:
    try:
        return save_goal(load(), brand_id, body or {})
    except DraftError as exc:
        _fail(exc)


@router.post("/stats")
def post_stat(body: dict) -> dict:
    try:
        return record_stat(load(), body)
    except DraftError as exc:
        _fail(exc)


@router.post("/pieces")
def post_piece(body: dict) -> dict:
    try:
        return create_piece(
            load(),
            str(body.get("brand_id", "")),
            str(body.get("idea", "")),
            pillar=str(body.get("pillar") or ""),
            format_name=str(body.get("format") or ""),
            hypothesis=str(body.get("hypothesis") or ""),
            campaign=str(body.get("campaign") or ""),
            scheduled_for=str(body.get("scheduled_for") or "") or None,
            status=str(body.get("status") or "draft"),
        )
    except DraftError as exc:
        _fail(exc)


@router.patch("/pieces/{piece_id}")
def patch_piece(piece_id: str, body: dict) -> dict:
    try:
        clear = "scheduled_for" in body and body.get("scheduled_for") in (None, "")
        return update_piece(
            load(),
            piece_id,
            variants=body.get("variants"),
            status=body.get("status"),
            scheduled_for=None if clear else body.get("scheduled_for"),
            clear_schedule=clear,
            pillar=body.get("pillar") if "pillar" in body else None,
            format_name=body.get("format") if "format" in body else None,
            hypothesis=body.get("hypothesis") if "hypothesis" in body else None,
            campaign=body.get("campaign") if "campaign" in body else None,
        )
    except DraftError as exc:
        _fail(exc)


@router.delete("/pieces/{piece_id}")
def remove_piece(piece_id: str) -> dict:
    try:
        delete_piece(load(), piece_id)
    except DraftError as exc:
        _fail(exc)
    return {"ok": True}
