"""Dashboard routes for House Social, mounted at /api/plugins/house-social/."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapt import DraftError, LIMITS, JOSIE_CARD
from assist import assist, ollama_complete
from brands import PLATFORMS
from library import library_for, open_asset_file, record_use, revise_asset, save_asset
from store import (
    add_brand,
    create_piece,
    delete_piece,
    ledger_dir,
    load,
    pull_brand,
    record_stat,
    resolve_brand,
    roster,
    save_connection,
    save_voice,
    set_channels,
    studio,
    update_piece,
    voice_check_brand,
    brand_history,
)
from queue_desk import bulk_queue
from voice import guide_for
from learn import read_ledger

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
        return assist(
            guide,
            str(body.get("action") or ""),
            str(body.get("text") or ""),
            complete=ollama_complete,
            image=image,
            mime=mime,
            brand_tags=tuple(brand.tags),
        )
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
