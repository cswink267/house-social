"""A short inbox for one brand.

Comments, mentions, and messages come from a pull. A missing
permission is an error line, not an invented message. A pull never
sends. Offering a saved reply is a separate step.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from adapt import DraftError
from assist import assist
from meta import redact
from store import resolve_brand, save


def inbox_for(state: dict, brand_id: str, posts: list[dict] | None = None) -> dict:
    brand = resolve_brand(state, brand_id)
    ahead = _ahead_posts(posts or [])
    items = [
        _noted(item, ahead)
        for item in state.get("inbox") or []
        if item.get("brand_id") == brand.id
    ]
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
        raise DraftError("Connect this brand's Facebook Page, Instagram, or Threads account under Accounts first.")
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
    from reply_learn import apply_counts

    updated = apply_counts({
        **state,
        "inbox": [*merged, *kept][:200],
        "inbox_errors": {**(state.get("inbox_errors") or {}), brand.id: errors[:12]},
    }, merged)
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
    public = _noted(saved, _ahead_posts([]))
    public["voice"] = (result.get("options") or [{}])[0].get("voice")
    return public


def keep_inbox_idea(state: dict, item_id: str, posts: list[dict] | None, path: Path | None = None) -> dict:
    from ideas import save_idea

    _updated, item = _replace(state, item_id, {})
    if item.get("kind") == "dm":
        raise DraftError("A message stays in the inbox. It is not a content idea.")
    noted = _noted(item, _ahead_posts(posts or []))
    if not noted["question"] and not noted["ahead"]:
        raise DraftError("This note is not a question, and it is not on a post that is at least 3× the others.")
    return save_idea(
        state,
        str(item.get("brand_id") or ""),
        {
            "text": noted["text"],
            "source": "comment",
            "inbox_id": item.get("id") or "",
            "note": str(item.get("author") or ""),
        },
        path,
    )


def keep_inbox_voice(state: dict, item_id: str, reply: str = "", path: Path | None = None) -> dict:
    from store import add_voice_post

    _updated, item = _replace(state, item_id, {})
    text = str(reply or item.get("reply") or "").strip()
    if not text:
        raise DraftError("Write the reply before it can go into the voice.")
    if len(text) > 500:
        raise DraftError("That reply is too long to keep in the voice.")
    return add_voice_post(
        state,
        str(item.get("brand_id") or ""),
        {"text": text, "kind": "on", "title": "Inbox reply"},
        path,
    )


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
            "reply_state": old.get("reply_state") or "",
            "reply_code": old.get("reply_code") or "",
            "reply_hold": old.get("reply_hold") or "",
            "reply_note": old.get("reply_note") or "",
            "sent_at": old.get("sent_at") or "",
            "likes": item["likes"] if "likes" in item else old.get("likes"),
            "replies": item["replies"] if "replies" in item else old.get("replies"),
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
        "post_id": str(item.get("post_id") or ""),
        "reply_state": item.get("reply_state") or "",
        "sending": False,
    }


def _noted(item: dict, ahead: dict[str, dict]) -> dict:
    public = _public(item)
    post_id = public["post_id"]
    post = ahead.get(post_id) if post_id else None
    question = "?" in public["text"] and not public["dismissed"]
    flagged = bool(post) and not public["dismissed"] and public["kind"] != "dm"
    if flagged:
        public["needs_attention"] = True
    public["ahead"] = flagged
    public["question"] = question and public["kind"] != "dm"
    if flagged:
        public["prompt"] = (
            f"This is on a post with {int(post.get('engagements') or 0)} engagements. "
            "That post is at least 3× the others."
        )
    elif public["question"]:
        public["prompt"] = "This is a question. It can be kept as an idea. It is not a score."
    else:
        public["prompt"] = "This note is not on a post that is at least 3× the others."
    return public


def _ahead_posts(posts: list[dict]) -> dict[str, dict]:
    from analytics_desk import _alerts

    return {str(item.get("id") or ""): item for item in _alerts(posts) if item.get("id")}
