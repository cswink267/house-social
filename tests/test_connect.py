"""A brand connects by signing in with the house app and picking its accounts."""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import connect  # noqa: E402
from adapt import DraftError  # noqa: E402
from connect import cancel_choice, choose_accounts, disconnect, finish_connect, read_choice, start_connect  # noqa: E402
from store import empty_state, load, pull_brand, save_apps, save_connection, studio  # noqa: E402

REDIRECT = "https://desk.example/house-social"
META_ID = "100000000000001"
THREADS_ID = "200000000000002"


def _house(tmp_path: Path) -> Path:
    path = tmp_path / "state.json"
    save_apps(
        empty_state(),
        {"meta": {"app_id": META_ID, "secret": "meta-fixture"}, "threads": {"app_id": THREADS_ID, "secret": "threads-fixture"}},
        path,
        lambda _name, _value: True,
    )
    return path


def _vault(name):
    return {"house-social.meta.app_secret": "meta-fixture", "house-social.threads.app_secret": "threads-fixture"}.get(name)


class FakeMeta:
    def __init__(self):
        self.calls = []

    def __call__(self, method, url, params):
        self.calls.append((method, url, dict(params or {})))
        if url.endswith("/oauth/access_token") and "graph.facebook.com" in url:
            if params.get("grant_type") == "fb_exchange_token":
                assert params["fb_exchange_token"] == "short-user"
                return {"access_token": "long-user"}
            assert params["code"] == "fixture-code"
            assert params["redirect_uri"] == REDIRECT
            assert params["client_secret"] == "meta-fixture"
            return {"access_token": "short-user"}
        if url.endswith("/me/permissions"):
            return {"data": [
                {"permission": "pages_show_list", "status": "granted"},
                {"permission": "pages_manage_posts", "status": "granted"},
                {"permission": "instagram_content_publish", "status": "declined"},
            ]}
        if url.endswith("/me/accounts"):
            assert params["access_token"] == "long-user"
            return {
                "data": [
                    {
                        "id": "111",
                        "name": "Okay",
                        "username": "okaypage",
                        "category": "Brand",
                        "access_token": "page-token-a",
                        "instagram_business_account": {"id": "178001", "username": "okay.ig"},
                    },
                    {"id": "222", "name": "Other Page", "access_token": "page-token-b"},
                ],
                "paging": {"next": "https://graph.facebook.com/v25.0/me/accounts?after=x"},
            }
        if "after=x" in url:
            return {
                "data": [
                    {
                        "id": "333",
                        "name": "Third Page",
                        "access_token": "page-token-c",
                        "instagram_business_account": {"id": "178003", "username": "third.ig"},
                    }
                ]
            }
        if url == "https://graph.threads.net/oauth/access_token":
            assert method == "POST"
            assert params["grant_type"] == "authorization_code"
            assert params["client_id"] == THREADS_ID
            return {"access_token": "short-threads", "user_id": "9"}
        if url == "https://graph.threads.net/access_token":
            assert params["grant_type"] == "th_exchange_token"
            assert params["access_token"] == "short-threads"
            return {"access_token": "long-threads", "expires_in": 5184000}
        if url.endswith("graph.threads.net/v1.0/me"):
            return {"id": "9", "username": "okay.threads", "name": "Okay"}
        raise AssertionError(url)


def _start(path: Path, provider: str, brand: str = "okay", clock=None) -> str:
    started = start_connect(load(path), brand, provider, REDIRECT + "?code=old#_=_", path, clock=clock)
    query = parse_qs(urlparse(started["url"]).query)
    assert query["redirect_uri"] == [REDIRECT]
    assert started["sending"] is False
    return query["state"][0]


