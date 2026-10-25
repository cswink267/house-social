"""Post pieces to Facebook, Instagram, and Threads.

Posting is off until House settings turns it on, and each brand turns it
on for itself. A scheduled piece posts when its time comes, if it was
approved (by a person, or by the brand's fully autonomous mode), it is not
the desk's placeholder, it passes the brand rules, and the brand is not
paused. A piece that missed its time by more than six hours does not post
late; it waits for a new time.

Tokens are read from the vault for each run and are never written to state.
"""

from __future__ import annotations

import contextlib
import json
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from adapt import DraftError, issues
from brands import PLATFORMS
from meta import GRAPH, THREADS
from store import _HOUSE_APPS, _copy, _read_vault, load, resolve_brand, save, state_path

LATE_HOURS = 6
CLAIM_SECONDS = 15 * 60
WORKER_SECONDS = 60
POST_SCOPES = {
    "facebook": "pages_manage_posts",
    "instagram": "instagram_content_publish",
    "threads": "threads_content_publish",
}
NAMES = {"facebook": "Facebook", "instagram": "Instagram", "threads": "Threads"}

_LOCK = threading.Lock()
_WORKER: dict = {"started": False, "last_tick": "", "last": None, "error": ""}


class PostError(Exception):
    """One platform did not take the post. The message never carries a token."""


# ---- Switches --------------------------------------------------------------


def posting_view(state: dict, brand_id: str = "") -> dict:
    book = _book(state)
    view: dict = {
        "on": bool(book.get("on")),
        "worker": {key: _WORKER.get(key) for key in ("started", "last_tick", "last", "error")},
        "late_hours": LATE_HOURS,
        "due_soon": worker_due_soon(state),
    }
    if brand_id:
        brand = resolve_brand(state, brand_id)
        view["brand_on"] = bool((book.get("brands") or {}).get(brand.id))
        view["live"] = view["on"] and view["brand_on"]
        view["accounts"] = {
            item.get("platform"): _account(item)
            for item in state.get("connections") or []
            if item.get("brand_id") == brand.id
        }
        view["tests"] = [
            _public_test(item) for item in state.get("test_posts") or [] if item.get("brand_id") == brand.id
        ][:10]
    return view


def set_posting(state: dict, spec: dict, path: Path | None = None) -> dict:
    """House switch with {"on": bool}; one brand with {"brand_id", "on"}."""
    if not isinstance(spec, dict) or "on" not in spec:
        raise DraftError("Say on or off.")
    updated = _copy(state)
    book = _book(updated)
    on = bool(spec.get("on"))
    brand_id = str(spec.get("brand_id") or "").strip()
    if brand_id:
        brand = resolve_brand(updated, brand_id)
        brands = dict(book.get("brands") or {})
        brands[brand.id] = on
        book["brands"] = brands
    else:
        book["on"] = on
    updated["publishing"] = book
    save(updated, path)
    return posting_view(updated, brand_id)


def is_live(state: dict, brand_id: str) -> bool:
    book = _book(state)
    return bool(book.get("on")) and bool((book.get("brands") or {}).get(brand_id))


# ---- What may post ---------------------------------------------------------


def blockers(state: dict, piece: dict, now: datetime | None = None, *, immediate: bool = False) -> list[str]:
    """Reasons this piece cannot post now. Empty means it may."""
    from support import assert_running

    found: list[str] = []
    brand = resolve_brand(state, str(piece.get("brand_id") or ""))
    book = _book(state)
    if not book.get("on"):
        found.append("Posting is off in House settings.")
    if not (book.get("brands") or {}).get(brand.id):
        found.append("Posting is off for this brand. Turn it on under Accounts.")
    try:
        assert_running(state, brand.id)
    except DraftError as exc:
        found.append(str(exc))
    if not (piece.get("approval") or {}).get("complete"):
        found.append("It needs approval first.")
    if piece.get("placeholder"):
        found.append("It is still the desk's placeholder. Write the post first.")
    status = piece.get("status") or "draft"
    if immediate:
        if status not in {"approved", "scheduled", "failed"}:
            found.append("Only an approved, scheduled, or failed piece can post now.")
    elif status != "scheduled":
        found.append("It is not scheduled.")
    elif not _due(piece, now):
        found.append("Its time has not come.")
    found.extend(issues(brand, piece.get("variants") or {}))
    if not _targets(state, piece):
        found.append("No connected account has words to post for this piece.")
    return found


