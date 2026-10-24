"""Connect a brand to its Facebook Page, Instagram account, and Threads account.

The house Meta app and the house Threads app sign a person in. The sign-in
comes back to the dashboard with a code. Here the code becomes tokens, the
person picks which Page and which accounts belong to the brand, and only the
chosen tokens are written to the vault. Tokens wait in memory while the person
picks; they never touch state.json. The sign-in asks to read and to post;
posting itself happens in publish.py, only when it is switched on.
"""

from __future__ import annotations

import json
import re
import secrets
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from adapt import DraftError
from meta import GRAPH, THREADS
from store import _HOUSE_APPS, _copy, _public_connection, _read_vault, _write_vault, resolve_brand, roster, save

FACEBOOK_DIALOG = "https://www.facebook.com/v25.0/dialog/oauth"
THREADS_DIALOG = "https://threads.com/oauth/authorize"
THREADS_TOKEN = "https://graph.threads.net/oauth/access_token"
THREADS_LONG_TOKEN = "https://graph.threads.net/access_token"

# Reading, plus posting. Posting stays off until House settings and the brand turn it on.
META_SCOPES = (
    "pages_show_list",
    "pages_read_engagement",
    "pages_read_user_content",
    "pages_manage_posts",
    "read_insights",
    "pages_messaging",
    "business_management",
    "instagram_basic",
    "instagram_content_publish",
    "instagram_manage_insights",
    "instagram_manage_comments",
    "instagram_manage_messages",
)
THREADS_SCOPES = (
    "threads_basic",
    "threads_content_publish",
    "threads_delete",
    "threads_read_replies",
    "threads_manage_insights",
)

PROVIDERS = {"meta": "Meta", "threads": "Threads"}
PENDING_SECONDS = 30 * 60
CHOICE_SECONDS = 20 * 60

_SECRET_PARAMS = re.compile(r"((?:access_token|client_secret|code|fb_exchange_token)=)[^&\s\"']+", re.I)
_CHOICES: dict[str, dict] = {}
_LOCK = threading.Lock()


def start_connect(state: dict, brand_id: str, provider: str, redirect_uri: str, path: Path | None = None, clock=None) -> dict:
    """The sign-in address for one brand and one provider."""
    brand = resolve_brand(state, brand_id)
    kind = _provider(provider)
    app_id = _app_id(state, kind)
    target = _redirect(redirect_uri)
    now = int((clock or time.time)())
    nonce = secrets.token_urlsafe(24)
    updated = _copy(state)
    kept = [item for item in _pending(updated) if now - int(item.get("at") or 0) < PENDING_SECONDS][-9:]
    updated["oauth_pending"] = [
        *kept,
        {"state": nonce, "brand_id": brand.id, "provider": kind, "redirect_uri": target, "at": now},
    ]
    save(updated, path)
    if kind == "meta":
        query = {
            "client_id": app_id,
            "redirect_uri": target,
            "state": nonce,
            "response_type": "code",
            "scope": ",".join(META_SCOPES),
        }
        url = f"{FACEBOOK_DIALOG}?{urlencode(query)}"
    else:
        query = {
            "client_id": app_id,
            "redirect_uri": target,
            "state": nonce,
            "response_type": "code",
            "scope": ",".join(THREADS_SCOPES),
        }
        url = f"{THREADS_DIALOG}?{urlencode(query)}"
    return {"url": url, "brand_id": brand.id, "provider": kind, "redirect_uri": target, "sending": False}


