# wb-sync

Выгрузка данных Wildberries (v1 statistics, /api/v3/orders FBS, карточки) в SQLite
и построение сводных xlsx-отчётов.

## Зависимости и установка (uv)

    python3 -m venv .venv
    . .venv/bin/activate
    pip install uv

    uv sync --extra dev          # зависимости + dev (pytest)
    uv sync --extra sheets       # + выгрузка в Google Sheets

## Запуск

    just test        # тесты
    just sync        # выгрузка за окно из конфига
    just report      # xlsx-реестр
    just cards       # карточки товаров
    just serve       # asyncio-служба (фетч по FETCH_INTERVAL_MINUTES)

Секреты и переменные — в .staff/env (в .gitignore): API_TOKEN, FETCH_DATA,
FETCH_INTERVAL_MINUTES, WB_SANDBOX, GOOGLE_SHEET_ID, GOOGLE_CREDENTIALS_FILE.

## Задействованные эндпоинты WB

| Метод | Эндпоинт | Назначение |
|---|---|---|
| GET | https://statistics-api.wildberries.ru/api/v1/supplier/orders | Заказы (v1), лимит 30 дней на запрос, пагинация rrdid/limit |
| GET | https://statistics-api.wildberries.ru/api/v1/supplier/sales | Выкупы (v1) |
| GET | https://statistics-api.wildberries.ru/api/v1/supplier/incomes | Поставки (v1) |
| GET | https://statistics-api.wildberries.ru/api/v1/supplier/stocks | Остатки (v1) |
| GET | https://marketplace-api.wildberries.ru/api/v3/orders | Сборочные задания FBS (v3): query-параметры limit (<=1000), next, dateFrom/dateTo (Unix-сек), окно до 30 дней |
| POST | https://content-api.wildberries.ru/content/v2/get/cards/list | Карточки: курсорная пагинация (limit<=100, копировать updatedAt+nmID) |
| POST | https://content-api.wildberries.ru/content/v2/cards/update | Редактирование существующих карточек |
| POST | https://content-api.wildberries.ru/content/v2/cards/upload | Создание новых карточек (для дублей — upload, не update) |
| GET | https://common-api.wildberries.ru/ping | Проверка доступности |

**Sandbox**: при WB_SANDBOX=1 все хосты переключаются на `*-api-sandbox.wildberries.ru`
(например, `content-api-sandbox.wildberries.ru`). Требуется токен с опцией
«Тестовый контур» в WB Партнёры; лимит — 1 запрос/секунду.

## Логирование

Лог: `work_dir/wb_sync.log` (ротация 5 МБ x 5) + консоль.

- INFO: каждая попытка запроса — успех («GET … → 200 (12.3 КБ, 0.42 с)») и неуспех
  (с кодом HTTP, номером попытки и началом тела ответа);
- INFO: паузы между ретраями (Retry-After или экспоненциальный backoff);
- ERROR: окончательная неудача после исчерпания ретраев;
- INFO: результаты циклов службы и синхронизации.

Сырые ответы API сохраняются в `work_dir/responses/<имя>_<временная_метка>.json`.

## Google Sheets

Сервисный аккаунт Google с доступом editor к таблице; в .staff/env:
`GOOGLE_SHEET_ID` и `GOOGLE_CREDENTIALS_FILE`. Запуск: `uv run wb-sync upload-sheets --file work_dir/registry.xlsx`.

## Тесты

Тесты в `tests/` в корне репозитория (src-layout). Запуск: `just test`.