def run_due(
    state: dict,
    path: Path | None = None,
    *,
    reader=None,
    http=None,
    now: datetime | None = None,
    sleep=None,
    root: Path | None = None,
) -> dict:
    """Post every scheduled piece whose time has come. Returns what happened."""
    moment = now or datetime.now(timezone.utc)
    result = {"at": moment.isoformat(timespec="seconds"), "posted": [], "failed": [], "late": [], "waiting": []}
    if not _book(state).get("on"):
        return result
    for piece in list(state.get("pieces") or []):
        if piece.get("status") != "scheduled" or not _due(piece, moment):
            continue
        if not is_live(state, str(piece.get("brand_id") or "")):
            continue
        hours = _late_hours(piece, moment)
        if hours > LATE_HOURS and not piece.get("published"):
            state = _mark_late(load(path) if path else load(), piece["id"], hours, path)
            result["late"].append(piece["id"])
            continue
        reasons = blockers(state, piece, moment)
        if reasons:
            result["waiting"].append({"id": piece["id"], "reasons": reasons})
            continue
        try:
            done = publish_piece(state, piece["id"], path, reader=reader, http=http, now=moment, sleep=sleep, root=root)
        except DraftError as exc:
            result["failed"].append({"id": piece["id"], "error": str(exc)})
            from todo_notes import note_failure

            note_failure(load(path) if path else state, str(piece.get("brand_id") or ""), str(piece.get("id") or ""), "", str(exc), "Publish", path)
            state = load(path) if path else load()
            continue
        (result["posted"] if done["status"] == "published" else result["failed"]).append(
            {"id": piece["id"], "error": done.get("failure") or ""}
        )
        state = load(path) if path else load()
    return result


def publish_piece(
    state: dict,
    piece_id: str,
    path: Path | None = None,
    *,
    reader=None,
    http=None,
    now: datetime | None = None,
    sleep=None,
    root: Path | None = None,
    immediate: bool = False,
) -> dict:
    """Post one piece to every connected platform that has words for it."""
    moment = now or datetime.now(timezone.utc)
    claimed = _claim(state, piece_id, moment, path, immediate)
    piece = next(item for item in claimed["pieces"] if item.get("id") == piece_id)
    brand = resolve_brand(claimed, piece["brand_id"])
    call = http or _call
    read = reader or _read_vault
    targets = _targets(claimed, piece)
    done: dict[str, dict] = {}
    errors: dict[str, str] = {}
    skipped: dict[str, str] = {}
    try:
        media = _media(claimed, piece, root)
        if media and media.get("unsupported"):
            raise PostError(f"{media['unsupported'].capitalize()} posts are not posted by the desk yet. Attach one image, or post it by hand.")
        tokens = {}
        for platform, connection in targets.items():
            token = read(_vault_name(connection))
            if not token:
                errors[platform] = f"No token in vault:{_vault_name(connection)}. Connect the account again."
            else:
                tokens[platform] = token
        facebook = _connection(claimed, brand.id, "facebook")
        image_url = (media or {}).get("url") or ""
        if "facebook" in tokens:
            try:
                done["facebook"] = _post_facebook(call, targets["facebook"], tokens["facebook"], _text(piece, "facebook"), media)
                if media and not image_url and done["facebook"].get("photo_id"):
                    image_url = _photo_url(call, done["facebook"]["photo_id"], tokens["facebook"])
            except PostError as exc:
                errors["facebook"] = str(exc)
        wants_url = media and not image_url and any(platform in tokens for platform in ("instagram", "threads"))
        if wants_url:
            image_url = _host_image(call, facebook, read, media)
        if "instagram" in tokens:
            if not media:
                skipped["instagram"] = "Instagram needs an image, so it was skipped."
            elif not image_url:
                errors["instagram"] = "Instagram needs the image at a public address. Connect the Facebook Page so the desk can host it there."
            else:
                try:
                    done["instagram"] = _post_instagram(call, targets["instagram"], tokens["instagram"], _text(piece, "instagram"), image_url, sleep)
                except PostError as exc:
                    errors["instagram"] = str(exc)
        if "threads" in tokens:
            if media and not image_url:
                errors["threads"] = "Threads needs the image at a public address. Connect the Facebook Page so the desk can host it there."
            else:
                try:
                    done["threads"] = _post_threads(call, targets["threads"], tokens["threads"], _text(piece, "threads"), image_url, sleep)
                except PostError as exc:
                    errors["threads"] = str(exc)
    except PostError as exc:
        for platform in targets:
            if platform not in done:
                errors.setdefault(platform, str(exc))
    except Exception as exc:  # record what posted so a retry never posts it twice
        for platform in targets:
            if platform not in done:
                errors.setdefault(platform, f"The desk hit an error: {str(exc)[:200]}")
    return _settle(path, piece_id, moment, done, errors, skipped)


