"""A short inbox for one brand. Replies stay drafts.

Comments, mentions, and messages come from a pull. A missing
permission is an error line, not an invented message. Nothing is sent.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from adapt import DraftError
from assist import assist
from meta import redact
from store import resolve_brand, save


def inbox_for(state: dict, brand_id: str) -> dict:
    brand = resolve_brand(state, brand_id)
    items = [_public(item) for item in state.get("inbox") or [] if item.get("brand_id") == brand.id]
    items.sort(key=lambda item: item.get("at") or "", reverse=True)
    items.sort(key=lambda item: 0 if item["needs_attention"] else 1)
    errors = list((state.get("inbox_errors") or {}).get(brand.id) or [])
    return {"items": items, "errors": errors, "sending": False}


def refresh_inbox(state: dict, brand_id: str, path: Path | None = None, reader=None, gather=None) -> dict:
    from meta import gather_inbox
    from store import _read_vault

    brand = resolve_brand(state, brand_id)
    mine = [item for item in state.get("connections") or [] if item.get("brand_id") == brand.id]
    if not mine:
        raise DraftError("Add a Meta app for this brand first.")
    read = reader or _read_vault
    fetch = gather or gather_inbox
    pulled = ((state.get("pulls") or {}).get(brand.id) or {}).get("posts") or []
    fresh: list[dict] = []
    errors: list[str] = []
    for connection in mine:
        if connection.get("platform") == "instagram" and connection.get("via") == "facebook":
            continue
        vault_name = str(connection.get("token_vault") or "").removeprefix("vault:")
        token = read(vault_name)
        if not token:
            errors.append(f"{connection.get('platform')}: no token in the vault.")
            continue
        post_ids = [
            str(post.get("id")) for post in pulled
            if post.get("platform") == connection.get("platform") and post.get("id")
        ][:8]
        found = fetch(str(connection.get("platform") or ""), str(connection.get("external_id") or ""), token, post_ids)
        fresh.extend(found.get("items") or [])
        errors.extend(redact(str(item)) for item in found.get("errors") or [])
    merged = _merge([item for item in state.get("inbox") or [] if item.get("brand_id") == brand.id], fresh, brand.id)
    kept = [item for item in state.get("inbox") or [] if item.get("brand_id") != brand.id]
    updated = {
        **state,
        "inbox": [*merged, *kept][:200],
        "inbox_errors": {**(state.get("inbox_errors") or {}), brand.id: errors[:12]},
    }
    save(updated, path)
    return inbox_for(updated, brand.id)


def save_inbox_reply(state: dict, item_id: str, spec: dict, path: Path | None = None) -> dict:
    if not isinstance(spec, dict):
        raise DraftError("The reply needs words.")
    text = str(spec.get("reply") or "")
    if len(text) > 2000:
        raise DraftError("That reply is too long.")
    changes = {"reply": text.strip()}
    if "dismissed" in spec:
        changes["dismissed"] = bool(spec.get("dismissed"))
    updated, item = _replace(state, item_id, changes)
    save(updated, path)
    return _public(item)


def suggest_inbox_reply(state: dict, item_id: str, guide: dict, complete, path: Path | None = None) -> dict:
    _state, item = _replace(state, item_id, {})
    result = assist(guide, "reply", item.get("text") or "", complete=complete)
    updated, saved = _replace(state, item_id, {"reply": result["text"]})
    save(updated, path)
    public = _public(saved)
    public["voice"] = (result.get("options") or [{}])[0].get("voice")
    return public


def _merge(previous: list[dict], fresh: list[dict], brand_id: str) -> list[dict]:
    prior = {item.get("id"): item for item in previous}
    rows = []
    seen = set()
    for item in fresh:
        if not item.get("id") or item["id"] in seen:
            continue
        seen.add(item["id"])
        old = prior.get(item["id"]) or {}
        rows.append({
            **item,
            "brand_id": brand_id,
            "text": redact(str(item.get("text") or ""))[:500],
            "reply": old.get("reply") or "",
            "dismissed": bool(old.get("dismissed")),
            "pulled_at": datetime.now(timezone.utc).isoformat(),
        })
    return rows


def _replace(state: dict, item_id: str, changes: dict) -> tuple[dict, dict]:
    found = None
    rows = []
    for item in state.get("inbox") or []:
        if item.get("id") == item_id:
            found = {**item, **changes}
            rows.append(found)
        else:
            rows.append(item)
    if found is None:
        raise DraftError("That note is not in the inbox.")
    return {**state, "inbox": rows}, found


def _public(item: dict) -> dict:
    text = str(item.get("text") or "")
    dismissed = bool(item.get("dismissed"))
    needs = False if dismissed else item.get("kind") == "dm" or "?" in text
    return {
        "id": item.get("id"),
        "brand_id": item.get("brand_id"),
        "kind": item.get("kind") or "comment",
        "platform": item.get("platform") or "",
        "author": item.get("author") or "Someone",
        "text": text,
        "at": item.get("at") or "",
        "permalink": item.get("permalink") or "",
        "reply": item.get("reply") or "",
        "dismissed": dismissed,
        "needs_attention": needs,
        "sending": False,
    }
