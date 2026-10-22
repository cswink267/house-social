"""Brand library for House Social.

Files live beside the state file, never in git. State keeps the name,
the folder, the tags, and the relative file key. A new version is
appended. The older file stays where it was.
"""

from __future__ import annotations

import base64
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from adapt import DraftError
from store import _copy, _find, _label, resolve_brand, save


KINDS = ("image", "video", "carousel", "template", "logo", "copy")
_TEXT = {"template", "copy"}
_IMAGE = {"image/png", "image/jpeg", "image/gif", "image/webp"}
_VIDEO = {"video/mp4", "video/webm"}
_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
    "video/mp4": "mp4",
    "video/webm": "webm",
}
_IMAGE_LIMIT = 4_000_000
_VIDEO_LIMIT = 12_000_000
_FRAMES = 10


def assets_root() -> Path:
    override = os.environ.get("HOUSE_SOCIAL_ASSETS", "").strip()
    if override:
        return Path(override)
    from store import state_path

    return state_path().parent / "assets"


def library_for(
    state: dict,
    brand_id: str,
    *,
    q: str = "",
    kind: str = "",
    folder: str = "",
    tag: str = "",
) -> dict:
    brand = resolve_brand(state, brand_id)
    owned = [asset for asset in state.get("assets") or [] if asset.get("brand_id") == brand.id]
    folders = sorted({asset.get("folder") or "" for asset in owned if asset.get("folder")})
    tags = sorted({item for asset in owned for item in asset.get("tags") or []})
    needle = q.strip().lower()
    kind_name = kind.strip().lower()
    folder_name = folder.strip().strip("/")
    tag_name = tag.strip().lower()
    cards = []
    for asset in owned:
        if kind_name and asset.get("kind") != kind_name:
            continue
        if folder_name and not _in_folder(asset.get("folder") or "", folder_name):
            continue
        if tag_name and tag_name not in {item.lower() for item in asset.get("tags") or []}:
            continue
        if needle and needle not in _haystack(asset):
            continue
        cards.append(_public(state, asset))
    cards.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    return {"folders": folders, "tags": tags, "assets": cards}


def save_asset(state: dict, brand_id: str, spec: dict, path: Path | None = None, root: Path | None = None) -> dict:
    brand = resolve_brand(state, brand_id)
    if not isinstance(spec, dict):
        raise DraftError("The asset needs fields.")
    asset_id = str(uuid.uuid4())
    version = _version_from(spec, brand.id, asset_id, root or assets_root())
    now = datetime.now(timezone.utc).isoformat()
    name = _label(spec.get("name") or "", 80)
    if not name:
        raise DraftError("Name the asset.")
    asset = {
        "id": asset_id,
        "brand_id": brand.id,
        "kind": version["kind"],
        "name": name,
        "folder": _folder(spec.get("folder") or ""),
        "tags": _tags(spec.get("tags") or []),
        "note": _label(spec.get("note") or "", 240),
        "body": version["body"],
        "file": version["file"],
        "mime": version["mime"],
        "frames": version["frames"],
        "created_at": now,
        "updated_at": now,
        "versions": [version],
        "uses": [],
    }
    updated = _copy(state)
    updated.setdefault("assets", [])
    updated["assets"] = [asset, *updated["assets"]]
    save(updated, path)
    return _public(updated, asset)


def revise_asset(state: dict, asset_id: str, spec: dict, path: Path | None = None, root: Path | None = None) -> dict:
    if not isinstance(spec, dict):
        raise DraftError("The asset needs fields.")
    updated = _copy(state)
    index, asset = _asset(updated, asset_id)
    store = root or assets_root()
    if spec.get("restore"):
        source = _version(asset, str(spec.get("restore")))
        version = {
            "id": str(uuid.uuid4()),
            "at": datetime.now(timezone.utc).isoformat(),
            "note": _label(spec.get("note") or "Restored", 120),
            "kind": asset["kind"],
            "body": source.get("body") or "",
            "file": source.get("file") or "",
            "mime": source.get("mime") or "",
            "frames": [dict(frame) for frame in source.get("frames") or []],
        }
        asset = _apply_version(asset, version)
    elif _has_content(spec):
        version = _version_from(spec, asset["brand_id"], asset["id"], store, kind=asset["kind"])
        asset = _apply_version(asset, version)
    else:
        asset = dict(asset)
    if "name" in spec:
        named = _label(spec.get("name") or "", 80)
        if named:
            asset["name"] = named
    if "folder" in spec:
        asset["folder"] = _folder(spec.get("folder") or "")
    if "tags" in spec:
        asset["tags"] = _tags(spec.get("tags") or [])
    if "note" in spec and not spec.get("restore"):
        asset["note"] = _label(spec.get("note") or "", 240)
    asset["updated_at"] = datetime.now(timezone.utc).isoformat()
    assets = list(updated.get("assets") or [])
    assets[index] = asset
    updated["assets"] = assets
    save(updated, path)
    return _public(updated, asset)