# ---- Check and test --------------------------------------------------------


def check_posting(state: dict, brand_id: str, path: Path | None = None, *, reader=None, http=None) -> dict:
    """Prove each connected account can post, without leaving anything visible."""
    brand = resolve_brand(state, brand_id)
    call = http or _call
    read = reader or _read_vault
    rows = []
    for platform in PLATFORMS:
        connection = _connection(state, brand.id, platform)
        if not connection:
            continue
        token = read(_vault_name(connection))
        if not token:
            rows.append({"platform": platform, "ok": False, "detail": f"No token in vault:{_vault_name(connection)}. Connect again."})
            continue
        try:
            detail = _check_one(call, state, read, platform, connection, token)
            rows.append({"platform": platform, "ok": True, "detail": detail})
        except PostError as exc:
            rows.append({"platform": platform, "ok": False, "detail": str(exc)})
    if not rows:
        raise DraftError("Connect an account under Accounts first.")
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    updated = _copy(state)
    for item in updated.get("connections") or []:
        if item.get("brand_id") != brand.id:
            continue
        row = next((entry for entry in rows if entry["platform"] == item.get("platform")), None)
        if row:
            item["checked"] = {"at": stamp, "ok": row["ok"], "detail": row["detail"][:300]}
    save(updated, path)
    return {"brand_id": brand.id, "rows": rows, "at": stamp}


def send_test_post(state: dict, brand_id: str, spec: dict, path: Path | None = None, *, reader=None, http=None, sleep=None) -> dict:
    """A real post, marked as a test, on the platforms chosen. It is public."""
    brand = resolve_brand(state, brand_id)
    spec = spec if isinstance(spec, dict) else {}
    chosen = [platform for platform in spec.get("platforms") or [] if platform in PLATFORMS]
    if not chosen:
        raise DraftError("Pick at least one platform for the test.")
    text = str(spec.get("text") or "").strip() or "Testing a post from House Social. This will be deleted."
    if len(text) > 500:
        raise DraftError("Keep the test under 500 characters, so Threads takes it too.")
    image_url = str(spec.get("image_url") or "").strip()
    if image_url and not image_url.startswith("https://"):
        raise DraftError("The image address must start with https://.")
    call = http or _call
    read = reader or _read_vault
    rows = []
    for platform in chosen:
        connection = _connection(state, brand.id, platform)
        if not connection:
            rows.append({"platform": platform, "ok": False, "detail": f"{NAMES[platform]} is not connected."})
            continue
        token = read(_vault_name(connection))
        if not token:
            rows.append({"platform": platform, "ok": False, "detail": "No token in the vault. Connect again."})
            continue
        try:
            if platform == "facebook":
                media = {"url": image_url} if image_url else None
                posted = _post_facebook(call, connection, token, text, media)
            elif platform == "instagram":
                if not image_url:
                    raise PostError("Instagram needs an image. Add a public https image address.")
                posted = _post_instagram(call, connection, token, text, image_url, sleep)
            else:
                posted = _post_threads(call, connection, token, text, image_url, sleep)
            rows.append({"platform": platform, "ok": True, "detail": "Posted.", **posted})
        except PostError as exc:
            rows.append({"platform": platform, "ok": False, "detail": str(exc)})
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    kept = [
        {
            "id": str(uuid.uuid4()),
            "brand_id": brand.id,
            "platform": row["platform"],
            "post_id": row.get("id") or "",
            "permalink": row.get("permalink") or "",
            "at": stamp,
            "deleted": False,
        }
        for row in rows
        if row["ok"]
    ]
    updated = _copy(state)
    updated["test_posts"] = [*kept, *(updated.get("test_posts") or [])][:40]
    save(updated, path)
    return {"brand_id": brand.id, "rows": rows, "tests": [_public_test(item) for item in kept]}


