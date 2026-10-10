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
CSRF="$(awk '$6=="assayr_csrf"{print $7}' "$JAR")"
SLOT="$(curl -fsS -b "$JAR" "$BASE/api/v1/controls/A.5.1" | sed -n 's/.*"slots":\[{"id":"\([^"]*\)".*/\1/p')"
DOC="$(mktemp --suffix=.txt)"
printf 'Acme Financial Services\nInformation Security Policy\nVersion 1.0\nApproved by: Smoke Admin\n' > "$DOC"
LINK="$(curl -fsS -b "$JAR" -H "X-CSRF-Token: $CSRF" -F "file=@$DOC;filename=policy.txt" \
  "$BASE/api/v1/controls/A.5.1/slots/$SLOT/artefacts" | sed -n 's/^{"id":"\([^"]*\)".*/\1/p')"
state="verifying"
for _ in $(seq 1 60); do
  state="$(curl -fsS -b "$JAR" "$BASE/api/v1/artefact-links/$LINK" | sed -n 's/.*"state":"\([a-z_]*\)".*/\1/p' | head -n1)"
  [ "$state" != "verifying" ] && break
  sleep 1
done
[ "$state" != "verifying" ] || { echo "Evidence was never verified (is the worker running?)" >&2; exit 1; }
echo "Evidence verified by the worker: $state"
curl -fsS -b "$JAR" "$BASE/api/v1/risk-methodology" | grep -q '"key":"critical"' \
  || { echo "The risk methodology is missing (did assayr seed run?)" >&2; exit 1; }
soa_rows="$(curl -fsS -b "$JAR" "$BASE/api/v1/soa" | grep -o '"code":"A\.[0-9.]*"' | wc -l)"
[ "$soa_rows" -eq 93 ] || { echo "Expected 93 controls in the SoA, got $soa_rows" >&2; exit 1; }
echo "Risk methodology and SoA served"
compose exec -T api assayr audit-verify
echo "Smoke test passed: stack is up, sign-in works and 93 controls are seeded."