def record_use(state: dict, asset_id: str, spec: dict, path: Path | None = None) -> dict:
    if not isinstance(spec, dict):
        raise DraftError("Say which piece or post used it.")
    piece_id = str(spec.get("piece_id") or "").strip()
    post_id = _label(spec.get("post_id") or "", 80)
    if not piece_id and not post_id:
        raise DraftError("Say which piece or post used it.")
    updated = _copy(state)
    index, asset = _asset(updated, asset_id)
    if piece_id:
        _, piece = _find(updated, piece_id)
        if piece.get("brand_id") != asset.get("brand_id"):
            raise DraftError("That piece belongs to another brand.")
    uses = list(asset.get("uses") or [])
    already = any(
        (piece_id and item.get("piece_id") == piece_id) or (post_id and not piece_id and item.get("post_id") == post_id)
        for item in uses
    )
    if not already:
        uses = [
            *uses,
            {
                "id": str(uuid.uuid4()),
                "at": datetime.now(timezone.utc).isoformat(),
                "piece_id": piece_id,
                "post_id": post_id,
            },
        ]
    asset = dict(asset)
    asset["uses"] = uses
    if piece_id:
        piece_index, piece = _find(updated, piece_id)
        ids = [item for item in (piece.get("asset_ids") or []) if item != asset["id"]]
        pieces = list(updated["pieces"])
        pieces[piece_index] = {**piece, "asset_ids": [*ids, asset["id"]]}
        updated["pieces"] = pieces
    assets = list(updated.get("assets") or [])
    assets[index] = asset
    updated["assets"] = assets
    save(updated, path)
    return _public(updated, asset)


def open_asset_file(
    state: dict,
    asset_id: str,
    version_id: str = "",
    frame: int | None = None,
    root: Path | None = None,
) -> dict:
    _, asset = _asset(_copy(state), asset_id)
    version = _version(asset, version_id) if version_id else asset
    if frame is None and not version.get("file") and version.get("frames"):
        frame = 0
    if frame is None:
        relative = str(version.get("file") or "")
        mime = str(version.get("mime") or "application/octet-stream")
        name = asset.get("name") or "asset"
    else:
        frames = list(version.get("frames") or [])
        if frame < 0 or frame >= len(frames):
            raise DraftError("That frame is not on the asset.")
        relative = str(frames[frame].get("file") or "")
        mime = str(frames[frame].get("mime") or "application/octet-stream")
        name = frames[frame].get("name") or asset.get("name") or "frame"
    path = _safe_path(root or assets_root(), relative)
    if not path.is_file():
        raise DraftError("That file is not in the library.")
    return {"path": path, "mime": mime, "name": _download_name(name, mime)}


def _apply_version(asset: dict, version: dict) -> dict:
    versions = [*(asset.get("versions") or []), version][-30:]
    return {
        **asset,
        "body": version["body"],
        "file": version["file"],
        "mime": version["mime"],
        "frames": version["frames"],
        "versions": versions,
    }


