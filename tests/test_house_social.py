"""House Social keeps one idea from shipping as three identical posts."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapt import DraftError, issues, shape  # noqa: E402
from brands import seed_brand  # noqa: E402
from store import (  # noqa: E402
    add_brand,
    remove_brand,
    calendar_entries,
    calendar_span,
    create_piece,
    empty_state,
    load,
    roster,
    set_channels,
    studio,
    pull_brand,
    save_connection,
    save_voice,
    update_piece,
)


IDEA = "The fire held. The night did not."


def test_roster_keeps_known_handles_and_open_slots():
    rows = {row["id"]: row for row in roster(empty_state())}
    josie = rows["josie-blackthorn"]
    facebook = next(channel for channel in josie["channels"] if channel["platform"] == "facebook")
    assert facebook["handle"] == "josephine.blackthorn"
    assert facebook["external_id"] == "729680390229294"
    assert facebook["posting"] is False
    misfit_ig = next(
        channel for channel in rows["misfit-mindset"]["channels"] if channel["platform"] == "instagram"
    )
    assert misfit_ig["handle"] == "misfit.mindset.store"
    morgan_ig = next(
        channel for channel in rows["morgan-rae"]["channels"] if channel["platform"] == "instagram"
    )
    assert morgan_ig["handle"] == "morgan.rae.mm"
    veil_threads = next(
        channel for channel in rows["blackthorn-veil"]["channels"] if channel["platform"] == "threads"
    )
    assert veil_threads["known"] is False
    assert "jamhaul" in rows
    assert "donnas-loaf" in rows


def test_two_sentences_become_three_different_drafts(tmp_path: Path):
    path = tmp_path / "state.json"
    piece = create_piece(empty_state(), "misfit-mindset", f"{IDEA} #misfitmindset", path)
    variants = piece["variants"]
    bodies = [variants[name]["body"].strip() for name in ("facebook", "instagram", "threads")]
    assert len(set(bodies)) == 3
    assert all("#" not in body for body in bodies)
    assert "misfitmindset" in variants["instagram"]["hashtags"]
    assert variants["threads"]["body"].strip() == "The fire held."
    assert variants["instagram"]["body"].endswith("Misfit Mindset")
    assert piece["posted"] is False
    saved = load(path)
    ready = update_piece(saved, piece["id"], status="ready", path=path)
    assert ready["status"] == "ready"
    assert ready["posted"] is False


def test_josie_facebook_stays_a_quote_card_until_the_image_is_ready(tmp_path: Path):
    path = tmp_path / "state.json"
    piece = create_piece(empty_state(), "josie-blackthorn", "Stay. The rest can wait.", path)
    facebook = piece["variants"]["facebook"]
    assert facebook["needs_image"] is True
    assert facebook["body"] == "Stay."
    assert "jamhaul.com" not in facebook["body"]
    with pytest.raises(DraftError, match="quote image"):
        update_piece(load(path), piece["id"], status="ready", path=path)
    ready = update_piece(
        load(path),
        piece["id"],
        variants={
            "facebook": {"image_ready": True},
            "threads": {"body": "Stay, and leave the rest."},
        },
        status="ready",
        path=path,
    )
    assert ready["status"] == "ready"


def test_jamhaul_requires_the_site_and_a_real_question(tmp_path: Path):
    path = tmp_path / "state.json"
    piece = create_piece(empty_state(), "jamhaul", "What is a haul?", path)
    facebook = piece["variants"]["facebook"]["body"]
    assert "jamhaul.com" in facebook
    assert "?" in facebook
    bodies = [piece["variants"][name]["body"].strip() for name in ("facebook", "instagram", "threads")]
    assert len(set(bodies)) == 3
    ready = update_piece(load(path), piece["id"], status="ready", path=path)
    assert ready["status"] == "ready"
    from approval import decide, submit_review
    submit_review(load(path), piece["id"], path)
    decide(load(path), piece["id"], {"author": "Approver", "decision": "approved"}, path)
    scheduled = update_piece(
        load(path),
        piece["id"],
        status="scheduled",
        scheduled_for="2026-10-22T15:00:00+00:00",
        path=path,
    )
    assert scheduled["status"] == "scheduled"
    assert scheduled["posted"] is False
    assert scheduled["scheduled_for"].startswith("2026-10-22T15:00:00")


def test_jamhaul_cannot_ride_another_brand(tmp_path: Path):
    path = tmp_path / "state.json"
    piece = create_piece(empty_state(), "misfit-mindset", IDEA, path)
    with pytest.raises(DraftError, match="JamHaul does not ride"):
        update_piece(
            load(path),
            piece["id"],
            variants={"facebook": {"body": "Come see jamhaul.com"}},
            status="ready",
            path=path,
        )


def test_threads_clip_and_empty_idea():
    brand = seed_brand("blunt")
    assert brand is not None
    long_idea = ("word " * 200).strip()
    variants = shape(brand, long_idea)
    assert len(variants["threads"]["body"]) <= 500
    with pytest.raises(DraftError, match="Write the idea"):
        shape(brand, "   ")


def test_custom_brand_and_channel_edit_roundtrip(tmp_path: Path):
    path = tmp_path / "state.json"
    state = empty_state()
    add_brand(
        state,
        {
            "id": "north-room",
            "name": "North Room",
            "site": "https://example.com",
            "voice": "A spare room.",
            "tags": ["north"],
        },
        path,
    )
    state = load(path)
    channels = set_channels(
        state,
        "north-room",
        {"threads": {"handle": "@north.room", "external_id": ""}},
        path,
    )
    threads = next(channel for channel in channels if channel["platform"] == "threads")
    assert threads["handle"] == "north.room"
    assert threads["known"] is True
    assert threads["posting"] is False
    piece = create_piece(load(path), "north-room", IDEA, path)
    assert piece["variants"]["instagram"]["body"].endswith("North Room")
    with pytest.raises(DraftError, match="Unknown brand"):
        create_piece(load(path), "not-a-brand", IDEA, path)


def test_a_custom_brand_can_be_removed_and_a_house_brand_cannot(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOUSE_SOCIAL_ASSETS", str(tmp_path / "files"))
    path = tmp_path / "state.json"
    add_brand(empty_state(), {"id": "north-room", "name": "North Room"}, path)
    piece = create_piece(load(path), "north-room", IDEA, path)
    files = tmp_path / "files" / "north-room"
    files.mkdir(parents=True)
    (files / "note.txt").write_text("keep", encoding="utf-8")
    kept = tmp_path / "files" / "other"
    kept.mkdir()
    (kept / "stay.txt").write_text("stay", encoding="utf-8")
    removed = remove_brand(load(path), "north-room", path)
    assert removed["id"] == "north-room"
    assert all(item["id"] != "north-room" for item in roster(load(path)))
    assert all(item["id"] != piece["id"] for item in load(path)["pieces"])
    assert not files.exists()
    assert (kept / "stay.txt").read_text(encoding="utf-8") == "stay"
    with pytest.raises(DraftError, match="Josie and Misfit stay"):
        remove_brand(load(path), "josie-blackthorn", path)
    with pytest.raises(DraftError, match="Josie and Misfit stay"):
        remove_brand(load(path), "misfit-mindset", path)
    assert any(item["id"] == "jamhaul" for item in roster(load(path)))
    create_piece(load(path), "jamhaul", "What is a haul?", path)
    remove_brand(load(path), "jamhaul", path)
    assert all(item["id"] != "jamhaul" for item in roster(load(path)))
    with pytest.raises(DraftError, match="Unknown brand"):
        create_piece(load(path), "jamhaul", "What is a haul?", path)
    restored = add_brand(load(path), {"id": "jamhaul", "name": "JamHaul"}, path)
    assert restored["id"] == "jamhaul"
    assert any(item["id"] == "jamhaul" for item in roster(load(path)))
    with pytest.raises(DraftError, match="not on the roster"):
        remove_brand(load(path), "north-room", path)


def test_saving_a_handle_keeps_the_known_page_id(tmp_path: Path):
    path = tmp_path / "state.json"
    channels = set_channels(
        empty_state(),
        "josie-blackthorn",
        {"facebook": {"handle": "josephine.blackthorn", "external_id": ""}},
        path,
    )
    facebook = next(channel for channel in channels if channel["platform"] == "facebook")
    assert facebook["external_id"] == "729680390229294"
    assert facebook["known"] is True


def _observed(hour: int, engagements: int, *, fmt: str = "unknown", source: str = "ledger") -> dict:
    return {
        "id": f"{source}-{hour}-{engagements}-{fmt}",
        "preview": "a line",
        "published_at": "2026-10-21T15:00:00+00:00",
        "local_hour": hour,
        "reactions": engagements,
        "comments": 0,
        "shares": 0,
        "engagements": engagements,
        "impressions": 0,
        "permalink": "",
        "format": fmt,
        "source": source,
    }


def test_hour_lesson_needs_a_real_gap_and_a_sample():
    from learn import engagement_rate, lessons

    posts = [_observed(10, 30) for _ in range(3)] + [_observed(20, 4) for _ in range(3)]
    found = {item["id"]: item for item in lessons(posts, [], [])}
    assert found["hour"]["clear"] is True
    assert "10:00" in found["hour"]["detail"]
    assert "n=3" in found["hour"]["detail"]
    thin = lessons([_observed(10, 10), _observed(10, 12)], [], [])
    assert thin[0]["id"] == "sample"
    assert engagement_rate(0, 9) is None


def test_format_lesson_does_not_invent_a_rate():
    from learn import lessons

    recorded = [_observed(12, 10, fmt="quote-image", source="recorded") for _ in range(3)]
    recorded += [_observed(12, 2, fmt="text", source="recorded") for _ in range(3)]
    found = {item["id"]: item for item in lessons(recorded, [], recorded)}
    assert found["format"]["clear"] is True
    assert "not an impressions rate" in found["format"]["detail"]


def test_page_trend_uses_impressions_only():
    from learn import lessons

    days = [{"date": f"2026-09-{day:02d}", "impressions": 10 if day < 8 else 40} for day in range(1, 15)]
    found = {item["id"]: item for item in lessons([], days, [])}
    assert "are up" in found["trend"]["detail"]
    assert "40" not in found["trend"]["detail"] or "against" in found["trend"]["detail"]


def test_ledger_roundtrip_and_brand_isolation(tmp_path: Path):
    from datetime import date

    from learn import parse_daily, read_ledger

    payload = {
        "posts": [
            {
                "id": "post-1",
                "message": "ghost track",
                "created_time_iso": "2026-10-14T14:02:01+0000",
                "local_hour": 10,
                "reactions": 18,
                "comments": 5,
                "shares": 6,
                "total": 29,
                "permalink": "https://www.facebook.com/example",
            }
        ],
        "insights": {"page_posts_impressions_organic": [{"date": "2026-10-21", "value": 784}]},
    }
    parsed = parse_daily(payload)
    assert list(parsed["posts"].values())[0]["published_at"].endswith("+00:00")
    (tmp_path / "2026-10-20.json").write_text(
        '{"posts":[{"id":"post-1","message":"old","total":1,"local_hour":10}]}',
        encoding="utf-8",
    )
    (tmp_path / "2026-10-21.json").write_text(
        '{"posts":[{"id":"post-1","message":"ghost track","total":29,"local_hour":10,"reactions":18,"comments":5,"shares":6}]}',
        encoding="utf-8",
    )
    merged = read_ledger(tmp_path)
    assert merged["posts"][0]["engagements"] == 29
    state = empty_state()
    view = studio(state, "misfit-mindset", merged, today=date(2026, 10, 21))
    assert view["performance"]["source"] == "none"
    assert view["performance"]["posts"] == []
    josie = studio(state, "josie-blackthorn", merged, today=date(2026, 10, 21))
    assert josie["performance"]["posts"][0]["engagements"] == 29
    assert josie["brand"]["pillars"]
    assert any(section["id"] == "performance" for section in josie["brand"]["sections"])


def test_connection_stores_a_vault_name_not_the_token(tmp_path: Path):
    seen = {}

    def writer(name, value):
        seen["name"] = name
        seen["value"] = value
        return True

    path = tmp_path / "state.json"
    saved = save_connection(
        empty_state(),
        {
            "brand_id": "jamhaul",
            "platform": "facebook",
            "external_id": "12345",
            "app_id": "999",
            "token": "fixture-token",
        },
        path,
        writer,
    )
    raw = path.read_text(encoding="utf-8")
    assert "fixture-token" not in raw
    assert "fixture-token" not in str(saved)
    assert saved["token_vault"] == "vault:house-social.jamhaul.facebook.token"
    assert seen["value"] == "fixture-token"


def test_pulled_facebook_posts_teach_what_worked(tmp_path: Path):
    from meta import facebook_posts, redact

    posts = facebook_posts(
        {
            "data": [
                {
                    "id": "1",
                    "message": "What is a haul?",
                    "created_time": "2026-10-14T14:02:01+0000",
                    "permalink_url": "https://facebook.com/p/1",
                    "shares": {"count": 2},
                    "reactions": {"summary": {"total_count": 4}},
                    "comments": {"summary": {"total_count": 1}},
                }
            ]
        }
    )
    assert posts[0]["engagements"] == 7
    assert posts[0]["local_hour"] == 10
    assert redact("https://x?access_token=abc&ok=1") == "https://x?access_token=REDACTED&ok=1"

    path = tmp_path / "state.json"
    save_connection(
        empty_state(),
        {
            "brand_id": "jamhaul",
            "platform": "facebook",
            "external_id": "12345",
            "app_id": "999",
            "token": "fixture-token",
        },
        path,
        lambda _name, _value: True,
    )

    def fetch(platform, external_id, token):
        assert token == "fixture-token"
        assert external_id == "12345"
        assert platform == "facebook"
        yes = [
            {
                "id": str(i),
                "preview": "Did you stay?",
                "engagements": 20,
                "reactions": 20,
                "comments": 0,
                "shares": 0,
                "local_hour": 10,
                "format": "unknown",
                "source": "pulled",
                "platform": "facebook",
                "published_at": "2026-10-21T14:00:00+00:00",
                "impressions": 0,
                "permalink": "",
            }
            for i in range(3)
        ]
        no = [
            {
                "id": str(i + 3),
                "preview": "The fire held through the night and into the morning after.",
                "engagements": 4,
                "reactions": 4,
                "comments": 0,
                "shares": 0,
                "local_hour": 10,
                "format": "unknown",
                "source": "pulled",
                "platform": "facebook",
                "published_at": "2026-10-20T14:00:00+00:00",
                "impressions": 0,
                "permalink": "",
            }
            for i in range(3)
        ]
        return yes + no

    result = pull_brand(
        load(path),
        "jamhaul",
        path,
        reader=lambda _name: "fixture-token",
        fetcher=fetch,
        discover=lambda _page, _token: None,
    )
    assert result["count"] == 6
    view = studio(load(path), "jamhaul")
    lessons = {item["id"]: item for item in view["lessons"]}
    assert lessons["question"]["clear"] is True
    assert len(view["feed"]) == 6
    assert "fixture-token" not in path.read_text(encoding="utf-8")


def test_facebook_page_pulls_its_instagram_account(tmp_path: Path):
    from meta import linked_instagram

    found = linked_instagram(
        {"instagram_business_account": {"id": "17841400000000001", "username": "example.brand"}}
    )
    assert found is not None
    assert found["username"] == "example.brand"
    assert linked_instagram({}) is None

    path = tmp_path / "state.json"
    save_connection(
        empty_state(),
        {
            "brand_id": "misfit-mindset",
            "platform": "facebook",
            "external_id": "111111111111111",
            "app_id": "222222222222222",
            "token": "fixture-token",
        },
        path,
        lambda _name, _value: True,
    )
    seen = []

    def fetch(platform, external_id, token):
        assert token == "fixture-token"
        seen.append((platform, external_id))
        return [
            {
                "id": f"{platform}-1",
                "preview": "a post",
                "engagements": 1,
                "reactions": 1,
                "comments": 0,
                "shares": 0,
                "local_hour": 10,
                "format": "feed" if platform == "instagram" else "unknown",
                "source": "pulled",
                "platform": platform,
                "published_at": "2026-10-21T14:00:00+00:00",
                "impressions": 0,
                "permalink": "",
            }
        ]

    pull_brand(
        load(path),
        "misfit-mindset",
        path,
        reader=lambda _name: "fixture-token",
        fetcher=fetch,
        discover=lambda page_id, _token: {"id": "17841400000000001", "username": "example.brand"}
        if page_id == "111111111111111"
        else None,
    )
    assert ("facebook", "111111111111111") in seen
    assert ("instagram", "17841400000000001") in seen
    view = studio(load(path), "misfit-mindset")
    instagram = next(item for item in view["connections"] if item["platform"] == "instagram")
    assert instagram["via"] == "facebook"
    assert instagram["username"] == "example.brand"
    assert instagram["token_vault"] == "vault:house-social.misfit-mindset.facebook.token"
    assert "fixture-token" not in path.read_text(encoding="utf-8")


def test_voice_checklist_catches_banned_lines_and_keeps_edits(tmp_path: Path):
    from voice import guide_for, voice_report

    guide = guide_for("misfit-mindset")
    hit = voice_report(guide, {"idea": "Just stay positive and the week will behave."})
    assert hit["fields"][0]["checks"][0]["ok"] is False or any(not item["ok"] for item in hit["fields"][0]["checks"])
    spoken = voice_report(guide, {"idea": "You felt the Sunday dread, and it is data, not a flaw in you."})
    assert all(item["ok"] for item in spoken["fields"][0]["checks"])
    haul = voice_report(guide_for("jamhaul"), {"idea": "Playlists drift. What do you do about it?"})
    assert any(item["id"] == "need:jamhaul.com" and item["ok"] is False for item in haul["fields"][0]["checks"])
    saved = save_voice(empty_state(), "blunt", {"tone": "Plain.", "banned": ["expires tomorrow"]}, tmp_path / "state.json")
    assert saved["tone"] == "Plain."
    assert saved["banned"] == ["expires tomorrow"]
    again = guide_for("blunt", load(tmp_path / "state.json")["voices"]["blunt"])
    assert voice_report(again, {"idea": "This file expires tomorrow."})["passed"] == 0


def test_calendar_holds_a_plan_and_counts_the_open_days(tmp_path: Path):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    path = tmp_path / "state.json"
    piece = create_piece(
        empty_state(),
        "misfit-mindset",
        "Sunday dread",
        campaign="October",
        status="planned",
        scheduled_for="2026-10-25",
        path=path,
    )
    assert piece["status"] == "planned"
    assert piece["campaign"] == "October"
    local = datetime.fromisoformat(piece["scheduled_for"]).astimezone(ZoneInfo("America/New_York"))
    assert (local.day, local.hour) == (25, 12)

    timed = update_piece(load(path), piece["id"], scheduled_for="2026-10-26T15:30:00-04:00", path=path)
    moved = update_piece(load(path), piece["id"], scheduled_for="2026-10-27", path=path)
    local = datetime.fromisoformat(moved["scheduled_for"]).astimezone(ZoneInfo("America/New_York"))
    assert (local.day, local.hour, local.minute) == (27, 15, 30)
    assert moved["status"] == "planned"
    assert timed["status"] == "planned"

    cleared = update_piece(load(path), piece["id"], clear_schedule=True, path=path)
    assert cleared["scheduled_for"] is None
    assert cleared["status"] == "planned"

    entries = calendar_entries(
        [cleared],
        [{
            "id": "1",
            "platform": "facebook",
            "preview": "Live line",
            "published_at": "2026-10-21T15:00:00+00:00",
            "format": "feed",
            "permalink": "https://example.test/p",
        }],
    )
    live = next(item for item in entries if item["lane"] == "published")
    assert live["date"] == "2026-10-21"
    assert live["draggable"] is False
    assert live["permalink"] == "https://example.test/p"
    plan = next(item for item in entries if item["kind"] == "piece")
    assert plan["lane"] == "planned"
    assert plan["date"] == ""
    assert plan["campaign"] == "October"
    span = calendar_span(entries, ["2026-10-21", "2026-10-22"])
    assert span["lanes"]["published"] == 1
    assert span["open_days"] == 1


def test_taking_a_scheduled_piece_off_the_day_keeps_it_ready(tmp_path: Path):
    path = tmp_path / "state.json"
    piece = create_piece(empty_state(), "jamhaul", "What is a haul?", path=path)
    from approval import decide, submit_review
    submit_review(load(path), piece["id"], path)
    decide(load(path), piece["id"], {"author": "Approver", "decision": "approved"}, path)
    update_piece(
        load(path),
        piece["id"],
        status="scheduled",
        scheduled_for="2026-10-22T15:00:00+00:00",
        path=path,
    )
    cleared = update_piece(load(path), piece["id"], clear_schedule=True, path=path)
    assert cleared["scheduled_for"] is None
    assert cleared["status"] == "ready"