def finish_connect(
    state: dict,
    nonce: str,
    code: str,
    path: Path | None = None,
    reader=None,
    http=None,
    clock=None,
) -> dict:
    """Trade the code for tokens and list what the person may pick. Saves no token."""
    now = int((clock or time.time)())
    pending = next((item for item in _pending(state) if item.get("state") == str(nonce or "")), None)
    if not pending:
        raise DraftError("That sign-in is unknown or was already used. Press Connect again.")
    updated = _copy(state)
    updated["oauth_pending"] = [item for item in _pending(updated) if item.get("state") != pending["state"]]
    save(updated, path)
    if now - int(pending.get("at") or 0) >= PENDING_SECONDS:
        raise DraftError("That sign-in took longer than 30 minutes. Press Connect again.")
    code = str(code or "").strip()
    if not code or len(code) > 2000:
        raise DraftError("The sign-in came back without a code. Press Connect again.")
    kind = _provider(pending.get("provider"))
    brand = resolve_brand(updated, str(pending.get("brand_id") or ""))
    app_id = _app_id(updated, kind)
    secret = (reader or _read_vault)(_HOUSE_APPS[kind])
    if not secret:
        raise DraftError(f"The {PROVIDERS[kind]} app secret is not in the vault. Save it again under House settings.")
    call = http or _call
    redirect_uri = str(pending.get("redirect_uri") or "")
    if kind == "meta":
        found = _meta_accounts(call, app_id, secret, redirect_uri, code)
    else:
        found = _threads_account(call, app_id, secret, redirect_uri, code, now)
    choice_id = secrets.token_urlsafe(18)
    with _LOCK:
        for key in [key for key, item in _CHOICES.items() if now - item["at"] >= CHOICE_SECONDS]:
            _CHOICES.pop(key, None)
        _CHOICES[choice_id] = {"brand_id": brand.id, "provider": kind, "at": now, **found}
    return _choice_view(choice_id, _CHOICES[choice_id], updated, brand.id)


def read_choice(state: dict, choice_id: str, clock=None) -> dict:
    """The picker again, for a page that was reloaded before the person chose."""
    choice = _choice(choice_id, clock)
    return _choice_view(choice_id, choice, state, choice["brand_id"])


def choose_accounts(
    state: dict,
    choice_id: str,
    spec: dict,
    path: Path | None = None,
    vault_write=None,
    clock=None,
) -> dict:
    """Save the Page and accounts the person picked. Their tokens go to the vault."""
    choice = _choice(choice_id, clock)
    spec = spec if isinstance(spec, dict) else {}
    brand = resolve_brand(state, choice["brand_id"])
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    picked: list[tuple[dict, str, dict]] = []
    if choice["provider"] == "meta":
        pages = {page["id"]: page for page in choice.get("pages") or []}
        page_id = str(spec.get("page_id") or "").strip()
        instagram_id = str(spec.get("instagram_id") or "").strip()
        if not page_id and not instagram_id:
            raise DraftError("Pick a Facebook Page, an Instagram account, or both.")
        if page_id:
            page = pages.get(page_id)
            if not page:
                raise DraftError("That Page was not in this sign-in. Press Connect again.")
            picked.append((
                {
                    "platform": "facebook",
                    "external_id": page["id"],
                    "name": page["name"],
                    "username": page.get("username") or "",
                },
                page["token"],
                {"handle": page.get("username") or "", "external_id": page["id"]},
            ))
        if instagram_id:
            owner = next((page for page in pages.values() if (page.get("instagram") or {}).get("id") == instagram_id), None)
            if not owner:
                raise DraftError("That Instagram account was not in this sign-in. Press Connect again.")
            account = owner["instagram"]
            picked.append((
                {
                    "platform": "instagram",
                    "external_id": account["id"],
                    "name": account.get("name") or "",
                    "username": account.get("username") or "",
                    "page_id": owner["id"],
                },
                owner["token"],
                {"handle": account.get("username") or "", "external_id": account["id"]},
            ))
    else:
        account = choice.get("threads") or {}
        if not account.get("id"):
            raise DraftError("Threads did not name an account. Press Connect again.")
        picked.append((
            {
                "platform": "threads",
                "external_id": account["id"],
                "name": account.get("name") or "",
                "username": account.get("username") or "",
                "expires_at": choice.get("expires_at") or "",
            },
            choice["token"],
            {"handle": account.get("username") or "", "external_id": account["id"]},
        ))
    writer = vault_write or _write_vault
    for row, token, _channel in picked:
        if not writer(_vault_name(brand.id, row["platform"]), token):
            raise DraftError("A token did not reach the vault. Nothing was saved.")
    updated = _copy(state)
    platforms = {row["platform"] for row, _token, _channel in picked}

    def replaced(item: dict) -> bool:
        if item.get("brand_id") != brand.id:
            return False
        if item.get("platform") in platforms:
            return True
        # An Instagram account the old Page named read with the old Page token.
        return "facebook" in platforms and item.get("platform") == "instagram" and item.get("via") == "facebook"

    kept = [item for item in updated.get("connections") or [] if not replaced(item)]
    app_id = _app_id(updated, choice["provider"])
    fresh = []
    for row, _token, _channel in picked:
        fresh.append({
            "id": f"{brand.id}:{row['platform']}",
            "brand_id": brand.id,
            "app_id": app_id,
            "token_vault": f"vault:{_vault_name(brand.id, row['platform'])}",
            "via": "login",
            "connected_at": stamp,
            **({"scopes": list(choice["scopes"])} if isinstance(choice.get("scopes"), list) else {}),
            **{key: value for key, value in row.items() if value},
        })
    updated["connections"] = [*kept, *fresh]
    channels = dict((updated.get("channels") or {}).get(brand.id) or {})
    current = {item["platform"]: item for item in _brand_channels(updated, brand.id)}
    for row, _token, channel in picked:
        before = current.get(row["platform"]) or {}
        handle = channel["handle"] or str(before.get("handle") or "")
        channels[row["platform"]] = {"handle": handle[:80], "external_id": channel["external_id"][:40], "known": True}
    updated.setdefault("channels", {})[brand.id] = channels
    save(updated, path)
    with _LOCK:
        _CHOICES.pop(choice_id, None)
    return {
        "brand_id": brand.id,
        "connections": [_public_connection(item) for item in fresh],
        "sending": False,
    }