def _version_from(spec: dict, brand_id: str, asset_id: str, root: Path, kind: str = "") -> dict:
    kind_name = (kind or str(spec.get("kind") or "")).strip().lower()
    if kind_name not in KINDS:
        raise DraftError("Kind is image, video, carousel, template, logo, or copy.")
    body = str(spec.get("body") or "")
    if len(body) > 8000:
        raise DraftError("That copy is too long.")
    files = _incoming_files(spec, kind_name)
    version_id = str(uuid.uuid4())
    stored = [_store_file(root, brand_id, asset_id, version_id, index, item, kind_name) for index, item in enumerate(files)]
    single = stored[0] if stored and kind_name != "carousel" else {"file": "", "mime": ""}
    frames = stored if kind_name == "carousel" else []
    if kind_name in _TEXT and not body.strip():
        raise DraftError("A copy block needs the words.")
    if kind_name not in _TEXT and not stored:
        raise DraftError("That asset needs a file.")
    return {
        "id": version_id,
        "at": datetime.now(timezone.utc).isoformat(),
        "note": _label(spec.get("version_note") or "", 120),
        "kind": kind_name,
        "body": body.strip(),
        "file": "" if kind_name == "carousel" else single["file"],
        "mime": "" if kind_name == "carousel" else single["mime"],
        "frames": frames,
    }


def _incoming_files(spec: dict, kind: str) -> list[dict]:
    raw = spec.get("files") if isinstance(spec.get("files"), list) else []
    if spec.get("data"):
        raw = [{"name": spec.get("file_name") or "", "data": spec.get("data")}, *raw]
    if kind in _TEXT and raw:
        raise DraftError("A copy block holds words. Save the picture as an image.")
    if kind != "carousel" and len(raw) > 1:
        raise DraftError("An image is one file. A carousel can hold several.")
    if len(raw) > _FRAMES:
        raise DraftError("A carousel holds up to 10 frames.")
    return raw


