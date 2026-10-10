#!/usr/bin/env bash
# Installer checks: shellcheck on every script, then the bats unit tests in this folder.
# CI sets ASSAYR_REQUIRE_SHELLCHECK=1; locally shellcheck is skipped with a warning when missing.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
cd "$REPO"

scripts=(
  deploy/installer/assayr
  deploy/installer/tests/run.sh
  deploy/installer/tests/e2e.sh
  deploy/installer/tests/clamav-offline.sh
  deploy/installer/tests/stubs/docker
  deploy/smoke.sh
  deploy/smoke-checks.sh
  scripts/build-bundle.sh
)
present=()
for script in "${scripts[@]}"; do
  if [ -f "$script" ]; then present+=("$script"); fi
done

if command -v shellcheck >/dev/null 2>&1; then
  shellcheck -x "${present[@]}"
  echo "shellcheck: ${#present[@]} scripts clean"
elif [ "${ASSAYR_REQUIRE_SHELLCHECK:-0}" = 1 ]; then
  echo "shellcheck is required but not installed" >&2
  exit 1
else
  echo "Warning: shellcheck is not installed; skipping it (CI runs it)." >&2
fi

if command -v bats >/dev/null 2>&1; then
  bats "$HERE"
else
  npx --yes bats@1.11.1 "$HERE"
fi
