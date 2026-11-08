"""Клиент WB API: v1 statistics, /api/v3/orders (FBS), контент (карточки).

Все обращения к API логируются: INFO — каждая попытка (успешная и неуспешная),
ERROR — окончательная неудача после ретраев. Сырые ответы сохраняются в
work_dir/responses/<имя>_<временная_метка>.json.
"""

import json
import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

logger = logging.getLogger("wb_sync.wb_api")

STATUS_RU = {
    "new": "Ожидает сборки",
    "confirm": "Готов к отгрузке",
    "complete": "Доставляется",
    "sent_to_carrier": "Доставляется",
    "delivered": "Доставлен",
    "cancel": "Отменен",
    "cancellation": "Отменен",
}

H = "https://{host}"


class CachedDataMissingError(RuntimeError):
    """Кеш в work_dir не найден, а fetch_data=False."""


def _host(base: str, sandbox: bool) -> str:
    return base if not sandbox else base.replace(".wildberries.ru", "-api-sandbox.wildberries.ru")


def normalize_v3_status(row: dict) -> str:
    statuses = row.get("statuses") or {}
    supplier = (statuses.get("supplierStatus") or "").strip().lower()
    if supplier in STATUS_RU:
        return STATUS_RU[supplier]
    wb = (statuses.get("wbStatus") or "").strip().lower()
    if wb in STATUS_RU:
        return STATUS_RU[wb]
    return "Готов к отгрузке"


def chunk_periods(date_from: date, date_to: date, window_days: int):
    """Разбивает период на чанки не длиннее window_days (включительно)."""
    if date_from > date_to:
        raise ValueError("date_from позже date_to")
    chunks = []
    start = date_from
    while start <= date_to:
        end = min(start + timedelta(days=window_days - 1), date_to)
        chunks.append((start, end))
        start = end + timedelta(days=1)
    return chunks


def _cache_name(prefix: str, d_from: date, d_to: date) -> str:
    return f"{prefix}_{d_from.isoformat()}_{d_to.isoformat()}.json"