def _store_file(root: Path, brand_id: str, asset_id: str, version_id: str, index: int, item: dict, kind: str) -> dict:
    if not isinstance(item, dict):
        raise DraftError("That file is not readable.")
    data = _decode(str(item.get("data") or ""))
    mime = _sniff(data)
    if kind == "video" and mime not in _VIDEO:
        raise DraftError("A video asset needs an MP4 or WEBM file.")
    if kind in {"image", "logo", "carousel"} and mime not in _IMAGE:
        raise DraftError("That asset needs an image file.")
    if mime in _VIDEO and len(data) > _VIDEO_LIMIT:
        raise DraftError("That video is over 12 MB.")
    if mime in _IMAGE and len(data) > _IMAGE_LIMIT:
        raise DraftError("That image is over 4 MB.")
    suffix = f"-{index}" if index else ""
    relative = f"{brand_id}/{asset_id}/{version_id}{suffix}.{_EXT[mime]}"
    target = _safe_path(root, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return {"name": _label(item.get("name") or "", 80), "file": relative, "mime": mime}


def _decode(value: str) -> bytes:
    text = value.strip()
    if text.startswith("data:") and "," in text:
        text = text.split(",", 1)[1]
    try:
        data = base64.b64decode(text, validate=True)
    except Exception as exc:
        raise DraftError("That file is not readable.") from exc
    if not data:
        raise DraftError("That file is empty.")
    return data


def _sniff(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    if len(data) > 12 and data[4:8] == b"ftyp":
        return "video/mp4"
    if data.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"
    raise DraftError("Use a PNG, JPEG, WEBP, GIF, MP4, or WEBM file.")


def _safe_path(root: Path, relative: str) -> Path:
    text = str(relative or "").strip().replace("\\", "/")
    if not text or text.startswith("/") or ".." in Path(text).parts:
        raise DraftError("That file path is not allowed.")
    base = root.resolve()
    target = (base / text).resolve()
    if target != base and base not in target.parents:
        raise DraftError("That file path is not allowed.")
    return target


def _public(state: dict, asset: dict) -> dict:
    uses = []
    for item in asset.get("uses") or []:
        piece = next((row for row in state.get("pieces") or [] if row.get("id") == item.get("piece_id")), None)
        uses.append(
            {
                "id": item.get("id"),
                "at": item.get("at"),
                "piece_id": item.get("piece_id") or "",
                "post_id": item.get("post_id") or "",
                "idea": str((piece or {}).get("idea") or "")[:80],
            }
        )
    versions = [
        {
            "id": version.get("id"),
            "at": version.get("at"),
            "note": version.get("note") or "",
            "body": version.get("body") or "",
            "has_file": bool(version.get("file")),
            "frames": len(version.get("frames") or []),
        }
        for version in asset.get("versions") or []
    ]
    return {
        "id": asset.get("id"),
        "brand_id": asset.get("brand_id"),
        "kind": asset.get("kind"),
        "name": asset.get("name") or "",
        "folder": asset.get("folder") or "",
        "tags": list(asset.get("tags") or []),
        "note": asset.get("note") or "",
        "body": asset.get("body") or "",
        "mime": asset.get("mime") or "",
        "has_file": bool(asset.get("file") or asset.get("frames")),
        "frames": [
            {"name": frame.get("name") or "", "mime": frame.get("mime") or ""}
            for frame in asset.get("frames") or []
        ],
        "versions": versions,
        "uses": uses,
        "performance": _performance(state, asset),
        "updated_at": asset.get("updated_at") or "",
    }


def _performance(state: dict, asset: dict) -> dict:
    piece_ids = {item.get("piece_id") for item in asset.get("uses") or [] if item.get("piece_id")}
    post_ids = {item.get("post_id") for item in asset.get("uses") or [] if item.get("post_id")}
    engagements = 0
    impressions = 0
    samples = 0
    for stat in state.get("stats") or []:
        if stat.get("brand_id") != asset.get("brand_id"):
            continue
        if stat.get("piece_id") not in piece_ids and stat.get("external_id") not in post_ids:
            continue
        metrics = stat.get("metrics") if isinstance(stat.get("metrics"), dict) else {}
        engagements += int(metrics.get("engagements") or 0)
        impressions += int(metrics.get("impressions") or 0)
        samples += 1
    posts = ((state.get("pulls") or {}).get(asset.get("brand_id")) or {}).get("posts") or []
    seen = {stat.get("external_id") for stat in state.get("stats") or [] if stat.get("external_id")}
    for post in posts:
        if post.get("id") not in post_ids or post.get("id") in seen:
            continue
        engagements += int(post.get("engagements") or 0)
        samples += 1
    return {
        "uses": len(asset.get("uses") or []),
        "samples": samples,
        "engagements": engagements,
        "impressions": impressions,
    }


def _asset(state: dict, asset_id: str) -> tuple[int, dict]:
    for index, asset in enumerate(state.get("assets") or []):
        if asset.get("id") == asset_id:
            return index, asset
    raise DraftError("That asset is not in the library.")


def _version(asset: dict, version_id: str) -> dict:
    for version in asset.get("versions") or []:
        if version.get("id") == version_id:
            return version
    raise DraftError("That version is not on the asset.")


def _has_content(spec: dict) -> bool:
    return "body" in spec or "data" in spec or "files" in spec


def _haystack(asset: dict) -> str:
    parts = [
        asset.get("name") or "",
        asset.get("folder") or "",
        asset.get("note") or "",
        asset.get("body") or "",
        " ".join(asset.get("tags") or []),
    ]
    return " ".join(parts).lower()


def _in_folder(folder: str, wanted: str) -> bool:
    return folder == wanted or folder.startswith(wanted + "/")


def _folder(value: object) -> str:
    text = str(value or "").strip().strip("/")
    if not text:
        return ""
    parts = text.split("/")
    if len(parts) > 4:
        raise DraftError("That folder is too deep.")
    for part in parts:
        cleaned = part.replace(" ", "").replace("-", "").replace("_", "")
        if part in {".", ".."} or not cleaned.isalnum():
            raise DraftError("Folders are words separated by slashes.")
        if len(part) > 40:
            raise DraftError("That folder name is too long.")
    return "/".join(parts)


def _tags(values) -> list[str]:
    if isinstance(values, str):
        values = values.split(",")
    rows = []
    for value in values or []:
        text = str(value or "").strip().lstrip("#")
        if text and text.lower() not in {row.lower() for row in rows}:
            rows.append(text[:24])
    return rows[:12]


def _download_name(name: str, mime: str) -> str:
    stem = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in str(name or "asset")).strip("-") or "asset"
    return f"{stem}.{_EXT.get(mime, 'bin')}"