def delete_test(state: dict, test_id: str, path: Path | None = None, *, reader=None, http=None) -> dict:
    row = next((item for item in state.get("test_posts") or [] if item.get("id") == test_id), None)
    if not row:
        raise DraftError("That test post is not on the desk.")
    if row.get("deleted"):
        raise DraftError("That test post was already deleted.")
    platform = row["platform"]
    if platform == "instagram":
        raise DraftError("Instagram does not let an app delete a post. Delete it in the Instagram app.")
    connection = _connection(state, row["brand_id"], platform)
    token = (reader or _read_vault)(_vault_name(connection)) if connection else None
    if not token:
        raise DraftError(f"{NAMES[platform]} is not connected now, so the test cannot be deleted from here.")
    base = GRAPH if platform == "facebook" else THREADS
    try:
        (http or _call)("DELETE", f"{base}/{row['post_id']}", {"access_token": token})
    except PostError as exc:
        raise DraftError(f"{NAMES[platform]} did not delete it. {exc}") from None
    updated = _copy(state)
    for item in updated.get("test_posts") or []:
        if item.get("id") == test_id:
            item["deleted"] = True
    save(updated, path)
    return {"id": test_id, "deleted": True}


# ---- The worker ------------------------------------------------------------


def start_worker(interval: int = WORKER_SECONDS) -> bool:
    """Post due pieces once a minute from the dashboard process."""
    with _LOCK:
        if _WORKER["started"]:
            return False
        _WORKER["started"] = True
    thread = threading.Thread(target=_loop, args=(interval,), name="house-social-poster", daemon=True)
    thread.start()
    return True


def tick(path: Path | None = None) -> dict | None:
    """One pass, guarded so two processes never post the same minute twice."""
    with _file_lock(path) as held:
        if not held:
            return None
        state = load(path) if path else load()
        result = run_due(state, path)
        from approval_mail import poll_replies, send_waiting

        # Approvals by email can schedule a piece, so read them after posting.
        result["mail"] = poll_replies(load(path) if path else load(), path)
        result["mail"]["sent"] = send_waiting(load(path) if path else load(), path)
        from inbox_send import send_approved_replies

        result["replies"] = send_approved_replies(load(path) if path else load(), path)
        return result


