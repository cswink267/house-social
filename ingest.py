"""Historical ingest for one brand.

Called by the dashboard routes POST /brands/{id}/ingest/preview and
POST /brands/{id}/ingest. Rows land in state["history"]. The audit is
state["ingest_log"]. A saved column map is state["ingest_maps"].
Date-only values become noon America/New_York. Missing metrics stay missing.
"""

from __future__ import annotations

import base64
import csv
import json
import re
import uuid
import zipfile
from datetime import date, datetime, timedelta
from io import BytesIO, StringIO
from pathlib import Path
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from adapt import DraftError
from meta import redact

FIELDS = (
    "caption",
    "published_at",
    "platform",
    "likes",
    "comments",
    "shares",
    "saves",
    "impressions",
    "reach",
    "video_views",
    "permalink",
    "format",
    "pillar",
)
_ALIASES = {
    "caption": ("caption", "text", "message", "body", "post", "content", "description", "tweet"),
    "published_at": ("date", "published_at", "published", "created", "created_at", "timestamp", "time"),
    "platform": ("platform", "network", "channel"),
    "likes": ("likes", "reactions", "like_count"),
    "comments": ("comments", "comment", "replies", "comments_count"),
    "shares": ("shares", "share", "reposts", "retweets"),
    "saves": ("saves", "save", "saved"),
    "impressions": ("impressions", "impression"),
    "reach": ("reach",),
    "video_views": ("video_views", "video views", "videoviews", "plays"),
    "permalink": ("permalink", "url", "link", "post_url"),
    "format": ("format", "media_type", "type"),
    "pillar": ("pillar", "topic"),
}
_FORMATS = {"feed", "quote-image", "carousel", "reel", "story", "thread", "text"}
_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_ZONE = ZoneInfo("America/New_York")


def ingest_for(state: dict, brand_id: str) -> dict:
    from store import resolve_brand

    resolve_brand(state, brand_id)
    log = [item for item in state.get("ingest_log") or [] if item.get("brand_id") == brand_id][:12]
    return {
        "fields": list(FIELDS),
        "mapping": dict((state.get("ingest_maps") or {}).get(brand_id) or {}),
        "log": log,
        "insights": (log[0].get("insights") if log else []) or [],
    }


def preview_ingest(spec: dict) -> dict:
    columns, records = _table(spec)
    if not columns:
        raise DraftError("That file has no header row.")
    suggested = _suggest(columns)
    saved = spec.get("saved") if isinstance(spec.get("saved"), dict) else {}
    if saved and all(str(column) in columns for column in saved):
        suggested = {str(column): str(field) for column, field in saved.items() if str(field) in FIELDS}
    sample = [[str(record.get(column) or "")[:80] for column in columns] for record in records[:3]]
    return {"columns": columns, "suggested": suggested, "sample": sample, "rows": len(records), "fields": list(FIELDS)}


def commit_ingest(state: dict, brand_id: str, spec: dict, path: Path | None = None) -> dict:
    from store import resolve_brand, save

    resolve_brand(state, brand_id)
    if not isinstance(spec, dict):
        raise DraftError("The import needs a file and a column map.")
    columns, records = _table(spec)
    mapping = _mapping(spec.get("mapping"), columns)
    cleaned = [row for row in (_clean_row(record, mapping) for record in records) if row is not None]
    if not cleaned:
        raise DraftError("No posts were in that file.")
    existing = {str(item.get("dedupe") or "") for item in state.get("history") or [] if item.get("brand_id") == brand_id}
    accepted = []
    skipped = 0
    seen = set(existing)
    for row in cleaned:
        if row["dedupe"] in seen:
            skipped += 1
            continue
        seen.add(row["dedupe"])
        accepted.append(row)
    incomplete = len([row for row in accepted if row["incomplete"]])
    stored = [_stored(brand_id, row) for row in accepted]
    others = [item for item in state.get("history") or [] if item.get("brand_id") != brand_id]
    mine = [item for item in state.get("history") or [] if item.get("brand_id") == brand_id]
    history = others + (mine + stored)[-2000:]
    maps = dict(state.get("ingest_maps") or {})
    maps[brand_id] = mapping
    insights = first_insights([item for item in history if item.get("brand_id") == brand_id])
    audit = {
        "id": str(uuid.uuid4()),
        "brand_id": brand_id,
        "at": datetime.now(_ZONE).isoformat(),
        "filename": _filename(spec.get("filename")),
        "accepted": len(accepted),
        "skipped": skipped,
        "incomplete": incomplete,
        "mapping": mapping,
        "insights": insights["lines"],
    }
    own_log = [item for item in state.get("ingest_log") or [] if item.get("brand_id") == brand_id]
    other_log = [item for item in state.get("ingest_log") or [] if item.get("brand_id") != brand_id]
    updated = {**state, "history": history, "ingest_maps": maps, "ingest_log": [audit, *own_log][:24] + other_log}
    save(updated, path)
    return {"accepted": len(accepted), "skipped": skipped, "incomplete": incomplete, "insights": insights["lines"], "audit": audit}