def test_meta_connect_picks_the_page_and_instagram_and_keeps_tokens_out_of_state(tmp_path: Path):
    path = _house(tmp_path)
    started = start_connect(load(path), "okay", "meta", REDIRECT, path)
    url = urlparse(started["url"])
    query = parse_qs(url.query)
    assert url.netloc == "www.facebook.com"
    assert query["client_id"] == [META_ID]
    assert "pages_show_list" in query["scope"][0]
    assert "pages_manage_posts" in query["scope"][0]
    assert "instagram_content_publish" in query["scope"][0]
    nonce = query["state"][0]

    fake = FakeMeta()
    found = finish_connect(load(path), nonce, "fixture-code", path, reader=_vault, http=fake)
    assert found["provider"] == "meta"
    assert [page["id"] for page in found["pages"]] == ["111", "222", "333"]
    assert {item["id"]: item["page_id"] for item in found["instagram"]} == {"178001": "111", "178003": "333"}
    assert "page-token" not in str(found)
    assert "page-token" not in path.read_text(encoding="utf-8")
    assert read_choice(load(path), found["choice"])["pages"][0]["name"] == "Okay"
    assert [page["likely"] for page in found["pages"]] == [True, False, False]

    written = {}

    def writer(name, value):
        written[name] = value
        return True

    saved = choose_accounts(load(path), found["choice"], {"page_id": "111", "instagram_id": "178003"}, path, writer)
    assert written == {
        "house-social.okay.facebook.token": "page-token-a",
        "house-social.okay.instagram.token": "page-token-c",
    }
    raw = path.read_text(encoding="utf-8")
    assert "page-token" not in raw and "long-user" not in raw and "fixture-code" not in raw
    assert "page-token" not in str(saved)
    view = studio(load(path), "okay")
    rows = {item["platform"]: item for item in view["connections"]}
    assert rows["facebook"]["external_id"] == "111"
    assert rows["facebook"]["name"] == "Okay"
    assert rows["facebook"]["app_id"] == META_ID
    assert rows["instagram"]["external_id"] == "178003"
    assert rows["instagram"]["page_id"] == "333"
    assert rows["instagram"]["via"] == "login"
    stored = {item["platform"]: item for item in load(path)["connections"]}
    assert "pages_manage_posts" in stored["facebook"]["scopes"]
    assert "instagram_content_publish" not in stored["instagram"]["scopes"]
    accounts = view["publishing"]["accounts"]
    assert accounts["facebook"]["can_post"] is True
    assert accounts["instagram"]["can_post"] is False
    channels = {item["platform"]: item for item in view["brand"]["channels"]}
    assert channels["instagram"]["handle"] == "third.ig"
    assert channels["facebook"]["external_id"] == "111"
    with pytest.raises(DraftError, match="expired or was already saved"):
        choose_accounts(load(path), found["choice"], {"page_id": "111"}, path, writer)
    with pytest.raises(DraftError, match="already used"):
        finish_connect(load(path), nonce, "fixture-code", path, reader=_vault, http=fake)


def test_threads_connect_saves_the_signed_in_account(tmp_path: Path):
    path = _house(tmp_path)
    nonce = _start(path, "threads")
    found = finish_connect(load(path), nonce, "fixture-code", path, reader=_vault, http=FakeMeta())
    assert found["threads"]["username"] == "okay.threads"
    assert found["expires_at"]
    written = {}
    choose_accounts(load(path), found["choice"], {}, path, lambda name, value: written.update({name: value}) or True)
    assert written == {"house-social.okay.threads.token": "long-threads"}
    row = next(item for item in studio(load(path), "okay")["connections"] if item["platform"] == "threads")
    assert row["app_id"] == THREADS_ID
    assert row["username"] == "okay.threads"
    assert row["expires_at"].startswith("20")
    assert "long-threads" not in path.read_text(encoding="utf-8")


def test_connect_needs_the_house_app_first_and_a_real_sign_in(tmp_path: Path):
    path = tmp_path / "state.json"
    with pytest.raises(DraftError, match="House settings"):
        start_connect(empty_state(), "okay", "meta", REDIRECT, path)
    save_apps(empty_state(), {"meta": {"app_id": META_ID}}, path, lambda _name, _value: True)
    with pytest.raises(DraftError, match="app secret under House settings"):
        start_connect(load(path), "okay", "meta", REDIRECT, path)
    path = _house(tmp_path)
    with pytest.raises(DraftError, match="Connect uses"):
        start_connect(load(path), "okay", "tiktok", REDIRECT, path)
    with pytest.raises(DraftError, match="address"):
        start_connect(load(path), "okay", "meta", "javascript:alert(1)", path)
    with pytest.raises(DraftError, match="unknown"):
        finish_connect(load(path), "made-up", "fixture-code", path, reader=_vault, http=FakeMeta())
    nonce = _start(path, "meta", clock=lambda: 1000)
    with pytest.raises(DraftError, match="30 minutes"):
        finish_connect(load(path), nonce, "fixture-code", path, reader=_vault, http=FakeMeta(), clock=lambda: 1000 + 31 * 60)
    nonce = _start(path, "meta")
    with pytest.raises(DraftError, match="not in the vault"):
        finish_connect(load(path), nonce, "fixture-code", path, reader=lambda _name: None, http=FakeMeta())