def cancel_choice(choice_id: str) -> dict:
    with _LOCK:
        _CHOICES.pop(str(choice_id or ""), None)
    return {"cancelled": True}


def disconnect(state: dict, brand_id: str, platform: str, path: Path | None = None) -> dict:
    """Forget one connection. The vault entry stays until it is removed there."""
    brand = resolve_brand(state, brand_id)
    if platform not in {"facebook", "instagram", "threads"}:
        raise DraftError("Channels are facebook, instagram, and threads.")
    updated = _copy(state)
    before = len(updated.get("connections") or [])

    def gone(item: dict) -> bool:
        if item.get("brand_id") != brand.id:
            return False
        if item.get("platform") == platform:
            return True
        # An Instagram account found through the Page reads with the Page token.
        return platform == "facebook" and item.get("platform") == "instagram" and item.get("via") == "facebook"

    found_on_page = any(
        gone(item) and item.get("platform") == "instagram" and item.get("via") == "facebook"
        for item in updated.get("connections") or []
    )
    updated["connections"] = [item for item in updated.get("connections") or [] if not gone(item)]
    if len(updated["connections"]) == before:
        raise DraftError("That account is not connected.")
    if platform == "instagram" and found_on_page:
        # Otherwise the next pull would find it on the Page again.
        for item in updated["connections"]:
            if item.get("brand_id") == brand.id and item.get("platform") == "facebook":
                item["skip_instagram"] = True
    save(updated, path)
    return {"brand_id": brand.id, "platform": platform, "vault": f"vault:{_vault_name(brand.id, platform)}"}