def _loop(interval: int) -> None:
    while True:
        try:
            result = tick()
            _WORKER["last_tick"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            if result and (result["posted"] or result["failed"] or result["late"]):
                _WORKER["last"] = {key: result[key] for key in ("at", "posted", "failed", "late")}
            _WORKER["error"] = ""
        except Exception as exc:  # the loop must outlive one bad pass
            _WORKER["error"] = str(exc)[:300]
        time.sleep(interval)


@contextlib.contextmanager
def _file_lock(path: Path | None):
    target = (path or state_path()).with_suffix(".lock")
    try:
        import fcntl
    except ImportError:  # no flock here; the in-process lock still holds
        with _LOCK:
            yield True
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


# ---- Platforms -------------------------------------------------------------


def _post_facebook(call, connection: dict, token: str, text: str, media: dict | None) -> dict:
    page = connection["external_id"]
    if media:
        params = {"caption": text, "access_token": token}
        if media.get("url"):
            params["url"] = media["url"]
            body = call("POST", f"{GRAPH}/{page}/photos", params)
        else:
            body = call("POST", f"{GRAPH}/{page}/photos", params, files={"source": _file_part(media)})
        post_id = str(body.get("post_id") or body.get("id") or "")
        photo_id = str(body.get("id") or "")
    else:
        body = call("POST", f"{GRAPH}/{page}/feed", {"message": text, "access_token": token})
        post_id = str(body.get("id") or "")
        photo_id = ""
    if not post_id:
        raise PostError("Facebook did not return the post.")
    return {"id": post_id, "photo_id": photo_id, "permalink": _permalink(call, f"{GRAPH}/{post_id}", token, "permalink_url")}


def _post_instagram(call, connection: dict, token: str, caption: str, image_url: str, sleep=None) -> dict:
    account = connection["external_id"]
    container = call("POST", f"{GRAPH}/{account}/media", {"image_url": image_url, "caption": caption, "access_token": token})
    creation = str(container.get("id") or "")
    if not creation:
        raise PostError("Instagram did not take the image.")
    _wait(call, f"{GRAPH}/{creation}", token, "status_code", sleep)
    done = call("POST", f"{GRAPH}/{account}/media_publish", {"creation_id": creation, "access_token": token})
    media_id = str(done.get("id") or "")
    if not media_id:
        raise PostError("Instagram did not publish the post.")
    return {"id": media_id, "permalink": _permalink(call, f"{GRAPH}/{media_id}", token, "permalink")}


def _post_threads(call, connection: dict, token: str, text: str, image_url: str = "", sleep=None) -> dict:
    account = connection["external_id"]
    params = {"media_type": "IMAGE" if image_url else "TEXT", "text": text, "access_token": token}
    if image_url:
        params["image_url"] = image_url
    container = call("POST", f"{THREADS}/{account}/threads", params)
    creation = str(container.get("id") or "")
    if not creation:
        raise PostError("Threads did not take the post.")
    _wait(call, f"{THREADS}/{creation}", token, "status", sleep)
    done = call("POST", f"{THREADS}/{account}/threads_publish", {"creation_id": creation, "access_token": token})
    media_id = str(done.get("id") or "")
    if not media_id:
        raise PostError("Threads did not publish the post.")
    return {"id": media_id, "permalink": _permalink(call, f"{THREADS}/{media_id}", token, "permalink")}


def _check_one(call, state: dict, read, platform: str, connection: dict, token: str) -> str:
    if platform == "threads":
        body = call("GET", f"{THREADS}/{connection['external_id']}/threads_publishing_limit", {"fields": "quota_usage,config", "access_token": token})
        row = (body.get("data") or [{}])[0]
        used = row.get("quota_usage")
        total = (row.get("config") or {}).get("quota_total")
        return f"Ready to post. {used} of {total} posts used in the last 24 hours." if used is not None and total else "Ready to post."
    scopes = _scopes(call, state, read, token)
    needed = POST_SCOPES[platform]
    if scopes is not None and needed not in scopes:
        raise PostError(f"This sign-in did not allow posting ({needed}). Press Change and connect again.")
    if platform == "instagram":
        body = call("GET", f"{GRAPH}/{connection['external_id']}/content_publishing_limit", {"fields": "quota_usage,config", "access_token": token})
        row = (body.get("data") or [{}])[0]
        used = row.get("quota_usage")
        total = (row.get("config") or {}).get("quota_total")
        return f"Ready to post. {used} of {total} posts used in the last 24 hours." if used is not None and total else "Ready to post."
    # A hidden Page post, deleted at once, proves the whole path.
    made = call("POST", f"{GRAPH}/{connection['external_id']}/feed", {
        "message": "House Social posting check. Hidden and deleted at once.",
        "published": "false",
        "access_token": token,
    })
    post_id = str(made.get("id") or "")
    if not post_id:
        raise PostError("Facebook did not make the hidden check post.")
    try:
        call("DELETE", f"{GRAPH}/{post_id}", {"access_token": token})
    except PostError:
        return "Ready to post. The hidden check post could not be deleted; remove it in Meta Business Suite."
    return "Ready to post. A hidden post was made and deleted."


def _scopes(call, state: dict, read, token: str) -> set[str] | None:
    row = (state.get("apps") or {}).get("meta") or {}
    secret = read(_HOUSE_APPS["meta"]) if row.get("secret_vault") else None
    if not row.get("app_id") or not secret:
        return None
    body = call("GET", f"{GRAPH}/debug_token", {"input_token": token, "access_token": f"{row['app_id']}|{secret}"})
    data = body.get("data") or {}
    if data.get("is_valid") is False:
        raise PostError("Meta says this token is no longer valid. Press Change and connect again.")
    scopes = data.get("scopes")
    return {str(item) for item in scopes} if isinstance(scopes, list) else None


def _host_image(call, facebook: dict | None, read, media: dict) -> str:
    """Instagram and Threads fetch an image from a public address. An unpublished Page photo gives one."""
    if not facebook:
        return ""
    token = read(_vault_name(facebook))
    if not token:
        return ""
    try:
        body = call(
            "POST",
            f"{GRAPH}/{facebook['external_id']}/photos",
            {"published": "false", "access_token": token},
            files={"source": _file_part(media)},
        )
        photo_id = str(body.get("id") or "")
        return _photo_url(call, photo_id, token) if photo_id else ""
    except PostError:
        return ""


def _photo_url(call, photo_id: str, token: str) -> str:
    try:
        body = call("GET", f"{GRAPH}/{photo_id}", {"fields": "images", "access_token": token})
    except PostError:
        return ""
    images = [item for item in body.get("images") or [] if isinstance(item, dict) and item.get("source")]
    if not images:
        return ""
    return str(max(images, key=lambda item: int(item.get("width") or 0))["source"])


def _permalink(call, url: str, token: str, field: str) -> str:
    try:
        return str(call("GET", url, {"fields": field, "access_token": token}).get(field) or "")
    except PostError:
        return ""


def _wait(call, url: str, token: str, field: str, sleep=None) -> None:
    pause = sleep or time.sleep
    for attempt in range(10):
        body = call("GET", url, {"fields": field, "access_token": token})
        status = str(body.get(field) or "").upper()
        if status in {"FINISHED", "PUBLISHED", ""}:
            return
        if status in {"ERROR", "EXPIRED"}:
            raise PostError(f"The upload ended in {status.lower()}. {body.get('error_message') or ''}".strip())
        pause(3 if attempt < 5 else 6)
    raise PostError("The upload was still processing after a minute. Retry the piece.")


# ---- Piece bookkeeping -----------------------------------------------------


def _claim(state: dict, piece_id: str, moment: datetime, path: Path | None, immediate: bool) -> dict:
    with _LOCK:
        fresh = load(path) if path else load()
        piece = next((item for item in fresh.get("pieces") or [] if item.get("id") == piece_id), None)
        if not piece:
            raise DraftError("That piece is not in the queue.")
        reasons = blockers(fresh, piece, moment, immediate=immediate)
        if reasons:
            raise DraftError(" ".join(reasons))
        claimed = str(piece.get("claimed_at") or "")
        if claimed and _age(claimed, moment) < CLAIM_SECONDS:
            raise DraftError("This piece is already posting.")
        piece["claimed_at"] = moment.isoformat(timespec="seconds")
        save(fresh, path)
        return fresh


def _settle(path: Path | None, piece_id: str, moment: datetime, done: dict, errors: dict, skipped: dict) -> dict:
    from approval import _notify

    with _LOCK:
        current = load(path) if path else load()
        piece = next(item for item in current["pieces"] if item.get("id") == piece_id)
        published = dict(piece.get("published") or {})
        stamp = moment.isoformat(timespec="seconds")
        for platform, row in done.items():
            published[platform] = {"id": row["id"], "permalink": row.get("permalink") or "", "at": stamp}
        log = list(piece.get("publish_log") or [])
        for platform, row in done.items():
            log.append({"at": stamp, "platform": platform, "ok": True, "detail": "Posted."})
        for platform, text in errors.items():
            log.append({"at": stamp, "platform": platform, "ok": False, "detail": text[:300]})
        for platform, text in skipped.items():
            log.append({"at": stamp, "platform": platform, "ok": True, "detail": text})
        piece["published"] = published
        piece["publish_log"] = log[-30:]
        piece["claimed_at"] = ""
        piece["posted"] = bool(published)
        names = " and ".join(NAMES[platform] for platform in PLATFORMS if platform in done)
        if not errors and not published:
            # Every platform was skipped, so nothing went out.
            errors = dict(skipped) or {"facebook": "Nothing could post."}
        if errors:
            failed = " ".join(f"{NAMES[platform]}: {text}" for platform, text in errors.items())
            piece["status"] = "failed"
            piece["failure"] = ((f"Posted to {names}. " if names else "") + failed)[:600]
            message = f"{_title(piece)} did not fully post. {piece['failure']}"
        else:
            piece["status"] = "published"
            piece["failure"] = ""
            message = f"{_title(piece)} posted to {names or 'nothing new'}."
        current = _notify(current, piece, message[:300])
        save(current, path)
        if errors:
            from todo_notes import note_failure

            for platform, text in errors.items():
                current = note_failure(load(path) if path else current, str(piece.get("brand_id") or ""), piece_id, platform, text, "Publish", path)
    return {
        "id": piece_id,
        "status": piece["status"],
        "published": published,
        "failure": piece.get("failure") or "",
        "skipped": skipped,
    }


def _mark_late(state: dict, piece_id: str, hours: float, path: Path | None) -> dict:
    from approval import _notify

    updated = _copy(state)
    piece = next(item for item in updated["pieces"] if item.get("id") == piece_id)
    piece["status"] = "failed"
    piece["failure"] = f"Its time passed {int(hours)} hours ago, so it did not post late. Pick a new time."
    updated = _notify(updated, piece, f"{_title(piece)} missed its time and did not post.")
    save(updated, path)
    return updated


def _targets(state: dict, piece: dict) -> dict[str, dict]:
    """The connected platforms that have words for this piece and are not posted yet."""
    variants = piece.get("variants") or {}
    done = piece.get("published") or {}
    found = {}
    for platform in PLATFORMS:
        if platform in done:
            continue
        if not str((variants.get(platform) or {}).get("body") or "").strip():
            continue
        connection = _connection(state, str(piece.get("brand_id") or ""), platform)
        if connection:
            found[platform] = connection
    return found


def _connection(state: dict, brand_id: str, platform: str) -> dict | None:
    return next(
        (
            item for item in state.get("connections") or []
            if item.get("brand_id") == brand_id and item.get("platform") == platform and item.get("token_vault")
        ),
        None,
    )


def _account(connection: dict) -> dict:
    scopes = connection.get("scopes")
    platform = connection.get("platform") or ""
    if isinstance(scopes, list):
        can = POST_SCOPES.get(platform, "") in scopes
    else:
        can = None
    checked = connection.get("checked") if isinstance(connection.get("checked"), dict) else {}
    if checked:
        can = bool(checked.get("ok"))
    return {"can_post": can, "checked": checked}


def _text(piece: dict, platform: str) -> str:
    variant = (piece.get("variants") or {}).get(platform) or {}
    body = str(variant.get("body") or "").strip()
    tags = [str(tag).strip().lstrip("#") for tag in variant.get("hashtags") or [] if str(tag).strip()]
    if platform == "instagram" and tags:
        body = body + "\n\n" + " ".join("#" + tag for tag in tags)
    return body


def _media(state: dict, piece: dict, root: Path | None) -> dict | None:
    from library import open_asset_file

    assets = {item.get("id"): item for item in state.get("assets") or []}
    unsupported = ""
    for asset_id in piece.get("asset_ids") or []:
        asset = assets.get(asset_id)
        if not asset:
            continue
        kind = str(asset.get("kind") or "")
        if kind in {"image", "logo"} and str(asset.get("mime") or "").startswith("image/"):
            found = open_asset_file(state, asset_id, root=root)
            return {"path": found["path"], "mime": found["mime"], "name": found["name"], "url": str(asset.get("public_url") or "")}
        if kind in {"video", "carousel"}:
            unsupported = unsupported or kind
    return {"unsupported": unsupported} if unsupported else None


def _file_part(media: dict) -> tuple[str, bytes, str]:
    return (str(media.get("name") or "image"), Path(media["path"]).read_bytes(), str(media.get("mime") or "image/jpeg"))


def _vault_name(connection: dict) -> str:
    return str(connection.get("token_vault") or "").removeprefix("vault:")


def _due(piece: dict, now: datetime | None) -> bool:
    when = _when(piece)
    return bool(when) and when <= (now or datetime.now(timezone.utc))


def _late_hours(piece: dict, now: datetime) -> float:
    when = _when(piece)
    return (now - when).total_seconds() / 3600 if when else 0.0


def _when(piece: dict) -> datetime | None:
    raw = str(piece.get("scheduled_for") or "")
    if not raw:
        return None
    try:
        moment = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _age(stamp: str, now: datetime) -> float:
    try:
        then = datetime.fromisoformat(stamp)
    except ValueError:
        return CLAIM_SECONDS
    return (now - then).total_seconds()


def _book(state: dict) -> dict:
    raw = state.get("publishing")
    return dict(raw) if isinstance(raw, dict) else {"on": False, "brands": {}}


def _public_test(item: dict) -> dict:
    return {key: item.get(key) for key in ("id", "platform", "permalink", "at", "deleted", "post_id")}


def _title(piece: dict) -> str:
    return str(piece.get("idea") or "A piece").strip()[:80]


# ---- HTTP ------------------------------------------------------------------


def _call(method: str, url: str, params: dict | None = None, files: dict | None = None) -> dict:
    from connect import _said, scrub

    headers = {"Accept": "application/json"}
    data = None
    target = url
    if method in {"GET", "DELETE"} and params:
        target = f"{url}?{urlencode(params)}"
    elif files:
        data, headers["Content-Type"] = _multipart(params or {}, files)
    elif params is not None:
        data = urlencode(params).encode("utf-8")
    request = Request(target, data=data, method=method, headers=headers)
    try:
        with urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        raise PostError(_said(exc.read().decode("utf-8", errors="replace"), exc.code)) from None
    except (URLError, TimeoutError) as exc:
        raise PostError(f"Meta could not be reached. {scrub(str(exc))[:200]}") from None
    try:
        body = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        raise PostError("Meta answered with something that is not JSON.") from None
    if isinstance(body, dict) and body.get("error"):
        raise PostError(_said(json.dumps(body), 400))
    if body is True or not isinstance(body, dict):
        return {"success": bool(body)}
    return body


def _multipart(fields: dict, files: dict) -> tuple[bytes, str]:
    boundary = "hs" + uuid.uuid4().hex
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode("utf-8"))
    for name, (filename, content, mime) in files.items():
        head = f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'
        parts.append(head.encode("utf-8") + content + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def worker_due_soon(state: dict, hours: int = 24) -> int:
    """How many scheduled pieces fall in the next day, for the House settings line."""
    edge = datetime.now(timezone.utc) + timedelta(hours=hours)
    return sum(
        1 for piece in state.get("pieces") or []
        if piece.get("status") == "scheduled" and (_when(piece) or edge + timedelta(seconds=1)) <= edge
    )
