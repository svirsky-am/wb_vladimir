# Секреты из .staff/env подхватываются в каждом рецепте.

setup:
    python3 -m venv .venv
    . .venv/bin/activate && pip install uv
    set -a; . .staff/env; set +a; uv sync --extra dev --extra sheets

test:
    set -a; . .staff/env; set +a; uv run pytest tests -v

ping:
    set -a; . .staff/env; set +a; uv run wb-sync ping

sync:
    set -a; . .staff/env; set +a; uv run wb-sync sync

cards:
    set -a; . .staff/env; set +a; uv run wb-sync cards

report:
    set -a; . .staff/env; set +a; uv run wb-sync report

serve:
    set -a; . .staff/env; set +a; uv run wb-sync serve

upload-sheets FILE:
    set -a; . .staff/env; set +a; uv run wb-sync upload-sheets --file {{FILE}}

run-client:
    set -a; . .staff/env; set +a; echo "${API_TOKEN_IS_IMPORTED}"; \
    python3 'src/msp_client.py'
