#!/usr/bin/env bash
# Checks a running Assayr from the outside: sign-in, 93 controls, an evidence upload verified by
# the worker, the risk methodology and the SoA.
# Usage: smoke-checks.sh BASE_URL EMAIL PASSWORD   (BASE_URL like https://localhost:8443)
set -euo pipefail
BASE="${1:?base URL, for example https://localhost:8443}"
EMAIL="${2:?administrator email}"
PASSWORD="${3:?administrator password}"
CURL=(curl -fsS)
case "$BASE" in https://*) CURL+=(-k) ;; esac # the installer's default certificate is self-signed
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
JAR="$work/cookies"

"${CURL[@]}" "$BASE/api/v1/healthz" >/dev/null
"${CURL[@]}" "$BASE/" | grep -q '<div id="root">'
"${CURL[@]}" -c "$JAR" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" "$BASE/api/v1/auth/login" >/dev/null
total="$("${CURL[@]}" -b "$JAR" "$BASE/api/v1/controls/summary" | sed -n 's/.*"total":\([0-9]*\).*/\1/p')"
[ "$total" = "93" ] || { echo "Expected 93 controls, got $total" >&2; exit 1; }

CSRF="$(awk '$6=="assayr_csrf"{print $7}' "$JAR")"
SLOT="$("${CURL[@]}" -b "$JAR" "$BASE/api/v1/controls/A.5.1" | sed -n 's/.*"slots":\[{"id":"\([^"]*\)".*/\1/p')"
printf 'Acme Financial Services\nInformation Security Policy\nVersion 1.0\nApproved by: Smoke Admin\n' >"$work/policy.txt"
LINK="$("${CURL[@]}" -b "$JAR" -H "X-CSRF-Token: $CSRF" -F "file=@$work/policy.txt;filename=policy.txt" \
  "$BASE/api/v1/controls/A.5.1/slots/$SLOT/artefacts" | sed -n 's/^{"id":"\([^"]*\)".*/\1/p')"
state="verifying"
for _ in $(seq 1 90); do
  state="$("${CURL[@]}" -b "$JAR" "$BASE/api/v1/artefact-links/$LINK" | sed -n 's/.*"state":"\([a-z_]*\)".*/\1/p' | head -n1)"
  [ "$state" != "verifying" ] && break
  sleep 1
done
[ "$state" != "verifying" ] || { echo "Evidence was never verified (is the worker running?)" >&2; exit 1; }
echo "Evidence verified by the worker: $state"

"${CURL[@]}" -b "$JAR" "$BASE/api/v1/risk-methodology" | grep -q '"key":"critical"' \
  || { echo "The risk methodology is missing (did assayr seed run?)" >&2; exit 1; }
soa_rows="$("${CURL[@]}" -b "$JAR" "$BASE/api/v1/soa" | grep -o '"code":"A\.[0-9.]*"' | wc -l | tr -d ' ')"
[ "$soa_rows" -eq 93 ] || { echo "Expected 93 controls in the SoA, got $soa_rows" >&2; exit 1; }
echo "Smoke checks passed against $BASE"
