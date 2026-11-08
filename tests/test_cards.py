import json

import pytest

from wb_sync import wb_api, cards as cards_mod
from wb_sync.app_config import AppConfig
from tests.test_wb_api import FakeResponse, FakeSession


def make_config(tmp_path, **kw):
    return AppConfig(work_dir=str(tmp_path), api_token="tok", **kw)


def test_cards_cursor_pagination(tmp_path):
    cfg = make_config(tmp_path)
    page1 = {"data": {"cards": [
        {"nmID": 1, "vendorCode": "A1", "brand": "B", "title": "T1", "imtID": 10},
    ], "cursor": {"updatedAt": "2026-01-01T00:00:00Z", "nmID": 1, "total": 100}}}
    page2 = {"data": {"cards": [
        {"nmID": 2, "vendorCode": "A2", "brand": "B", "title": "T2", "imtID": 10},
    ], "cursor": {"updatedAt": "2026-01-02T00:00:00Z", "nmID": 2, "total": 1}}}
    session = FakeSession([FakeResponse(page1), FakeResponse(page2)])
    client = wb_api.WBClient(cfg, session=session)
    cards = client.get_cards()
    assert [c["nmID"] for c in cards] == [1, 2]
    # второй запрос передал курсор первой страницы
    second_payload = session.calls[1][2]["settings"]["cursor"]
    assert second_payload["nmID"] == 1
    assert "updatedAt" in second_payload


def test_cards_cached_no_api(tmp_path):
    cfg = make_config(tmp_path)
    page = {"data": {"cards": [{"nmID": 5, "vendorCode": "X"}], "cursor": {"total": 1}}}
    client = wb_api.WBClient(cfg, session=FakeSession([FakeResponse(page)]))
    client.get_cards()
    cfg2 = make_config(tmp_path)
    cfg2.fetch_data = False
    client2 = wb_api.WBClient(cfg2, session=FakeSession([]))
    assert client2.get_cards()[0]["nmID"] == 5


def test_responses_saved_with_timestamp(tmp_path):
    cfg = make_config(tmp_path)
    page = {"data": {"cards": [{"nmID": 5, "vendorCode": "X"}], "cursor": {"total": 1}}}
    client = wb_api.WBClient(cfg, session=FakeSession([FakeResponse(page)]))
    client.get_cards()
    files = list((tmp_path / "responses").glob("api_content-api.wildberries.ru_content_v2_get_cards_list_*.json"))
    assert files, "сырой ответ должен сохраняться в work_dir/responses с временной меткой"


def test_duplicate_card_strips_ids():
    card = {"nmID": 42, "imtID": 7, "vendorCode": "MC12", "title": "Пылесос"}
    dup = cards_mod.duplicate_card(card, {"vendorCode": "MC12_v2", "title": "Пылесос v2"})
    assert "nmID" not in dup and "imtID" not in dup
    assert dup["vendorCode"] == "MC12_v2"
    assert card["nmID"] == 42  # оригинал не тронут


def test_update_and_create_save_responses(tmp_path):
    cfg = make_config(tmp_path)
    session = FakeSession([FakeResponse({"ok": True}), FakeResponse({"ok": True})])
    client = wb_api.WBClient(cfg, session=session)
    client.update_cards({"imtID": 7, "cards": [{"nmID": 42, "title": "new"}]})
    client.create_cards({"cards": [{"subjectID": 1, "variants": [{"vendorCode": "V1"}]}]})
    assert any(p.name.startswith("api_content-api") for p in (tmp_path / "responses").iterdir())


def test_sandbox_urls(tmp_path):
    cfg = make_config(tmp_path, sandbox=True)
    client = wb_api.WBClient(cfg, session=FakeSession([]))
    assert client.content_base == "https://content-api-sandbox.wildberries.ru"
    assert client.stat_base == "https://statistics-api-sandbox.wildberries.ru"
    assert client.market_base == "https://marketplace-api-sandbox.wildberries.ru"
