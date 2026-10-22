"""Pull live posts from a brand's Meta app.

Studio keeps weekly, peak, and now posts. This module only reads what
already went out. Tokens stay in agent-vault. Callers pass the secret
in and get posts back. Nothing here writes a token to disk.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

GRAPH = "https://graph.facebook.com/v25.0"
THREADS = "https://graph.threads.net/v1.0"
_TOKEN = re.compile(r"(access_token=)[^&\s]+", re.I)
_OFFSET = re.compile(r"([+-])(\d{2})(\d{2})$")
_FORMATS = {
    "IMAGE": "feed",
    "VIDEO": "reel",
    "CAROUSEL_ALBUM": "carousel",
    "TEXT": "text",
}


class MetaError(ValueError):
    """A page could not be read. The message never includes a token."""


def redact(text: str) -> str:
    return _TOKEN.sub(r"\1REDACTED", text)


def linked_instagram(page: dict) -> dict | None:
    """The professional Instagram account linked to a Facebook Page, if the Page says so."""
    account = page.get("instagram_business_account")
    if not isinstance(account, dict) or not account.get("id"):
        return None
    return {
        "id": str(account["id"]),
        "username": str(account.get("username") or ""),
        "name": str(account.get("name") or ""),
    }


def lookup_instagram(page_id: str, token: str) -> dict | None:
    payload = _get(
        f"{GRAPH}/{page_id}",
        token,
        {"fields": "instagram_business_account{id,username,name}"},
    )
    return linked_instagram(payload)


def facebook_posts(payload: dict) -> list[dict]:
    return [_facebook_post(row) for row in payload.get("data") or [] if isinstance(row, dict) and row.get("id")]


def instagram_posts(payload: dict) -> list[dict]:
    return [_instagram_post(row) for row in payload.get("data") or [] if isinstance(row, dict) and row.get("id")]


def threads_posts(payload: dict) -> list[dict]:
    return [_threads_post(row) for row in payload.get("data") or [] if isinstance(row, dict) and row.get("id")]


def pull_platform(platform: str, external_id: str, token: str, *, limit: int = 50) -> list[dict]:
    if platform == "facebook":
        raw = _collect(f"{GRAPH}/{external_id}/posts", token, _facebook_query(), limit)
        return facebook_posts({"data": raw})
    if platform == "instagram":
        raw = _collect(f"{GRAPH}/{external_id}/media", token, _instagram_query(), limit)
        return instagram_posts({"data": raw})
    if platform == "threads":
        raw = _collect(f"{THREADS}/{external_id}/threads", token, _threads_query(), limit)
        return threads_posts({"data": raw})
    raise MetaError("Channels are facebook, instagram, and threads.")


def _facebook_query() -> dict[str, str]:
    return {
        "fields": "id,message,created_time,permalink_url,shares,reactions.summary(true),comments.summary(true)",
        "limit": "25",
    }


def _instagram_query() -> dict[str, str]:
    return {
        "fields": "id,caption,timestamp,permalink,like_count,comments_count,media_type",
        "limit": "25",
    }


def _threads_query() -> dict[str, str]:
    return {"fields": "id,text,timestamp,permalink", "limit": "25"}


def _collect(url: str, token: str, params: dict[str, str], limit: int) -> list[dict]:
    rows: list[dict] = []
    payload = _get(url, token, params)
    for _ in range(4):
        rows.extend(item for item in payload.get("data") or [] if isinstance(item, dict))
        if len(rows) >= limit:
            return rows[:limit]
        nxt = str((payload.get("paging") or {}).get("next") or "")
        if not nxt:
            return rows
        payload = _get(nxt, token, None)
    return rows[:limit]


def _get(url: str, token: str, params: dict[str, str] | None) -> dict:
    if params is None:
        target = url
    else:
        query = dict(params)
        query["access_token"] = token
        target = f"{url}?{urlencode(query)}"
    request = Request(target, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = redact(exc.read().decode("utf-8", errors="replace")[:240])
        raise MetaError(f"Meta returned {exc.code}. {detail}") from None
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise MetaError(redact(str(exc))) from None
    if not isinstance(body, dict):
        raise MetaError("Meta did not return a page of posts.")
    if body.get("error"):
        raise MetaError(redact(str(body.get("error"))))
    return body


def _facebook_post(row: dict) -> dict:
    reactions = _summary(row.get("reactions"))
    comments = _summary(row.get("comments"))
    shares = _count(row.get("shares"))
    published = _iso(str(row.get("created_time") or ""))
    return _post(
        row,
        platform="facebook",
        preview=row.get("message"),
        published=published,
        reactions=reactions,
        comments=comments,
        shares=shares,
        permalink=row.get("permalink_url"),
        fmt="unknown",
    )


def _instagram_post(row: dict) -> dict:
    published = _iso(str(row.get("timestamp") or ""))
    likes = _count(row.get("like_count"))
    comments = _count(row.get("comments_count"))
    return _post(
        row,
        platform="instagram",
        preview=row.get("caption"),
        published=published,
        reactions=likes,
        comments=comments,
        shares=0,
        permalink=row.get("permalink"),
        fmt=_FORMATS.get(str(row.get("media_type") or ""), "unknown"),
    )


def _threads_post(row: dict) -> dict:
    published = _iso(str(row.get("timestamp") or ""))
    return _post(
        row,
        platform="threads",
        preview=row.get("text"),
        published=published,
        reactions=0,
        comments=0,
        shares=0,
        permalink=row.get("permalink"),
        fmt="thread",
    )


def _post(row, *, platform, preview, published, reactions, comments, shares, permalink, fmt) -> dict:
    return {
        "id": str(row.get("id")),
        "platform": platform,
        "preview": " ".join(str(preview or "").split())[:140],
        "published_at": published,
        "local_hour": _local_hour(published),
        "reactions": reactions,
        "comments": comments,
        "shares": shares,
        "engagements": reactions + comments + shares,
        "impressions": 0,
        "permalink": str(permalink or ""),
        "format": fmt,
        "source": "pulled",
    }


def _summary(value: object) -> int:
    if isinstance(value, dict):
        summary = value.get("summary")
        if isinstance(summary, dict):
            return _count(summary.get("total_count"))
    return 0


def _count(value: object) -> int:
    if isinstance(value, dict):
        return _count(value.get("count"))
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def _iso(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    matched = _OFFSET.search(text)
    if matched and ":" not in text[-6:]:
        text = text[: matched.start()] + f"{matched.group(1)}{matched.group(2)}:{matched.group(3)}"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


def _local_hour(iso: str) -> int | None:
    if not iso:
        return None
    try:
        parsed = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(ZoneInfo("America/New_York")).hour


def gather_inbox(platform: str, external_id: str, token: str, post_ids: list[str], getter=None) -> dict:
    """A short read of comments, mentions, and messages. Failures stay as text."""
    fetch = getter or _get
    items: list[dict] = []
    errors: list[str] = []
    for post_id in [str(item) for item in post_ids if item][:8]:
        try:
            items.extend(_comments(platform, post_id, token, fetch))
        except MetaError as exc:
            errors.append(redact(f"{platform} comments: {exc}"))
            break
    try:
        items.extend(_mentions(platform, external_id, token, fetch))
    except MetaError as exc:
        errors.append(redact(f"{platform} mentions: {exc}"))
    if platform == "threads":
        errors.append("Threads messages are not in this snapshot.")
    else:
        try:
            items.extend(_direct_messages(platform, external_id, token, fetch))
        except MetaError as exc:
            errors.append(redact(f"{platform} messages: {exc}"))
    return {"items": items[:40], "errors": errors}


def _comments(platform: str, post_id: str, token: str, fetch) -> list[dict]:
    if platform == "facebook":
        payload = fetch(f"{GRAPH}/{post_id}/comments", token, {"fields": "id,message,created_time,permalink_url", "limit": "5"})
        return [_item(row, platform=platform, kind="comment", text=row.get("message"), when=row.get("created_time"), link=row.get("permalink_url"), post_id=post_id) for row in _rows(payload)]
    if platform == "instagram":
        payload = fetch(f"{GRAPH}/{post_id}/comments", token, {"fields": "id,text,timestamp,username", "limit": "5"})
        return [_item(row, platform=platform, kind="comment", text=row.get("text"), when=row.get("timestamp"), author=row.get("username"), post_id=post_id) for row in _rows(payload)]
    if platform == "threads":
        payload = fetch(f"{THREADS}/{post_id}/replies", token, {"fields": "id,text,timestamp,username,permalink", "limit": "5"})
        return [_item(row, platform=platform, kind="comment", text=row.get("text"), when=row.get("timestamp"), author=row.get("username"), link=row.get("permalink"), post_id=post_id) for row in _rows(payload)]
    raise MetaError("Channels are facebook, instagram, and threads.")


def _mentions(platform: str, external_id: str, token: str, fetch) -> list[dict]:
    if platform == "facebook":
        payload = fetch(f"{GRAPH}/{external_id}/tagged", token, {"fields": "id,message,created_time,permalink_url", "limit": "5"})
        return [_item(row, platform=platform, kind="mention", text=row.get("message"), when=row.get("created_time"), link=row.get("permalink_url")) for row in _rows(payload)]
    if platform == "instagram":
        payload = fetch(f"{GRAPH}/{external_id}/tags", token, {"fields": "id,caption,timestamp,permalink,username", "limit": "5"})
        return [_item(row, platform=platform, kind="mention", text=row.get("caption"), when=row.get("timestamp"), author=row.get("username"), link=row.get("permalink")) for row in _rows(payload)]
    payload = fetch(f"{THREADS}/{external_id}/replies", token, {"fields": "id,text,timestamp,username,permalink", "limit": "5"})
    return [_item(row, platform=platform, kind="mention", text=row.get("text"), when=row.get("timestamp"), author=row.get("username"), link=row.get("permalink")) for row in _rows(payload)]


def _direct_messages(platform: str, external_id: str, token: str, fetch) -> list[dict]:
    params = {"fields": "id,messages.limit(1){id,message,created_time}", "limit": "5"}
    if platform == "instagram":
        params["platform"] = "instagram"
    payload = fetch(f"{GRAPH}/{external_id}/conversations", token, params)
    rows = []
    for conversation in _rows(payload):
        messages = ((conversation.get("messages") or {}).get("data") or []) if isinstance(conversation.get("messages"), dict) else []
        message = messages[0] if messages and isinstance(messages[0], dict) else {}
        if not message and not conversation.get("id"):
            continue
        rows.append(_item(
            message or conversation,
            platform=platform,
            kind="dm",
            text=message.get("message") or conversation.get("snippet"),
            when=message.get("created_time") or conversation.get("updated_time"),
            item_id=str(message.get("id") or conversation.get("id")),
        ))
    return rows


def _rows(payload: dict) -> list[dict]:
    return [row for row in payload.get("data") or [] if isinstance(row, dict) and (row.get("id") or row.get("message"))]


def _item(row: dict, *, platform: str, kind: str, text, when, author=None, link=None, item_id: str = "", post_id: str = "") -> dict:
    identity = item_id or str(row.get("id") or "")
    who = author or ""
    if not who and isinstance(row.get("from"), dict):
        who = str(row["from"].get("name") or "")
    return {
        "id": f"{platform}:{kind}:{identity}",
        "kind": kind,
        "platform": platform,
        "author": str(who or "Someone")[:80],
            "text": redact(str(text or ""))[:500],
        "at": _iso(str(when or "")),
        "permalink": str(link or "")[:300],
        "post_id": str(post_id or "")[:80],
    }