def _meta_accounts(call, app_id: str, secret: str, redirect_uri: str, code: str) -> dict:
    short = call("GET", f"{GRAPH}/oauth/access_token", {
        "client_id": app_id,
        "client_secret": secret,
        "redirect_uri": redirect_uri,
        "code": code,
    })
    user_token = str(short.get("access_token") or "")
    if not user_token:
        raise DraftError("Facebook did not return a token for that sign-in. Press Connect again.")
    # A Page token read with a long-lived user token does not expire.
    long = call("GET", f"{GRAPH}/oauth/access_token", {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": secret,
        "fb_exchange_token": user_token,
    })
    user_token = str(long.get("access_token") or "")
    if not user_token:
        raise DraftError("Facebook did not return a long-lived token. Press Connect again.")
    granted = _granted(call, user_token)
    payload = call("GET", f"{GRAPH}/me/accounts", {
        "fields": "id,name,username,category,access_token,instagram_business_account{id,username,name}",
        "limit": "100",
        "access_token": user_token,
    })
    pages: list[dict] = []
    for _ in range(5):
        for row in payload.get("data") or []:
            if not isinstance(row, dict) or not row.get("id") or not row.get("access_token"):
                continue
            account = row.get("instagram_business_account")
            instagram = None
            if isinstance(account, dict) and account.get("id"):
                instagram = {
                    "id": str(account["id"]),
                    "username": str(account.get("username") or "")[:80],
                    "name": str(account.get("name") or "")[:120],
                }
            pages.append({
                "id": str(row["id"]),
                "name": str(row.get("name") or row["id"])[:120],
                "username": str(row.get("username") or "")[:80],
                "category": str(row.get("category") or "")[:80],
                "token": str(row["access_token"]),
                "instagram": instagram,
            })
        nxt = str((payload.get("paging") or {}).get("next") or "")
        if not nxt:
            break
        payload = call("GET", nxt, None)
    if not pages:
        raise DraftError(
            "Facebook returned no Pages. In the sign-in window, choose this brand's Page when Facebook asks which Pages to share, "
            "and sign in as someone who manages it."
        )
    return {"pages": pages, "scopes": granted}


def _granted(call, user_token: str) -> list[str] | None:
    """The permissions the person actually allowed. They can untick some."""
    try:
        body = call("GET", f"{GRAPH}/me/permissions", {"access_token": user_token})
    except DraftError:
        return None
    rows = body.get("data") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        return None
    return sorted(str(row.get("permission")) for row in rows if isinstance(row, dict) and row.get("status") == "granted")


def _threads_account(call, app_id: str, secret: str, redirect_uri: str, code: str, now: int) -> dict:
    short = call("POST", THREADS_TOKEN, {
        "client_id": app_id,
        "client_secret": secret,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
        "code": code,
    })
    token = str(short.get("access_token") or "")
    if not token:
        raise DraftError("Threads did not return a token for that sign-in. Press Connect again.")
    long = call("GET", THREADS_LONG_TOKEN, {
        "grant_type": "th_exchange_token",
        "client_secret": secret,
        "access_token": token,
    })
    token = str(long.get("access_token") or "")
    if not token:
        raise DraftError("Threads did not return a long-lived token. Press Connect again.")
    seconds = _seconds(long.get("expires_in"))
    me = call("GET", f"{THREADS}/me", {"fields": "id,username,name", "access_token": token})
    if not me.get("id"):
        raise DraftError("Threads did not name the account. Press Connect again.")
    expires_at = ""
    if seconds:
        expires_at = datetime.fromtimestamp(now + seconds, timezone.utc).isoformat(timespec="seconds")
    return {
        "token": token,
        "expires_at": expires_at,
        "scopes": list(THREADS_SCOPES),
        "threads": {
            "id": str(me["id"]),
            "username": str(me.get("username") or "")[:80],
            "name": str(me.get("name") or "")[:120],
        },
    }


