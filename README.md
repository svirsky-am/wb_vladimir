# wb-sync

Выгрузка данных Wildberries в SQLite и xlsx-реестры; MCP-сервер для AI Studio / Алисы AI Про.

## Установка

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install uv
just setup          # uv sync --extra dev --extra sheets
```

## Эндпойнты WB

| Хост | Метод и путь | Что делает |
|---|---|---|
| common-api.wildberries.ru | GET /ping | Проверка доступности (используется перед стартом службы) |
| statistics-api.wildberries.ru | GET /api/v1/supplier/orders | Заказы (окно ≤ 30 дней, чанкуется) |
| statistics-api.wildberries.ru | GET /api/v1/supplier/sales | Продажи |
| statistics-api.wildberries.ru | GET /api/v1/supplier/incomes | Поставки |
| statistics-api.wildberries.ru | GET /api/v1/supplier/stocks | Остатки |
| statistics-api.wildberries.ru | GET /api/v1/supplier/warehouses | Склады |
| marketplace-api.wildberries.ru | GET /api/v3/orders | FBS-заказы со статусами (limit ≤ 1000, пагинация next, окно ≤ 30 дней) |
| content-api.wildberries.ru | POST /content/v2/get/cards/list | Карточки (курсорная пагинация, limit ≤ 100) |
| content-api.wildberries.ru | POST /content/v2/cards/update | Редактирование существующих карточек |
| content-api.wildberries.ru | POST /content/v2/cards/upload | Создание карточек (в т.ч. дубликаты) |

## Песочница

`WB_SANDBOX=1` переключает все хосты на `*-api-sandbox.wildberries.ru`
(например, `content-api-sandbox.wildberries.ru`). Нужен токен с опцией
«Тестовый контур» в WB Партнёры; лимит — 1 запрос/секунду суммарно.

## Запуск

```bash
just ping           # проверить доступность WB
just sync           # выгрузка всех данных (пул потоков, FETCH_WORKERS)
just report         # xlsx-реестр за текущий месяц
just cards          # синхронизация карточек
just serve          # служба: ping -> цикл sync каждые FETCH_INTERVAL_MINUTES минут
just upload-sheets --file work_dir/registry_....xlsx   # выгрузка в Google Sheets
```

## Конфигурация (.staff/env)

- `API_TOKEN` — токен WB (обязателен);
- `FETCH_DATA` — 0: работать только из кеша, без сети;
- `FETCH_INTERVAL_MINUTES` — пауза службы;
- `FETCH_WORKERS` — размер пула (по умолчанию 3);
- `MIN_REQUEST_INTERVAL`, `MAX_RETRIES`, `RETRY_BASE_DELAY` — троттлинг и ретраи;
- `WB_SANDBOX` — 1: песочница;
- `GOOGLE_SHEET_ID`, `GOOGLE_CREDENTIALS_FILE` — Google Sheets.

Все сырые ответы API сохраняются в `work_dir/responses/<label>_<timestamp>.json`,
лог — `work_dir/wb_sync.log` (ротация 5 МБ × 5).

## MCP

`src/wb_sync/mcp_server.py` — инструменты: `ping_wb_tool`, `sync_data_tool`,
`build_registry_report_tool`, `build_summary_tool`. Регистрируется в MCP Hub AI Studio
(транспорт streamable-http) или запускается локально.

## Тесты

```bash
just test
```
