"""A piece posts only when posting is on, it is approved, and its time has come."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import publish  # noqa: E402
from adapt import DraftError  # noqa: E402
from approval import decide, submit_review  # noqa: E402
from publish import blockers, check_posting, delete_test, publish_piece, run_due, send_test_post, set_posting  # noqa: E402
from store import create_piece, empty_state, load, save, save_apps, save_connection, studio, update_piece  # noqa: E402

NOW = datetime(2026, 10, 24, 18, 0, tzinfo=timezone.utc)
IDEA = "The fire held. The night did not."
TOKENS = {
    "house-social.okay.facebook.token": "page-token",
    "house-social.okay.instagram.token": "page-token",
    "house-social.okay.threads.token": "threads-token",
    "house-social.meta.app_secret": "meta-fixture",
}


class FakeMeta:
    def __init__(self, fail=None, scopes=None):
        self.calls = []
        self.fail = fail or set()
        self.scopes = scopes

    def __call__(self, method, url, params=None, files=None):
        self.calls.append((method, url.split("?")[0].replace("https://graph.facebook.com/v25.0", "fb").replace("https://graph.threads.net/v1.0", "th"), dict(params or {}), bool(files)))
        short = self.calls[-1][1]
        for name in self.fail:
            if name in short:
                raise publish.PostError("Meta said (400): nope")
        if method == "POST" and short == "fb/111/feed":
            return {"id": "111_900"}
        if method == "POST" and short == "fb/111/photos":
            return {"id": "photo-1", "post_id": "111_901"} if params.get("published") != "false" else {"id": "photo-2"}
        if short in {"fb/photo-1", "fb/photo-2"}:
            return {"images": [{"source": "https://cdn.example/small.jpg", "width": 100}, {"source": "https://cdn.example/big.jpg", "width": 900}]}
        if method == "POST" and short == "fb/178/media":
            return {"id": "ig-container"}
        if short == "fb/ig-container":
            return {"status_code": "FINISHED"}
        if method == "POST" and short == "fb/178/media_publish":
            return {"id": "ig-1"}
        if method == "POST" and short == "th/9/threads":
            return {"id": "th-container"}
        if short == "th/th-container":
            return {"status": "FINISHED"}
        if method == "POST" and short == "th/9/threads_publish":
            return {"id": "th-1"}
        if method == "GET" and short in {"fb/111_900", "fb/111_901", "fb/ig-1", "th/th-1"}:
            return {"permalink_url": "https://facebook.example/p", "permalink": "https://example/p"}
        if short == "fb/debug_token":
            return {"data": {"is_valid": True, "scopes": self.scopes or ["pages_manage_posts", "instagram_content_publish"]}}
        if short == "fb/178/content_publishing_limit":
            return {"data": [{"quota_usage": 2, "config": {"quota_total": 100}}]}
        if short == "th/9/threads_publishing_limit":
            return {"data": [{"quota_usage": 1, "config": {"quota_total": 250}}]}
        if method == "DELETE":
            return {"success": True}
        raise AssertionError((method, short))


def _brand(tmp_path: Path, platforms=("facebook", "instagram", "threads")) -> Path:
    path = tmp_path / "state.json"
    save_apps(empty_state(), {"meta": {"app_id": "100000000000001", "secret": "meta-fixture"}, "threads": {"app_id": "200000000000002", "secret": "threads-fixture"}}, path, lambda _n, _v: True)
    ids = {"facebook": "111", "instagram": "178", "threads": "9"}
    for platform in platforms:
        save_connection(load(path), {"brand_id": "okay", "platform": platform, "external_id": ids[platform], "token": "fixture-token"}, path, lambda _n, _v: True)
    return path


def _approved(path: Path, when: datetime | None = None) -> str:
    piece = create_piece(load(path), "okay", IDEA, path=path)
    if when:
        update_piece(load(path), piece["id"], scheduled_for=when.isoformat(), path=path)
    submit_review(load(path), piece["id"], path)
    decide(load(path), piece["id"], {"author": "Approver", "decision": "approved"}, path)
    return piece["id"]


def _scheduled(path: Path, when: datetime) -> str:
    piece_id = _approved(path)
    update_piece(load(path), piece_id, scheduled_for=when.isoformat(), status="scheduled", path=path)
    return piece_id


def _on(path: Path) -> None:
    set_posting(load(path), {"on": True}, path)
    set_posting(load(path), {"brand_id": "okay", "on": True}, path)


def _piece(path: Path, piece_id: str) -> dict:
    return next(item for item in load(path)["pieces"] if item["id"] == piece_id)


def test_nothing_posts_until_the_house_and_the_brand_turn_posting_on(tmp_path: Path):
    path = _brand(tmp_path)
    piece_id = _scheduled(path, NOW - timedelta(minutes=5))
    fake = FakeMeta()
    assert run_due(load(path), path, reader=TOKENS.get, http=fake, now=NOW)["posted"] == []
    assert fake.calls == []
    set_posting(load(path), {"on": True}, path)
    reasons = blockers(load(path), _piece(path, piece_id), NOW)
    assert any("off for this brand" in item for item in reasons)
    assert studio(load(path), "okay")["posting"] is False
    set_posting(load(path), {"brand_id": "okay", "on": True}, path)
    assert studio(load(path), "okay")["posting"] is True


def test_a_due_piece_posts_to_facebook_and_threads_and_skips_instagram_without_an_image(tmp_path: Path):
    path = _brand(tmp_path)
    _on(path)
    later = _scheduled(path, NOW + timedelta(hours=1))
    piece_id = _scheduled(path, NOW - timedelta(minutes=2))
    fake = FakeMeta()
    result = run_due(load(path), path, reader=TOKENS.get, http=fake, now=NOW, sleep=lambda _s: None)
    assert [row["id"] for row in result["posted"]] == [piece_id]
    piece = _piece(path, piece_id)
    assert piece["status"] == "published"
    assert piece["posted"] is True
    assert set(piece["published"]) == {"facebook", "threads"}
    assert any("Instagram needs an image" in row["detail"] for row in piece["publish_log"])
    feed = next(call for call in fake.calls if call[1] == "fb/111/feed")
    assert feed[2]["message"] == IDEA
    assert _piece(path, later)["status"] == "scheduled"
    raw = path.read_text(encoding="utf-8")
    assert "page-token" not in raw and "threads-token" not in raw
    assert any("posted to Facebook and Threads" in item["text"] for item in load(path)["notices"])
    with pytest.raises(DraftError, match="already posted"):
        update_piece(load(path), piece_id, status="draft", path=path)
    again = run_due(load(path), path, reader=TOKENS.get, http=FakeMeta(), now=NOW + timedelta(minutes=1))
    assert again["posted"] == []


def test_an_image_posts_on_facebook_and_feeds_instagram_and_threads_the_page_copy(tmp_path: Path):
    from library import record_use, save_asset
    import base64

    path = _brand(tmp_path)
    _on(path)
    root = tmp_path / "assets"
    png = base64.b64encode(bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000")).decode()
    asset = save_asset(load(path), "okay", {"kind": "image", "name": "card", "data": png}, path, root)
    piece_id = _scheduled(path, NOW - timedelta(minutes=1))
    record_use(load(path), asset["id"], {"piece_id": piece_id}, path)
    fake = FakeMeta()
    run_due(load(path), path, reader=TOKENS.get, http=fake, now=NOW, sleep=lambda _s: None, root=root)
    piece = _piece(path, piece_id)
    assert set(piece["published"]) == {"facebook", "instagram", "threads"}
    photo = next(call for call in fake.calls if call[1] == "fb/111/photos")
    assert photo[3] is True
    media = next(call for call in fake.calls if call[1] == "fb/178/media")
    assert media[2]["image_url"] == "https://cdn.example/big.jpg"
    threads = next(call for call in fake.calls if call[1] == "th/9/threads")
    assert threads[2]["media_type"] == "IMAGE"


def test_a_failed_platform_can_be_retried_without_posting_twice(tmp_path: Path):
    path = _brand(tmp_path, ("facebook", "threads"))
    _on(path)
    piece_id = _scheduled(path, NOW - timedelta(minutes=1))
    run_due(load(path), path, reader=TOKENS.get, http=FakeMeta(fail={"th/9/threads"}), now=NOW, sleep=lambda _s: None)
    piece = _piece(path, piece_id)
    assert piece["status"] == "failed"
    assert "Posted to Facebook" in piece["failure"]
    assert "Threads" in piece["failure"]
    fake = FakeMeta()
    done = publish_piece(load(path), piece_id, path, reader=TOKENS.get, http=fake, now=NOW, sleep=lambda _s: None, immediate=True)
    assert done["status"] == "published"
    assert not any(call[1] == "fb/111/feed" for call in fake.calls)
    assert set(_piece(path, piece_id)["published"]) == {"facebook", "threads"}


def test_late_placeholder_and_unapproved_pieces_do_not_post(tmp_path: Path):
    path = _brand(tmp_path)
    _on(path)
    late = _scheduled(path, NOW - timedelta(hours=9))
    fake = FakeMeta()
    result = run_due(load(path), path, reader=TOKENS.get, http=fake, now=NOW)
    assert result["late"] == [late]
    assert fake.calls == []
    assert "did not post late" in _piece(path, late)["failure"]
    draft = create_piece(load(path), "okay", IDEA, path=path)
    reasons = blockers(load(path), _piece(path, draft["id"]), NOW, immediate=True)
    assert any("approval" in item for item in reasons)
    held = _scheduled(path, NOW - timedelta(minutes=1))
    state = load(path)
    next(item for item in state["pieces"] if item["id"] == held)["placeholder"] = True
    save(state, path)
    result = run_due(load(path), path, reader=TOKENS.get, http=FakeMeta(), now=NOW)
    assert result["waiting"][0]["id"] == held
    assert any("placeholder" in item for item in result["waiting"][0]["reasons"])
    update_piece(load(path), held, variants={"threads": {"body": "Written by a person."}}, path=path)
    assert "placeholder" not in _piece(path, held)


def test_approving_a_piece_with_a_future_time_schedules_it(tmp_path: Path):
    path = _brand(tmp_path)
    future = datetime.now(timezone.utc) + timedelta(days=2)
    piece_id = _approved(path, future)
    assert _piece(path, piece_id)["status"] == "scheduled"
    assert any("scheduled for" in item["text"] for item in load(path)["notices"])
    plain = _approved(path)
    assert _piece(path, plain)["status"] == "approved"


def test_check_posting_leaves_nothing_visible_and_names_a_missing_permission(tmp_path: Path):
    path = _brand(tmp_path)
    fake = FakeMeta()
    checked = check_posting(load(path), "okay", path, reader=TOKENS.get, http=fake)
    rows = {row["platform"]: row for row in checked["rows"]}
    assert all(row["ok"] for row in rows.values())
    hidden = next(call for call in fake.calls if call[1] == "fb/111/feed")
    assert hidden[2]["published"] == "false"
    assert any(call[0] == "DELETE" and call[1] == "fb/111_900" for call in fake.calls)
    assert "2 of 100" in rows["instagram"]["detail"]
    view = studio(load(path), "okay")["publishing"]["accounts"]
    assert view["threads"]["can_post"] is True
    narrow = check_posting(load(path), "okay", path, reader=TOKENS.get, http=FakeMeta(scopes=["pages_show_list"]))
    rows = {row["platform"]: row for row in narrow["rows"]}
    assert rows["facebook"]["ok"] is False
    assert "connect again" in rows["facebook"]["detail"]
    assert studio(load(path), "okay")["publishing"]["accounts"]["facebook"]["can_post"] is False


def test_a_test_post_is_real_and_can_be_deleted_where_meta_allows(tmp_path: Path):
    path = _brand(tmp_path)
    fake = FakeMeta()
    made = send_test_post(load(path), "okay", {"platforms": ["facebook", "instagram", "threads"], "text": "Testing."}, path, reader=TOKENS.get, http=fake, sleep=lambda _s: None)
    rows = {row["platform"]: row for row in made["rows"]}
    assert rows["facebook"]["ok"] and rows["threads"]["ok"]
    assert rows["instagram"]["ok"] is False
    assert "needs an image" in rows["instagram"]["detail"]
    tests = studio(load(path), "okay")["publishing"]["tests"]
    facebook = next(item for item in tests if item["platform"] == "facebook")
    delete_test(load(path), facebook["id"], path, reader=TOKENS.get, http=fake)
    assert any(call[0] == "DELETE" and call[1] == "fb/111_900" for call in fake.calls)
    with pytest.raises(DraftError, match="already deleted"):
        delete_test(load(path), facebook["id"], path, reader=TOKENS.get, http=fake)
    with pytest.raises(DraftError, match="https"):
        send_test_post(load(path), "okay", {"platforms": ["facebook"], "image_url": "http://plain.example/a.jpg"}, path, reader=TOKENS.get, http=fake)


def test_two_runs_cannot_post_the_same_piece(tmp_path: Path):
    path = _brand(tmp_path, ("facebook",))
    _on(path)
    piece_id = _scheduled(path, NOW - timedelta(minutes=1))
    state = load(path)
    next(item for item in state["pieces"] if item["id"] == piece_id)["claimed_at"] = NOW.isoformat()
    save(state, path)
    with pytest.raises(DraftError, match="already posting"):
        publish_piece(load(path), piece_id, path, reader=TOKENS.get, http=FakeMeta(), now=NOW + timedelta(minutes=1))
    with publish._file_lock(path) as held:
        assert held is True
        assert publish.tick(path) is None


def test_a_piece_that_only_skips_is_not_called_posted(tmp_path: Path):
    path = _brand(tmp_path, ("instagram",))
    _on(path)
    piece_id = _scheduled(path, NOW - timedelta(minutes=1))
    done = publish_piece(load(path), piece_id, path, reader=TOKENS.get, http=FakeMeta(), now=NOW)
    assert done["status"] == "failed"
    assert "needs an image" in _piece(path, piece_id)["failure"]
    assert _piece(path, piece_id)["posted"] is False


def test_an_unexpected_error_keeps_what_already_posted(tmp_path: Path):
    path = _brand(tmp_path, ("facebook", "threads"))
    _on(path)
    piece_id = _scheduled(path, NOW - timedelta(minutes=1))
    fake = FakeMeta()

    def flaky(method, url, params=None, files=None):
        if "graph.threads.net" in url:
            raise KeyError("boom")
        return fake(method, url, params, files)

    done = publish_piece(load(path), piece_id, path, reader=TOKENS.get, http=flaky, now=NOW)
    piece = _piece(path, piece_id)
    assert done["status"] == "failed"
    assert set(piece["published"]) == {"facebook"}
    assert "hit an error" in piece["failure"]
    assert piece["claimed_at"] == ""
