#import? ".staff/env"

run-client:
    set -a; . .staff/env; set +a; echo "${API_TOKEN_IS_IMPORTED}"; \
    python3 'src/msp_client.py'
#    echo '${API_TOKEN}'
#    @echo "HOME is: '${HOME}' '${API_TOKEN}'"

run-client:
    set -a; . .staff/env; set +a; echo "${API_TOKEN_IS_IMPORTED}"; \
    python -m pytest tests -v'