class WBClient:
    statistics_base = "statistics-api.wildberries.ru"
    marketplace_base = "marketplace-api.wildberries.ru"
    content_base = "content-api.wildberries.ru"
    common_base = "common-api.wildberries.ru"

    def __init__(self, config):
        self.config = config
        self._session = requests.Session()
        self._session.headers.update(
            {"Authorization": config.api_token, "Accept": "application/json"}
        )
        self._last_request_at = 0.0

    # ----- низкий уровень: логирование, троттлинг, ретраи -----
    def _throttle(self):
        interval = getattr(self.config, "min_request_interval", 1.0)
        wait = self._last_request_at + interval - time.monotonic()
        if wait > 0:
            logger.info("Троттлинг: пауза %.1f с перед следующим запросом", wait)
            time.sleep(wait)
        self._last_request_at = time.monotonic()

    def _save_response(self, method: str, url: str, payload):
        responses_dir = self.config.work_dir / "responses"
        responses_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        safe = url.replace("https://", "").replace("/", "_").replace("?", "_").replace("=", "_").replace("&", "_").replace(".", "_")
        name = f"{method}_{safe}_{stamp}.json"
        with open(responses_dir / name, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return responses_dir / name

    def request(self, method: str, url: str, *, params=None, json_body=None):
        """Запрос с логированием попыток и ретраями на 429/5xx.

        Логи:
          INFO  — каждая попытка (успех и неуспех);
          ERROR — окончательная неудача.
        Пауза между ретраями: Retry-After, иначе экспоненциальный backoff.
        """
        max_retries = getattr(self.config, "max_retries", 5)
        base_delay = getattr(self.config, "retry_base_delay", 5.0)
        attempt = 0
        while True:
            attempt += 1
            self._throttle()
            started = time.monotonic()
            try:
                resp = self._session.request(
                    method, url, params=params, json=json_body, timeout=60
                )
            except requests.RequestException as exc:
                logger.info(
                    "Попытка %d/%d %s %s — сетевая ошибка: %s",
                    attempt, max_retries + 1, method, url, exc,
                )
                if attempt > max_retries:
                    logger.error("Сетевые ошибки исчерпаны: %s %s", method, url)
                    raise
                delay = base_delay * (2 ** (attempt - 1))
                logger.info("Пауза %.0f с перед повторной попыткой", delay)
                time.sleep(delay)
                continue

            elapsed = time.monotonic() - started
            size = len(resp.content) if resp.content else 0

            if resp.status_code < 400:
                logger.info(
                    "%s %s → %s (%.1f КБ, %.2f с) — попытка %d",
                    method, url, resp.status_code, size / 1024, elapsed, attempt,
                )
                return resp

            retryable = resp.status_code == 429 or resp.status_code >= 500
            logger.info(
                "Попытка %d/%d %s %s — HTTP %s (%.2f с): %s",
                attempt, max_retries + 1, method, url,
                resp.status_code, elapsed, resp.text[:300],
            )
            if not retryable or attempt > max_retries:
                logger.error(
                    "Запрос не удался окончательно: %s %s — HTTP %s",
                    method, url, resp.status_code,
                )
                resp.raise_for_status()
                return resp

            retry_after = resp.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                delay = float(retry_after)
            else:
                delay = base_delay * (2 ** (attempt - 1))
            logger.info(
                "HTTP %s: пауза %.0f с перед попыткой %d/%d",
                resp.status_code, delay, attempt + 1, max_retries + 1,
            )
            time.sleep(delay)

    # ----- кеш -----
    def _cache_path(self, prefix: str, d_from: date, d_to: date) -> Path:
        return self.config.work_dir / _cache_name(prefix, d_from, d_to)

    def _fetch_or_cache(self, prefix, d_from, d_to, fetcher):
        """fetch_data=True — обращаемся к API и обновляем снапшот,
        иначе читаем кеш; нет кеша — CachedDataMissingError."""
        cache = self._cache_path(prefix, d_from, d_to)
        if self.config.fetch_data:
            payload = fetcher()
            with open(cache, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return payload
        if not cache.exists():
            raise CachedDataMissingError(
                f"Кеш {cache.name} не найден, а fetch_data=False. "
                f"Запустите sync с FETCH_DATA=1."
            )
        logger.info("Кеш: %s", cache.name)
        with open(cache, "r", encoding="utf-8") as f:
            return json.load(f)

    # ----- v1 statistics -----
    def _v1(self, endpoint: str, d_from: date, d_to: date):
        url = H.format(host=_host(self.statistics_base, self.config.sandbox)) + endpoint
        rows = []
        for c_from, c_to in chunk_periods(d_from, d_to, self.config.fetch_window_days):
            params = {
                "dateFrom": c_from.isoformat(),
                "dateTo": c_to.isoformat(),
                "rrdid": 0,
                "limit": 100000,
            }
            resp = self.request("GET", url, params=params)
            rows.extend(resp.json())
        return rows

    def get_orders(self, d_from: date, d_to: date):
        return self._fetch_or_cache(
            "wb_orders", d_from, d_to,
            lambda: self._v1("/api/v1/supplier/orders", d_from, d_to),
        )

    def get_sales(self, d_from: date, d_to: date):
        return self._fetch_or_cache(
            "wb_sales", d_from, d_to,
            lambda: self._v1("/api/v1/supplier/sales", d_from, d_to),
        )

    def get_incomes(self, d_from: date, d_to: date):
        return self._fetch_or_cache(
            "wb_incomes", d_from, d_to,
            lambda: self._v1("/api/v1/supplier/incomes", d_from, d_to),
        )

    def get_stocks(self):
        def _fetch():
            url = H.format(host=_host(self.statistics_base, self.config.sandbox))
            return self.request("GET", url + "/api/v1/supplier/stocks").json()
        if self.config.fetch_data:
            payload = _fetch()
            path = self.config.work_dir / "wb_stocks.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return payload
        path = self.config.work_dir / "wb_stocks.json"
        if not path.exists():
            raise CachedDataMissingError("Кеш wb_stocks.json не найден, а fetch_data=False")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    # ----- v3 FBS orders: GET с query-параметрами, пагинация через next -----
    def get_v3_orders(self, d_from: date, d_to: date):
        url = H.format(host=_host(self.marketplace_base, self.config.sandbox))
        url += "/api/v3/orders"

        def _fetch():
            rows = []
            next_cursor = 0
            for c_from, c_to in chunk_periods(d_from, d_to, self.config.fetch_window_days):
                next_cursor = 0
                while True:
                    params = {
                        "limit": 1000,
                        "next": next_cursor,
                        "dateFrom": int(datetime.combine(c_from, datetime.min.time()).timestamp()),
                        "dateTo": int(datetime.combine(c_to, datetime.max.time()).timestamp()),
                    }
                    resp = self.request("GET", url, params=params)
                    data = resp.json()
                    rows.extend(data.get("orders", []))
                    next_cursor = data.get("next", 0)
                    if not next_cursor:
                        break
            return rows

        return self._fetch_or_cache("wb_v3_orders", d_from, d_to, _fetch)

    # ----- карточки -----
    def get_cards(self):
        url = H.format(host=_host(self.content_base, self.config.sandbox))
        url += "/content/v2/get/cards/list"

        def _fetch():
            cards, cursor = [], {"limit": 100}
            while True:
                resp = self.request("POST", url, json_body={"settings": cursor})
                data = resp.json()
                batch = data.get("data", {}).get("cards", [])
                cards.extend(batch)
                total = data.get("data", {}).get("total", 0)
                if not batch or total < cursor["limit"] or len(cards) >= total:
                    break
                cursor = {
                    "limit": 100,
                    "updatedAt": batch[-1].get("updatedAt"),
                    "nmID": batch[-1].get("nmID"),
                }
            return cards

        return self._fetch_or_cache("wb_cards", date(2000, 1, 1), date.today(), _fetch)

    def update_cards(self, cards_payload: list):
        url = H.format(host=_host(self.content_base, self.config.sandbox))
        url += "/content/v2/cards/update"
        resp = self.request("POST", url, json_body={"data": cards_payload})
        return resp.json()

    def create_cards(self, cards_payload: list):
        url = H.format(host=_host(self.content_base, self.config.sandbox))
        url += "/content/v2/cards/upload"
        resp = self.request("POST", url, json_body={"data": cards_payload})
        return resp.json()

    def ping(self):
        url = H.format(host=_host(self.common_base, self.config.sandbox)) + "/ping"
        return self.request("GET", url).json()
