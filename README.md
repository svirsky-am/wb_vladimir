# wb-sync

Выгрузка отчётов Wildberries → SQLite (SQLAlchemy) → xlsx-реестры. MCP-сервер для Алисы AI / AI Studio.

## Структура

```
src/wb_sync/        # пакет (src-layout)
  app_config.py     # AppConfig: work_dir, API_TOKEN, fetch_data, fetch_interval_minutes
  logging_setup.py  # лог в work_dir/wb_sync.log (ротация)
  wb_api.py         # statistics-api v1 + marketplace-api /api/v3/orders, кеш в work_dir
  db.py             # SQLite: orders, sales, fbs_orders (апсерт по уникальному ключу)
  core.py           # sync_data / build_registry_report — общая логика
  reports.py        # xlsx: «Реестр», «По дням», «По артикулам»
  service.py        # asyncio-служба: цикл фетча по расписанию, SIGINT/SIGTERM
  mcp_server.py     # MCP-инструменты для агента
  main.py           # CLI: wb-sync sync|report|all|serve
tests/              # тесты — в корне репозитория, рядом с src/ (стандарт src-layout)
```

## Установка (uv)

```bash
uv sync --extra dev          # создаёт .venv, ставит зависимости из pyproject.toml
```

Зависимости заданы в `pyproject.toml` (`[project.dependencies]` + группа dev для pytest/pytest-asyncio). Файл `uv.lock` появится после первого `uv sync` — комитьте его для воспроизводимости.

## Запуск

```bash
export API_TOKEN=...
uv run wb-sync sync --date-from 2026-10-01 --date-to 2026-10-31
uv run wb-sync report --date-from 2026-10-01 --date-to 2026-10-31 --out registry.xlsx
uv run wb-sync serve                                   # служба, интервал — fetch_interval_minutes
uv run wb-sync serve --no-fetch                        # не понадобится: serve всегда фетчит
MCP_TRANSPORT=streamable-http uv run wb-sync-mcp       # или: uv run python -m wb_sync.mcp_server
```

## Тесты

Тесты кладём в **`tests/` в корне репозитория** — так принято в src-layout: пакет в `src/`, тесты отдельно, путь задаётся `testpaths` в `pyproject.toml`.

```bash
uv run pytest tests -v
```

## Конфиг (переменные окружения)

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `API_TOKEN` | — | токен WB (обязателен) |
| `FETCH_DATA` | `1` | `0` — работать только по кешу в work_dir |
| `FETCH_INTERVAL_MINUTES` | `30` | период цикла службы |
| `WORK_DIR` | `work_dir` | кеш, SQLite, лог, отчёты |

## Логи

Все события (циклы фетча, ошибки, путь отчёта) пишутся в `work_dir/wb_sync.log`, ротация 5 МБ × 5 файлов.
