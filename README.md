# wb-sync

Синхронизация данных Wildberries -> локальная SQLite -> сводные отчёты в xlsx/Google Sheets.
Подходит для подключения к Алисе AI через MCP.

## Установка

### Через venv + uv (рекомендуется)

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install uv
uv sync --extra dev          # зависимости + тестовый набор
```

`uv run <команда>` сам использует `.venv` проекта — активировать venv вручную не обязательно.
Для ручной работы: `source .venv/bin/activate`.

## Секреты

Переменные окружения хранятся в `.staff/env` (папка под `.gitignore`):

```
API_TOKEN=...                  # токен WB Партнёры
FETCH_DATA=1                   # 0 — работать только из кеша
FETCH_INTERVAL_MINUTES=30      # период фетча для службы
WB_SANDBOX=0                   # 1 — тестовый контур WB
GOOGLE_SHEET_ID=...            # опционально
GOOGLE_CREDENTIALS_FILE=...    # опционально (сервисный аккаунт Google)
```

## Использование

```bash
uv run wb-sync sync  --date-from 2026-10-01 --date-to 2026-10-31
uv run wb-sync cards
uv run wb-sync report --date-from 2026-10-01 --date-to 2026-10-31 --out work_dir/registry.xlsx
uv run wb-sync serve                 # asyncio-служба: периодический фетч по конфигу
uv run wb-sync upload-sheets --file work_dir/registry.xlsx   # требует uv sync --extra sheets
uv run pytest tests -v
```

### justfile

```bash
just setup        # venv + uv + зависимости
just test         # тесты (секреты из .staff/env)
just sync 2026-10-01 2026-10-31
just cards
just report
just serve
just run-client   # легаси-рецепт старого клиента
```

## Что где лежит

- `src/wb_sync/` — пакет; `tests/` — тесты (pytest, запуск: `uv run pytest`).
- `work_dir/` — всё изменяемое: SQLite (`wb_sync.db`), кеш выгрузок (`wb_orders_*.json`, `wb_cards.json` и т. п.),
  лог (`wb_sync.log`) и сырые ответы API в `work_dir/responses/<имя>_<timestamp>.json`.
- `AppConfig.fetch_data` (`FETCH_DATA`): `False` — обращения к API нет, работа только по кешу;
  если кеша нет — `CachedDataMissingError`.

## Задействованные эндпойнты WB API

| Метод | Домен | Назначение |
|---|---|---|
| GET /ping | common-api.wildberries.ru | проверка токена/связи |
| GET /api/v1/supplier/orders | statistics-api.wildberries.ru | заказы (цены в копейках, чанки по 30 дней) |
| GET /api/v1/supplier/sales | statistics-api.wildberries.ru | продажи (цены в копейках) |
| GET /api/v1/supplier/stocks, /incomes | statistics-api.wildberries.ru | остатки, поставки |
| POST /api/v3/orders | marketplace-api.wildberries.ru | заказы FBS с честными статусами (пагинация `next`, лимит 1000) |
| POST /content/v2/get/cards/list | content-api.wildberries.ru | карточки товаров (курсор: `limit`<=100, затем `updatedAt`+`nmID`; стоп при `total < limit`) |
| POST /content/v2/cards/update | content-api.wildberries.ru | редактирование существующих карточек |
| POST /content/v2/cards/upload | content-api.wildberries.ru | создание новых карточек (в т.ч. дубликатов) |

### Песочница

Тестовый контур существует — `WB_SANDBOX=1` переключает все хосты на `*-api-sandbox.wildberries.ru`
(например, `content-api-sandbox.wildberries.ru`). Нужен токен с опцией «Тестовый контур» в WB Партнёры.
Данные в песочнице случайные и не связаны с реальным кабинетом; лимит — 1 запрос/секунду суммарно;
карточка создаётся сразу, без очереди. Полный список: https://dev.wildberries.ru/sandbox

### Лимиты

- statistics-api: до 30 дней на один запрос (учтено в `chunk_periods`), при 429 — ретраи с backoff.
- content-api: максимум 100 карточек на запрос (`limit` больше отклоняется с HTTP 400).

### Дублирование карточек

`cards.duplicate_card(card, overrides)` копирует карточку с чистыми `nmID`/`imtID`.
Для записи в WB: `update_cards()` — правка существующей; `create_cards()` (`/content/v2/cards/upload`) —
создание новой. Перед созданием сверяйтесь с обязательными характеристиками предмета:
`GET /content/v2/object/parent/all` -> `GET /content/v2/object/all` -> `GET /content/v2/object/charcs/{subjectId}`.

## Google Sheets

`uv sync --extra sheets`, затем создайте сервисный аккаунт в Google Cloud, включите Sheets API,
выдайте аккаунту доступ (editor) к таблице. Проверка: `just report` + `uv run wb-sync upload-sheets --file work_dir/registry.xlsx`.

## MCP (подключение к Алисе AI)

`src/wb_sync/mcp_server.py` — инструменты: `ping_wb`, `sync_data_tool`, `sync_cards_tool`,
`build_registry_report_tool`, `build_summary_tool`, `upload_report_to_sheets_tool`.
Локально: `MCP_TRANSPORT=stdio uv run python -m wb_sync.mcp_server`.
В AI Studio: Agent Atelier -> MCP-серверы -> подключить внешний (Streamable HTTP).

Инструменты записи карточек (`update_cards`/`create_cards`) в MCP **не выведены** намеренно —
изменение каталога WB это критическое действие, выполняйте вручную.

## Следующие шаги (план)

1. Сервер в Yandex Cloud (VM или Serverless Containers), `systemd`-юнит на `wb-sync serve`.
2. MCP-сервер зарегистрировать в MCP Hub (AI Studio), подключить к Алисе AI Про для бизнеса.
3. Аналитики строят сводные отчёты естественным языком; отчёты уезжают в Google Sheets.
