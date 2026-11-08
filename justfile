# Переменные окружения (в том числе секретные) из .staff/env — папка в .gitignore
set dotenv-load := false

setup:
    python3 -m venv .venv
    . .venv/bin/activate && pip install uv && uv sync --extra dev

test:
    set -a; . .staff/env; set +a; uv run pytest tests -v

sync *args:
    set -a; . .staff/env; set +a; uv run wb-sync sync {{args}}

cards:
    set -a; . .staff/env; set +a; uv run wb-sync cards

report *args:
    set -a; . .staff/env; set +a; uv run wb-sync report {{args}}

serve:
    set -a; . .staff/env; set +a; uv run wb-sync serve

# Легаси-запуск исходного клиента
run-client:
    set -a; . .staff/env; set +a; python3 src/msp_client.py
