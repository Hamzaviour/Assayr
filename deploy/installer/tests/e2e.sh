#!/usr/bin/env bash
# End-to-end test of real bundles on a Linux machine with Docker. Run as root:
#   sudo deploy/installer/tests/e2e.sh BUNDLE.tar.gz NEXT_BUNDLE_DIR BROKEN_BUNDLE_DIR
# NEXT is a newer version that works; BROKEN is a newer version whose API never starts.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
tarball="$1"
next="$2"
broken="$3"
work="$(mktemp -d)"
dir="$work/install dir" # a space on purpose: every path must be quoted
EMAIL=admin@example.com
PASSWORD=e2e-test-password-123
BASE=https://localhost:8443
JAR="$work/cookies"
export ASSAYR_HOSTNAME=localhost ASSAYR_ORG_NAME="E2E Org" ASSAYR_ADMIN_EMAIL="$EMAIL" ASSAYR_ADMIN_PASSWORD="$PASSWORD"

cleanup() {
  local status=$?
  if [ "$status" -ne 0 ] && [ -f "$dir/assayr.env" ]; then diagnostics; fi
  if [ -f "$dir/assayr" ]; then "$dir/assayr" uninstall --delete-data --yes >/dev/null 2>&1 || true; fi
  rm -rf "$work"
}
# diagnostics — what the containers were doing when a step failed.
diagnostics() {
  local files=(-f "$dir/compose.yaml")
  if [ -f "$dir/compose.https.yaml" ]; then files+=(-f "$dir/compose.https.yaml"); fi
  echo "--- containers" >&2
  docker compose --project-directory "$dir" --env-file "$dir/assayr.env" "${files[@]}" --profile av ps -a >&2 || true
  echo "--- container logs (last 60 lines each)" >&2
  docker compose --project-directory "$dir" --env-file "$dir/assayr.env" "${files[@]}" --profile av logs --tail 60 >&2 || true
  echo "--- install.log (last 80 lines)" >&2
  tail -n 80 "$dir/install.log" >&2 || true
}
trap cleanup EXIT

step() { printf '\n=== %s\n' "$*"; }
fail() {
  echo "FAILED: $*" >&2
  if [ -f "$dir/install.log" ]; then tail -n 60 "$dir/install.log" >&2; fi
  exit 1
}
# expect_failure TEXT COMMAND... — COMMAND must fail and print TEXT.
expect_failure() {
  local text="$1" out="$work/out"
  shift
  if "$@" >"$out" 2>&1; then
    cat "$out"
    fail "expected failure: $*"
  fi
  grep -qF "$text" "$out" || {
    cat "$out"
    fail "expected the message: $text"
  }
}
sign_in() {
  rm -f "$JAR"
  curl -kfsS -c "$JAR" -H 'Content-Type: application/json' \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" "$BASE/api/v1/auth/login" >/dev/null
}
create_risk() {
  local csrf
  csrf="$(awk '$6=="assayr_csrf"{print $7}' "$JAR")"
  curl -kfsS -b "$JAR" -H "X-CSRF-Token: $csrf" -H 'Content-Type: application/json' \
    -d "{\"title\":\"$1\"}" "$BASE/api/v1/risks" >/dev/null
}
risk_count() {
  curl -kfsS -b "$JAR" "$BASE/api/v1/risks" | grep -o '"code":"R-[0-9]*"' | wc -l | tr -d ' '
}

tar -C "$work" -xzf "$tarball"
bundle="$(find "$work" -mindepth 1 -maxdepth 1 -type d -name 'assayr-*' | head -n 1)"
next_version="$(cat "$next/VERSION")"

step "A modified bundle is refused before anything changes"
cp -R "$bundle" "$work/modified"
echo "# changed" >>"$work/modified/compose.yaml"
expect_failure "damaged or was modified" \
  "$work/modified/assayr" install --dir "$dir" --non-interactive --https-port 8443 --http-port 8080
[ ! -e "$dir" ] || fail "the modified bundle created $dir"
rm -rf "$work/modified"

step "Install"
"$bundle/assayr" install --dir "$dir" --non-interactive --https-port 8443 --http-port 8080
"$REPO/deploy/smoke-checks.sh" "$BASE" "$EMAIL" "$PASSWORD"
code="$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/)"
[ "$code" = 308 ] || fail "plain HTTP should redirect to HTTPS (got $code)"
"$dir/assayr" status

step "Installing twice is refused"
expect_failure "already installed" "$bundle/assayr" install --dir "$dir" --non-interactive

step "Backup and restore"
sign_in
create_risk "Before the backup"
"$dir/assayr" backup --to "$work/backups"
backup_file="$(find "$work/backups" -name 'assayr-*.tar.gz' | head -n 1)"
[ -n "$backup_file" ] || fail "no backup was written"
create_risk "After the backup"
[ "$(risk_count)" = 2 ] || fail "expected 2 risks before the restore"
"$dir/assayr" restore "$backup_file" --yes
sign_in
[ "$(risk_count)" = 1 ] || fail "expected 1 risk after the restore"

step "Upgrade keeps the data"
"$next/assayr" upgrade --dir "$dir"
"$dir/assayr" version | grep -q "Assayr $next_version " || fail "the version did not change to $next_version"
sign_in
[ "$(risk_count)" = 1 ] || fail "data was lost in the upgrade"
"$REPO/deploy/smoke-checks.sh" "$BASE" "$EMAIL" "$PASSWORD"

step "A failing upgrade is rolled back"
sed -i 's/^ASSAYR_WAIT_TIMEOUT=.*/ASSAYR_WAIT_TIMEOUT=120/' "$dir/assayr.env"
expect_failure "rolled back to $next_version" "$broken/assayr" upgrade --dir "$dir"
"$dir/assayr" version | grep -q "Assayr $next_version " || fail "the version changed despite the rollback"
sign_in
[ "$(risk_count)" = 1 ] || fail "data was lost in the rollback"

step "End-to-end test passed"
