#!/usr/bin/env bash
# Development end-to-end check: builds the images from source, starts the stack, runs the
# smoke checks and tears everything down.
set -euo pipefail
cd "$(dirname "$0")"
ENV_FILE="${ENV_FILE:-assayr.env}"
[ -f "$ENV_FILE" ] || cp assayr.env.example "$ENV_FILE"
compose() { docker compose --env-file "$ENV_FILE" -f compose.yaml -f compose.build.yaml "$@"; }
trap 'compose down -v' EXIT

compose up -d --build --wait
compose exec -T -e ASSAYR_ADMIN_PASSWORD=smoke-test-password-123 api \
  assayr create-admin --email admin@example.com --full-name "Smoke Admin"
./smoke-checks.sh "http://localhost:${ASSAYR_HTTP_PORT:-8080}" admin@example.com smoke-test-password-123
compose exec -T api assayr audit-verify
echo "Smoke test passed: stack is up, sign-in works and 93 controls are seeded."
