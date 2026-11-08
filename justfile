# WB Sync — рецепты. Нужен just: cargo install just / brew install just
set shell := ["bash", "-uc"]

# Установка с нуля: venv -> uv -> зависимости (+ тестовый набор)
setup:
    python3 -m venv .venv
    . .venv/bin/activate && pip install -U pip uv && uv sync --extra dev

# Нюанс: just не может активировать venv в родительском шелле,
# поэтому во всех рецептах используется `uv run` — он сам использует .venv проекта.
# Для ручной работы выполняйте: source .venv/bin/activate

# --- Секреты: переменные читаются из .staff/env (папка под .gitignore) ---

test:
    set -a; . .staff/env; set +a; uv run pytest tests -v

sync d1="2026-10-01" d2="2026-10-31":
    set -a; . .staff/env; set +a; uv run wb-sync sync --date-from {{d1}} --date-to {{d2}}

cards:
    set -a; . .staff/env; set +a; uv run wb-sync cards

report d1="2026-10-01" d2="2026-10-31" out="work_dir/registry.xlsx":
    set -a; . .staff/env; set +a; uv run wb-sync report --date-from {{d1}} --date-to {{d2}} --out {{out}}

# Легаси-рецепт из старого justfile (до перехода на uv)
run-client:
    set -a; . .staff/env; set +a; echo "${API_TOKEN_IS_IMPORTED}"; \
    uv run python 'src/msp_client.py'

serve:
    set -a; . .staff/env; set +a; uv run wb-sync serve