def test_a_failed_vault_write_saves_no_connection(tmp_path: Path):
    path = _house(tmp_path)
    nonce = _start(path, "meta")
    found = finish_connect(load(path), nonce, "fixture-code", path, reader=_vault, http=FakeMeta())
    with pytest.raises(DraftError, match="did not reach the vault"):
        choose_accounts(load(path), found["choice"], {"page_id": "111"}, path, lambda _name, _value: False)
    assert studio(load(path), "okay")["connections"] == []
    with pytest.raises(DraftError, match="Pick a Facebook Page"):
        choose_accounts(load(path), found["choice"], {}, path, lambda _name, _value: True)
    with pytest.raises(DraftError, match="not in this sign-in"):
        choose_accounts(load(path), found["choice"], {"instagram_id": "999"}, path, lambda _name, _value: True)
    cancel_choice(found["choice"])
    with pytest.raises(DraftError, match="expired"):
        read_choice(load(path), found["choice"])


def test_meta_errors_never_echo_a_secret():
    assert "meta-fixture" not in connect.scrub("client_secret=meta-fixture&code=abc&access_token=xyz")
    said = connect._said('{"error": {"message": "Invalid redirect_uri. access_token=xyz"}}', 400)
    assert "xyz" not in said
    assert "Invalid redirect_uri" in said


def test_disconnect_forgets_the_page_and_what_it_found(tmp_path: Path):
    path = _house(tmp_path)
    nonce = _start(path, "meta")
    found = finish_connect(load(path), nonce, "fixture-code", path, reader=_vault, http=FakeMeta())
    choose_accounts(load(path), found["choice"], {"page_id": "111"}, path, lambda _name, _value: True)
    pull_brand(
        load(path), "okay", path,
        reader=lambda _name: "page-token-a",
        fetcher=lambda _platform, _external, _token: [],
        discover=lambda _page, _token: {"id": "178001", "username": "okay.ig"},
    )
    assert {item["platform"] for item in studio(load(path), "okay")["connections"]} == {"facebook", "instagram"}
    disconnect(load(path), "okay", "instagram", path)
    pull_brand(
        load(path), "okay", path,
        reader=lambda _name: "page-token-a",
        fetcher=lambda _platform, _external, _token: [],
        discover=lambda _page, _token: {"id": "178001", "username": "okay.ig"},
    )
    assert {item["platform"] for item in studio(load(path), "okay")["connections"]} == {"facebook"}
    gone = disconnect(load(path), "okay", "facebook", path)
    assert gone["vault"] == "vault:house-social.okay.facebook.token"
    assert studio(load(path), "okay")["connections"] == []
    with pytest.raises(DraftError, match="not connected"):
        disconnect(load(path), "okay", "facebook", path)


def test_a_chosen_instagram_account_survives_a_pull(tmp_path: Path):
    path = _house(tmp_path)
    for platform, external in (("facebook", "111"), ("instagram", "178003")):
        save_connection(
            load(path),
            {"brand_id": "okay", "platform": platform, "external_id": external, "token": "fixture-token"},
            path,
            lambda _name, _value: True,
        )
    seen = []
    pull_brand(
        load(path), "okay", path,
        reader=lambda _name: "fixture-token",
        fetcher=lambda platform, external, _token: seen.append((platform, external)) or [],
        discover=lambda _page, _token: {"id": "178001", "username": "okay.ig"},
    )
    assert ("instagram", "178003") in seen
    assert ("instagram", "178001") not in seen
    instagram = next(item for item in studio(load(path), "okay")["connections"] if item["platform"] == "instagram")
    assert instagram["external_id"] == "178003"