def first_insights(rows: list[dict]) -> dict:
    from analytics_desk import annotate

    dated = [row for row in rows if row.get("published_at") and row.get("engagements") is not None]
    count = len(dated)
    lines = [f"Based on {count} posts."]
    if count < 15:
        lines.append(f"Not enough posts to split into a top, middle, and bottom. Based on {count} posts.")
    else:
        ranked = sorted(dated, key=lambda row: int(row.get("engagements") or 0), reverse=True)
        band = max(3, count // 5)
        if band >= 3 and count - band >= 3:
            lines.append(f"The highest {band} of {count} posts are the stronger set. The lowest {band} are the quieter set.")
            lines.extend(_openers(ranked[:band], band, count))
        else:
            lines.append(f"Not enough posts to split into a top, middle, and bottom. Based on {count} posts.")
    posts = [_as_post(row) for row in dated]
    clear = [item for item in annotate(posts, [])["patterns"] if item.get("clear") and item.get("detail")]
    if clear:
        lines.extend(str(item["detail"]) for item in clear)
    else:
        lines.append("No hour, format, or hook pattern is clear enough to change the voice.")
    return {"lines": lines, "posts": count}


def _table(spec: dict) -> tuple[list[str], list[dict]]:
    if not isinstance(spec, dict):
        raise DraftError("The import needs a file.")
    if spec.get("xlsx"):
        grid = _xlsx_grid(spec.get("xlsx"))
    else:
        text = str(spec.get("text") or "")
        if len(text) > 400_000:
            raise DraftError("That file is too big.")
        grid = _text_grid(text)
    if not grid:
        raise DraftError("That file has no header row.")
    seen: set[str] = set()
    columns = []
    for index, cell in enumerate(grid[0]):
        name = str(cell or "").strip() or f"column_{index + 1}"
        while name.lower() in seen:
            name = name + "_2"
        seen.add(name.lower())
        columns.append(name)
    records = []
    for cells in grid[1:]:
        if not any(str(cell or "").strip() for cell in cells):
            continue
        records.append({column: str(cells[index]).strip() if index < len(cells) else "" for index, column in enumerate(columns)})
        if len(records) >= 2000:
            break
    return columns, records


def _text_grid(text: str) -> list[list[str]]:
    stripped = text.strip()
    if not stripped:
        raise DraftError("Paste the rows, or choose a file.")
    if stripped[0] in "[{":
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise DraftError("That JSON could not be read.") from exc
        if isinstance(data, dict):
            data = data.get("data") or data.get("posts") or data.get("rows")
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            raise DraftError("JSON needs a list of posts.")
        keys = list(data[0].keys())
        return [keys, *[[str(item.get(key) or "") for key in keys] for item in data if isinstance(item, dict)]]
    sample = stripped.splitlines()[0]
    delimiter = "\t" if sample.count("\t") > sample.count(",") else ","
    rows = list(csv.reader(StringIO(stripped), delimiter=delimiter))
    return [row for row in rows if any(str(cell).strip() for cell in row)]


def _xlsx_grid(raw) -> list[list[str]]:
    try:
        blob = base64.b64decode(str(raw), validate=True)
    except (ValueError, TypeError) as exc:
        raise DraftError("That spreadsheet could not be read.") from exc
    if len(blob) > 400_000:
        raise DraftError("That file is too big.")
    try:
        book = zipfile.ZipFile(BytesIO(blob))
        shared = _shared_strings(book)
        sheet = book.read("xl/worksheets/sheet1.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        raise DraftError("That spreadsheet could not be read.") from exc
    root = ElementTree.fromstring(sheet)
    grid = []
    for row in root.findall("m:sheetData/m:row", _NS):
        cells = []
        for cell in row.findall("m:c", _NS):
            kind = cell.attrib.get("t")
            value = cell.findtext("m:v", default="", namespaces=_NS)
            if kind == "s" and str(value).isdigit():
                index = int(value)
                value = shared[index] if index < len(shared) else ""
            elif kind == "inlineStr":
                value = "".join(node.text or "" for node in cell.findall(".//m:t", _NS))
            cells.append(value)
        grid.append(cells)
    return grid


def _shared_strings(book: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in book.namelist():
        return []
    root = ElementTree.fromstring(book.read("xl/sharedStrings.xml"))
    return ["".join(node.text or "" for node in item.findall(".//m:t", _NS)) for item in root.findall("m:si", _NS)]


def _suggest(columns: list[str]) -> dict:
    used = set()
    found = {}
    folded = [(column.lower().replace(" ", "_"), column) for column in columns]
    for field, names in _ALIASES.items():
        for name in names:
            key = name.replace(" ", "_")
            column = next((original for folded_name, original in folded if folded_name == key or folded_name.endswith("_" + key)), None)
            if column and column not in used:
                found[column] = field
                used.add(column)
                break
    return found


def _mapping(raw, columns: list[str]) -> dict:
    if not isinstance(raw, dict):
        raise DraftError("Map the columns before importing.")
    mapping = {}
    seen = set()
    for column, field in raw.items():
        name = str(field or "").strip()
        if not name:
            continue
        if str(column) not in columns:
            raise DraftError("That column is not in the file.")
        if name not in FIELDS:
            raise DraftError("That field is not one this desk keeps.")
        if name in seen:
            raise DraftError("Each field can be mapped once.")
        seen.add(name)
        mapping[str(column)] = name
    if "caption" not in seen:
        raise DraftError("Map a column to the caption.")
    return mapping


def _clean_row(record: dict, mapping: dict) -> dict | None:
    values = {field: "" for field in FIELDS}
    for column, field in mapping.items():
        values[field] = str(record.get(column) or "").strip()
    text = redact(values["caption"]).strip()
    if not text:
        return None
    published, hour = _when(values["published_at"])
    numbers = {name: _number(values[name]) for name in ("likes", "comments", "shares", "saves", "impressions", "reach", "video_views")}
    present = [numbers[name] for name in ("likes", "comments", "shares") if numbers[name] is not None]
    return {
        "text": text[:500],
        "published_at": published,
        "local_hour": hour,
        "engagements": sum(present) if present else None,
        "impressions": numbers["impressions"],
        "comments": numbers["comments"],
        "shares": numbers["shares"],
        "saves": numbers["saves"],
        "reach": numbers["reach"],
        "video_views": numbers["video_views"],
        "permalink": values["permalink"][:300],
        "platform": _platform(values["platform"]),
        "format": _format(values["format"]),
        "pillar": values["pillar"][:40],
        "dedupe": _fingerprint(values["permalink"][:300], published, text),
        "incomplete": not published or not present,
    }


def _when(text: str) -> tuple[str, int | None]:
    raw = text.strip()
    if not raw:
        return "", None
    if re.fullmatch(r"\d{5}", raw):
        moment = datetime.combine(date(1899, 12, 30) + timedelta(days=int(raw)), datetime.min.time()).replace(hour=12, tzinfo=_ZONE)
        return moment.isoformat(), 12
    matched = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if matched:
        year, month, day = (int(matched.group(index)) for index in (1, 2, 3))
        return datetime(year, month, day, 12, 0, tzinfo=_ZONE).isoformat(), 12
    matched = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", raw)
    if matched:
        month, day, year = (int(matched.group(index)) for index in (1, 2, 3))
        return datetime(year, month, day, 12, 0, tzinfo=_ZONE).isoformat(), 12
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return "", None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_ZONE)
    return parsed.isoformat(), parsed.astimezone(_ZONE).hour


def _number(text: str) -> int | None:
    raw = text.replace(",", "").strip()
    if not re.fullmatch(r"\d+", raw):
        return None
    number = int(raw)
    if number > 10_000_000:
        return None
    return number


def _platform(text: str) -> str:
    name = text.strip().lower()
    if name in {"ig", "instagram"}:
        return "instagram"
    if name in {"fb", "facebook"}:
        return "facebook"
    if name in {"twitter", "x"}:
        return "x"
    return name[:16]


def _format(text: str) -> str:
    name = text.strip().lower().replace(" ", "-")
    if name in {"image", "photo"}:
        return "feed"
    if name == "video":
        return "reel"
    return name if name in _FORMATS else "unknown"


def _fingerprint(permalink: str, published: str, text: str) -> str:
    link = permalink.strip().lower()
    if link:
        return "link:" + link[:300]
    return "text:" + published[:10] + ":" + " ".join(text.lower().split())[:80]


def _filename(value) -> str:
    name = Path(str(value or "paste")).name.replace("\\", "").strip() or "paste"
    if ".." in name:
        name = "paste"
    return name[:80]


def _stored(brand_id: str, item: dict) -> dict:
    return {"id": "history:" + str(uuid.uuid4()), "brand_id": brand_id, "preview": item["text"], "source": "history", **item}


def _as_post(row: dict) -> dict:
    return {
        "id": row.get("id") or "",
        "preview": row.get("preview") or row.get("text") or "",
        "published_at": row.get("published_at") or "",
        "local_hour": row.get("local_hour"),
        "engagements": row.get("engagements"),
        "format": row.get("format") or "unknown",
        "pillar": row.get("pillar") or "",
    }


def _openers(rows: list[dict], band: int, count: int) -> list[str]:
    found: dict[str, int] = {}
    for row in rows:
        opener = _opener(str(row.get("preview") or row.get("text") or ""))
        if opener:
            found[opener] = found.get(opener, 0) + 1
    repeated = [name for name, times in found.items() if times >= 2]
    if not repeated:
        return ["No opener repeats among the stronger posts."]
    name = repeated[0]
    return [f'"{name}" opens {found[name]} of the stronger posts. That set is the highest {band} of {count}.']


def _opener(text: str) -> str:
    sentence = re.split(r"[.!?]", text.strip(), maxsplit=1)[0]
    words = sentence.split()[:6]
    if len(words) < 3:
        return ""
    return " ".join(words).lower()
