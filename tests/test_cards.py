from wb_sync.cards import duplicate_card, set_characteristic


def test_duplicate_strips_ids():
    card = {"nmID": 123, "imtID": 9, "title": "T", "characteristics": [{"id": "x", "value": 1}]}
    dup = duplicate_card(card)
    assert "nmID" not in dup and "imtID" not in dup
    assert card["nmID"] == 123  # оригинал не тронут
    assert dup["characteristics"][0]["value"] == 1


def test_duplicate_overrides():
    dup = duplicate_card({"nmID": 1, "title": "T"}, {"title": "New"})
    assert dup["title"] == "New"
