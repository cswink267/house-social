"""A mapped import keeps missing numbers missing and skips a row it already has."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ingest import commit_ingest, preview_ingest  # noqa: E402
from store import empty_state, load, studio  # noqa: E402


CSV = "\n".join(
    [
        "Post caption,Created,Likes,Comments",
        "You felt that dread.,2026-10-01,20,0",
        "You felt that dread.,2026-10-02,20,0",
        "You felt that dread.,2026-10-03,20,0",
        "A quiet evening post.,2026-10-01,4,0",
        "A quiet evening post.,2026-10-02,4,0",
        "A quiet evening post.,2026-10-03,4,0",
        "No date on this one.,,9,0",
    ]
)


def test_ingest_maps_columns_and_skips_a_repeat(tmp_path: Path):
    path = tmp_path / "state.json"
    preview = preview_ingest({"text": CSV, "filename": "/tmp/secret/posts.csv"})
    assert preview["suggested"]["Post caption"] == "caption"
    assert preview["suggested"]["Created"] == "published_at"
    assert preview["suggested"]["Likes"] == "likes"
    saved = commit_ingest(
        empty_state(),
        "misfit-mindset",
        {"text": CSV, "filename": "/tmp/secret/posts.csv", "mapping": preview["suggested"]},
        path,
    )
    assert saved["accepted"] == 7
    assert saved["incomplete"] == 1
    assert saved["audit"]["filename"] == "posts.csv"
    assert "%" not in "\n".join(saved["insights"])
    assert saved["insights"][0].startswith("Based on 6 posts.")
    row = next(item for item in load(path)["history"] if item["preview"].startswith("No date"))
    assert row["published_at"] == ""
    assert row["saves"] is None
    dated = next(item for item in load(path)["history"] if item["published_at"])
    local = datetime.fromisoformat(dated["published_at"]).astimezone(ZoneInfo("America/New_York"))
    assert local.hour == 12
    again = commit_ingest(load(path), "misfit-mindset", {"text": CSV, "mapping": preview["suggested"], "filename": "posts.csv"}, path)
    assert again["accepted"] == 0
    assert again["skipped"] == 7
    desk = studio(load(path), "misfit-mindset")
    assert desk["ingest"]["log"][0]["accepted"] == 0
    assert any(section["id"] == "ingest" for section in desk["brand"]["sections"])