def _choice_view(choice_id: str, choice: dict, state: dict, brand_id: str) -> dict:
    row = next((item for item in roster(state) if item["id"] == brand_id), {"name": brand_id, "channels": []})
    name = row["name"]
    channels = {item["platform"]: item for item in row.get("channels") or []}

    def likely(platform: str, account_id: str, *names: str) -> bool:
        # The id or handle already on the brand, or a Page named like the brand.
        channel = channels.get(platform) or {}
        if channel.get("external_id") and channel["external_id"] == account_id:
            return True
        wanted = {_plain(channel.get("handle")), _plain(name)} - {""}
        return any(_plain(item) in wanted for item in names if _plain(item))

    connected = {
        item.get("platform"): item.get("external_id")
        for item in state.get("connections") or []
        if item.get("brand_id") == brand_id
    }
    view: dict = {
        "choice": choice_id,
        "brand_id": brand_id,
        "brand_name": name,
        "provider": choice["provider"],
        "sending": False,
    }
    if choice["provider"] == "meta":
        pages = choice.get("pages") or []
        view["pages"] = [
            {key: page.get(key) for key in ("id", "name", "username", "category")}
            | {
                "instagram_id": (page.get("instagram") or {}).get("id") or "",
                "current": connected.get("facebook") == page["id"],
                "likely": likely("facebook", page["id"], page.get("name") or "", page.get("username") or ""),
            }
            for page in pages
        ]
        view["instagram"] = [
            {
                "id": page["instagram"]["id"],
                "username": page["instagram"].get("username") or "",
                "name": page["instagram"].get("name") or "",
                "page_id": page["id"],
                "page_name": page["name"],
                "current": connected.get("instagram") == page["instagram"]["id"],
                "likely": likely("instagram", page["instagram"]["id"], page["instagram"].get("username") or ""),
            }
            for page in pages
            if page.get("instagram")
        ]
    else:
        account = choice.get("threads") or {}
        view["threads"] = {
            "id": account.get("id") or "",
            "username": account.get("username") or "",
            "name": account.get("name") or "",
            "current": connected.get("threads") == account.get("id"),
        }
        view["expires_at"] = choice.get("expires_at") or ""
    return view


def _choice(choice_id: str, clock=None) -> dict:
    now = int((clock or time.time)())
    with _LOCK:
        choice = _CHOICES.get(str(choice_id or ""))
        if choice and now - choice["at"] >= CHOICE_SECONDS:
            _CHOICES.pop(str(choice_id), None)
            choice = None
    if not choice:
        raise DraftError("That choice expired or was already saved. Press Connect again.")
    return choice


def _brand_channels(state: dict, brand_id: str) -> list[dict]:
    return next((row["channels"] for row in roster(state) if row["id"] == brand_id), [])


def _plain(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _pending(state: dict) -> list[dict]:
    return [item for item in state.get("oauth_pending") or [] if isinstance(item, dict)]


def _provider(value: object) -> str:
    kind = str(value or "").strip()
    if kind not in PROVIDERS:
        raise DraftError("Connect uses the Meta app or the Threads app.")
    return kind


def _app_id(state: dict, kind: str) -> str:
    row = (state.get("apps") or {}).get(kind)
    row = row if isinstance(row, dict) else {}
    name = PROVIDERS[kind]
    if not str(row.get("app_id") or "").strip():
        raise DraftError(f"Add the house {name} app id under House settings first.")
    if not row.get("secret_vault"):
        raise DraftError(f"Save the house {name} app secret under House settings first.")
    return str(row["app_id"]).strip()


def _redirect(value: object) -> str:
    text = str(value or "").strip()
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or len(text) > 300:
        raise DraftError("The sign-in needs the dashboard's own address to come back to.")
    return text.split("#", 1)[0].split("?", 1)[0]


def _vault_name(brand_id: str, platform: str) -> str:
    return f"house-social.{brand_id}.{platform}.token"


def _seconds(value: object) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def scrub(text: str) -> str:
    return _SECRET_PARAMS.sub(r"\1REDACTED", str(text))


def _call(method: str, url: str, params: dict | None) -> dict:
    data = None
    target = url
    if params is not None and method == "GET":
        target = f"{url}?{urlencode(params)}"
    elif params is not None:
        data = urlencode(params).encode("utf-8")
    request = Request(target, data=data, method=method, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise DraftError(_said(exc.read().decode("utf-8", errors="replace"), exc.code)) from None
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise DraftError(f"Meta could not be reached. {scrub(str(exc))[:200]}") from None
    if not isinstance(body, dict):
        raise DraftError("Meta did not answer the sign-in.")
    if body.get("error"):
        raise DraftError(_said(json.dumps(body), 400))
    return body


def _said(raw: str, status: int) -> str:
    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        body = {}
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        detail = error.get("error_user_msg") or error.get("message") or ""
    else:
        detail = (body.get("error_message") if isinstance(body, dict) else "") or error or raw
    return f"Meta said ({status}): {scrub(str(detail))[:240]}"
