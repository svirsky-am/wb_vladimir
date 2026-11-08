"""Нормализация карточек WB и подготовкаpayload-ов для update/upload."""
from __future__ import annotations

import copy


def normalize_card(card: dict) -> dict:
    return {
        "nm_id": card.get("nmID"),
        "imt_id": card.get("imtID"),
        "article": card.get("vendorCode"),
        "title": card.get("title") or "",
        "brand": card.get("brand") or "",
        "raw": copy.deepcopy(card),
    }


def duplicate_card(card: dict, overrides: dict | None = None) -> dict:
    """Копия карточки с чистыми идентификаторами и заменёнными атрибутами.

    nmID/imtID убираются — новая карточка получит свои ID от WB.
    Для записи в WB используйте клиент.create_cards() (создание) или
    клиент.update_cards() (правка существующей, тогда ID оставляют).
    """
    new = copy.deepcopy(card)
    new.pop("nmID", None)
    new.pop("imtID", None)
    if overrides:
        new.update(overrides)
    return new


def card_to_upload_payload(card: dict, overrides: dict | None = None) -> dict:
    """Строит минимальный payload для POST /content/v2/cards/upload.

    Полный список обязательных характеристик зависит от предмета
    (см. GET /content/v2/object/charcs/{subjectId}) — перед созданием
    сверяйтесь с ним. Здесь собирается базовая структура.
    """
    variant = {
        "vendorCode": overrides.pop("vendorCode", card.get("vendorCode")),
        "brand": overrides.pop("brand", card.get("brand") or ""),
        "title": overrides.pop("title", card.get("title") or ""),
        "description": overrides.pop("description", ""),
    }
    characteristics = overrides.pop("characteristics", []) or []
    if characteristics:
        variant["characteristics"] = characteristics
    if overrides:
        variant.update(overrides)
    return {"cards": [{"subjectID": card.get("subjectID"), "variants": [variant]}]}
