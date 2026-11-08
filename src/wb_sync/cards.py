"""Дублирование карточек WB с заменой атрибутов."""

import copy


def duplicate_card(card: dict, overrides: dict) -> dict:
    """Глубокая копия карточки с чистыми идентификаторами и оверрайдами.

    nmID/imtID обнуляются — новая карточка получит их от WB.
    Оверрайды (overrides) заменяют/добавляют значения атрибутов и характеристик.
    """
    new_card = copy.deepcopy(card)
    new_card.pop("nmID", None)
    new_card.pop("imtID", None)
    new_card.pop("id", None)

    if overrides.get("vendorCode"):
        new_card["vendorCode"] = overrides["vendorCode"]
    if overrides.get("title"):
        new_card["title"] = overrides["title"]
    if overrides.get("description"):
        new_card["description"] = overrides["description"]

    for extra in overrides.get("characteristics", []):
        found = False
        for ch in new_card.get("characteristics", []):
            if ch.get("id") == extra.get("id"):
                ch["value"] = extra["value"]
                found = True
                break
        if not found:
            new_card.setdefault("characteristics", []).append(dict(extra))
    return new_card


def card_to_upload_payload(card: dict) -> dict:
    """Формат для POST /content/v2/cards/upload."""
    return {
        "subjectID": card.get("subjectID"),
        "variants": [card],
    }
