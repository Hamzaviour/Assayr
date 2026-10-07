#!/usr/bin/env bash
# End-to-end check of the compose stack: builds, starts, signs in, counts controls, tears down.
set -euo pipefail
cd "$(dirname "$0")"
ENV_FILE="${ENV_FILE:-assayr.env}"
[ -f "$ENV_FILE" ] || cp assayr.env.example "$ENV_FILE"
compose() { docker compose --env-file "$ENV_FILE" -f compose.yaml "$@"; }
trap 'compose down -v' EXIT

compose up -d --build --wait
compose exec -T -e ASSAYR_ADMIN_PASSWORD=smoke-test-password-123 api \
  assayr create-admin --email admin@example.com --full-name "Smoke Admin"

BASE="http://localhost:${ASSAYR_HTTP_PORT:-8080}"
JAR="$(mktemp)"
curl -fsS "$BASE/api/v1/healthz" >/dev/null
curl -fsS "$BASE/" | grep -q '<div id="root">'
curl -fsS -c "$JAR" -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"smoke-test-password-123"}' "$BASE/api/v1/auth/login" >/dev/null
total="$(curl -fsS -b "$JAR" "$BASE/api/v1/controls/summary" | sed -n 's/.*"total":\([0-9]*\).*/\1/p')"
[ "$total" = "93" ] || { echo "Expected 93 controls, got $total" >&2; exit 1; }
compose exec -T api assayr audit-verify
echo "Smoke test passed: stack is up, sign-in works and 93 controls are seeded."
