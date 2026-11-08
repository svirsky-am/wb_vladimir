"""Карточки: дублирование и payload для update/upload."""
import copy


def duplicate_card(card: dict, overrides: dict | None = None) -> dict:
    """Глубокая копия карточки с чистыми nmID/imtID и оверрайдами полей."""
    c = copy.deepcopy(card)
    c.pop("nmID", None)
    c.pop("imtID", None)
    for ch in c.get("characteristics", []):
        ch.pop("id", None)
    if overrides:
        c.update(overrides)
    return c


def card_to_upload_payload(cards: list[dict]) -> dict:
    return {"cards": cards}


def set_characteristic(card: dict, name: str, value) -> dict:
    for ch in card.get("characteristics", []):
        if ch.get("id") == name or ch.get("name") == name:
            ch["value"] = value
            return card
    card.setdefault("characteristics", []).append({"id": name, "value": value})
    return card
