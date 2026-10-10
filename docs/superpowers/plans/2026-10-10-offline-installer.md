# Assayr Offline Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Assayr as two offline bundles (`linux-amd64`, `linux-arm64`) built and tested by GitHub Actions, each carrying one bash command, `./assayr`, that installs, serves HTTPS, upgrades with automatic rollback, backs up and restores Assayr on Linux servers (production) and on macOS / Windows-WSL with Docker Desktop (evaluation).

**Architecture:** The installer is a bash 3.2-compatible program in `deploy/installer/`: an entry script that sources small libraries (`lib/*.sh`, one responsibility each) and dispatches commands. It drives `docker compose` with the production compose file (`deploy/compose.yaml`, image tags only) plus an HTTPS override. `scripts/build-bundle.sh` saves the images and writes checksums; `.github/workflows/release.yml` builds both architectures, runs an end-to-end test against the real bundle (install → smoke → backup/restore → upgrade → forced rollback), and publishes a GitHub Release on version tags. Unit tests use `bats` with a recording `docker` stub.

**Tech Stack:** bash 3.2+, Docker Engine + Compose v2.17+, Caddy 2 (existing web image), openssl, bats-core 1.11, shellcheck, GitHub Actions (`ubuntu-24.04`, `ubuntu-24.04-arm`, `macos-14`).

**Spec:** `docs/superpowers/specs/2026-10-10-offline-installer-design.md` (approved 2026-10-10). Vault: NFR-OPS-1, ADR-001, `06-Architecture/Deployment On-Prem.md`.

**Refinements of the spec made while planning (each is the smallest change that keeps the spec's intent):**
- The two Caddy configurations are baked into the web image (`/etc/caddy/Caddyfile` and `Caddyfile.https`, sharing `site.caddy`) and chosen by the compose HTTPS override, instead of shipping as loose files in the bundle. One less thing to copy and keep in sync; the bundle still contains everything needed.
- Third-party images are pinned by tag in `compose.yaml` (`postgres:16-alpine`, `clamav/clamav:1.4`); the exact image IDs are recorded in the bundle's `images/IMAGES.txt`. `docker load` does not reliably restore registry digests, so the compose file can't reference images by digest.
- The bundle gains an `ARCH` file (`amd64`/`arm64`) next to `VERSION`, read by the architecture check.
- Backups carry `manifest.txt` (`version=`, `created=`) plus `SHA256SUMS` instead of `manifest.json`: plain bash has no JSON parser, and the same checksum code verifies bundles and backups.
- `restore` restores data (database + evidence files). The `assayr.env`, `certs/` and `license/` copies inside a backup are for disaster recovery by hand: putting back an old `assayr.env` would break the database password of a fresh installation.
- In the install folder, `VERSION` is written last during an upgrade, and a leftover `.previous/` folder (an upgrade that was interrupted) is put back before a new upgrade starts. This makes an interrupted upgrade safe to re-run.
- ClamAV offline: a release gate (`clamav-offline.sh`) fails the build unless the pinned ClamAV image contains a virus database and starts with networking disabled. If that gate ever fails, adding a database snapshot to the bundle (the spec's fallback) becomes a follow-up task; no speculative code for it now.
- In HTTP mode the default HTTP port is 8080; in HTTPS mode the HTTP port (redirect only) defaults to 80.

## Global Constraints

- **Commit messages carry no `Co-Authored-By` or any Claude attribution** — the user is the only contributor (standing instruction).
- Every installer script runs on **bash 3.2** (macOS default): no associative arrays, no `${var,,}`/`${var^^}`, no `mapfile`/`readarray`, no `|&`, no negative substring offsets; empty arrays are expanded as `${arr[@]+"${arr[@]}"}`. Use `printf -v` and `${!name}` for indirection, never `eval`.
- Works with GNU and BSD tools: `sha256sum` or `shasum -a 256`; never `sed -i` (except in the Linux-only e2e test); `mktemp` always with a template or `-d`; `df -P`; `tar -czf/-xzf`.
- Every script starts with `set -euo pipefail` (entry points) or `# shellcheck shell=bash` (libraries) and passes `shellcheck -x` with no warnings.
- Secrets (database password, admin password, private keys) are never printed, never put on a command line, never written to `install.log`. Pass the admin password to the container with `docker compose exec -e ASSAYR_ADMIN_PASSWORD` (name only) from a subshell that exports it.
- Files: `assayr.env`, `install.log`, `certs/tls.key`, `license/assayr.lic`, backups → mode 600; `backups/`, `license/` → mode 700.
- Install folders: Linux `/opt/assayr` (root required); macOS and WSL `~/assayr` (normal user).
- Compose project name stays `assayr`; volumes `assayr_dbdata` and `assayr_blobs` keep their names, so data survives upgrades. PostgreSQL stays on major version 16 (a major change needs its own migration path, out of scope).
- Version strings are `MAJOR.MINOR.PATCH` digits only; tags are `v<version>`.
- User-facing messages: plain sentences saying what happened and what to do next; sentence case; "licence" (noun) as in the rest of the product copy.
- Line endings: the repo's `.gitattributes` (`* text=auto eol=lf`) already keeps scripts LF; do not add CRLF exceptions for anything under `deploy/` or `scripts/`.
- No new runtime dependencies for the application. Test-only tools: `bats` (via `npx --yes bats@1.11.1` locally when not installed) and `shellcheck` (required in CI; skipped with a warning locally when missing).
- Local commands start with `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh` (the C: drive is nearly full; this redirects caches). Docker Desktop is installed on the dev machine but usually stopped; tests that need a running daemon skip themselves, and the end-to-end test runs in GitHub Actions.

## Review Focus

- An install folder or bundle path containing spaces (`/srv/my apps/assayr`, `~/Downloads/assayr bundles/`) must work for every command → Task 4 (`install works in a folder whose path has spaces`), Task 7 e2e installs into `install dir`.
- An organisation name or hostname containing `$`, quotes, `#` or a backslash must be refused with a plain message before anything is written, because it would corrupt `assayr.env` → Task 4 (`install refuses an organisation name that would break the settings file`).
- An upgrade interrupted half-way (Ctrl-C, power loss) must be re-runnable and must not leave a mix of old and new program files → Task 6 (`an interrupted upgrade is put back before the next one`).
- A backup that fails part-way (database dump error, full disk) must leave no partial archive and no temporary folder behind → Task 5 (`a failed backup leaves nothing behind`).
- A restore from a damaged archive, or from a newer Assayr version, must be refused before any data is touched → Task 5 (`restore refuses a damaged backup`, `restore refuses a backup from a newer version`).

---

## File Structure

```
.github/workflows/
├── release.yml                     # NEW: tag → build both bundles, e2e test, publish Release
└── ci.yml                          # + installer job (shellcheck + bats)
deploy/
├── compose.yaml                    # CHANGED: production definition, image tags only
├── compose.https.yaml              # NEW: TLS on 8443 → HTTPS port, certificates mounted
├── compose.build.yaml              # NEW: build sections for development
├── smoke.sh                        # CHANGED: uses compose.build.yaml and smoke-checks.sh
├── smoke-checks.sh                 # NEW: sign-in, 93 controls, evidence verified, methodology, SoA
└── installer/
    ├── assayr                      # entry point: sources lib/, calls main
    ├── assayr.env.example          # every installer-managed setting, documented
    ├── README-INSTALL.md           # customer guide (Linux, macOS, Windows/WSL)
    ├── MANUAL-CHECKS.md            # Docker Desktop checklist for macOS and Windows
    ├── lib/
    │   ├── common.sh               # messages, install log, prompts, input checks
    │   ├── platform.sh             # linux / macos / wsl, install folder, privileges
    │   ├── envfile.sh              # read/write assayr.env, defaults merge, random password
    │   ├── bundle.sh               # checksums, versions, program files, image loading
    │   ├── checks.sh               # Docker, Compose, architecture, disk, memory, ports, openssl
    │   ├── certs.sh                # self-signed certificate, fingerprint
    │   ├── compose.sh              # docker compose wrapper, start, health, URL
    │   ├── backup.sh               # backup, read a backup, restore data
    │   ├── cmd_install.sh          # install
    │   ├── cmd_upgrade.sh          # upgrade, rollback, interrupted-upgrade recovery
    │   ├── cmd_misc.sh             # status, start, stop, restart, logs, backup, restore, create-admin, uninstall, version, help
    │   └── main.sh                 # argument handling and dispatch
    └── tests/
        ├── run.sh                  # shellcheck + bats
        ├── helpers.bash            # shared test setup, fixture bundle and installation
        ├── stubs/docker            # recording docker test double
        ├── compose.bats, common.bats, platform.bats, envfile.bats, bundle.bats,
        │   build_bundle.bats, checks.bats, install.bats, cli.bats, backup.bats, upgrade.bats
        ├── clamav-offline.sh       # release gate: ClamAV works without internet
        └── e2e.sh                  # end-to-end test of real bundles (CI, root, real Docker)
frontend/
├── Dockerfile                      # CHANGED: copies the three Caddy files, health check on /healthz
├── Caddyfile                       # CHANGED: HTTP on 8080, imports site.caddy
├── Caddyfile.https                 # NEW: TLS on 8443, 8080 redirects to HTTPS
└── site.caddy                      # NEW: shared headers, /healthz, /api proxy, SPA
scripts/build-bundle.sh             # NEW: assemble a bundle from local images
README.md, backend/pyproject.toml, backend/uv.lock, frontend/package.json, frontend/package-lock.json  # version 0.2.0, docs
.gitignore                          # + deploy/license/, deploy/certs/, dist/
Assayr-Vault: Deployment On-Prem, ADR-001, Non-Functional Requirements (build status)
```

---
### Task 1: Production compose file, HTTPS web configuration and the installer test harness

**Files:**
- Create: `deploy/compose.https.yaml`, `deploy/compose.build.yaml`, `deploy/smoke-checks.sh`, `frontend/site.caddy`, `frontend/Caddyfile.https`, `.shellcheckrc`, `deploy/installer/tests/run.sh`, `deploy/installer/tests/helpers.bash`
- Modify: `deploy/compose.yaml`, `deploy/smoke.sh`, `frontend/Caddyfile`, `frontend/Dockerfile`, `.github/workflows/ci.yml`, `.gitignore`
- Test: `deploy/installer/tests/compose.bats`

**Interfaces:**
- Consumes: the existing images' behaviour (API migrates and seeds on start; web serves the SPA and proxies `/api`).
- Produces: compose variables `ASSAYR_VERSION`, `ASSAYR_HOSTNAME`, `ASSAYR_HTTPS_PORT`, `ASSAYR_HTTP_PORT`, `ASSAYR_CERTS_DIR` (default `./certs`), `ASSAYR_LICENSE_DIR` (default `./license`), `ASSAYR_CLAMAV_HOST`, `POSTGRES_PASSWORD`; services `db`, `api`, `worker`, `web`, `clamav` (profile `av`); images `assayr-api:<version>`, `assayr-web:<version>`, `postgres:16-alpine`, `clamav/clamav:1.4`; web container serves `GET /healthz` → 200 on port 8080 in both modes; `deploy/smoke-checks.sh BASE EMAIL PASSWORD`; test helpers `REPO_ROOT`, `INSTALLER`, `load_libs`, `on_windows`, `skip_on_windows`, `file_mode PATH` (prints e.g. `rw-------`); `deploy/installer/tests/run.sh` (shellcheck, then every `*.bats` in that folder).

- [ ] **Step 1: Write the test harness and the failing compose tests**

`.shellcheckrc`:
```
source-path=SCRIPTDIR
external-sources=true
```

`deploy/installer/tests/run.sh`:
```bash
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
```

`deploy/installer/tests/helpers.bash`:
```bash
# Shared setup for the installer tests. Load with: load helpers
REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../.." && pwd)"
INSTALLER="$REPO_ROOT/deploy/installer"

# Source every installer library that exists so far.
load_libs() {
  local part
  for part in common platform envfile bundle checks certs compose backup cmd_install cmd_upgrade cmd_misc main; do
    if [ -f "$INSTALLER/lib/$part.sh" ]; then
      # shellcheck source=/dev/null
      . "$INSTALLER/lib/$part.sh"
    fi
  done
}

on_windows() {
  case "$(uname -s)" in MINGW* | MSYS* | CYGWIN*) return 0 ;; esac
  return 1
}

skip_on_windows() {
  if on_windows; then skip "file modes aren't meaningful on Windows"; fi
}

# file_mode PATH — permission bits as ls shows them, e.g. rw-------
file_mode() {
  ls -ld "$1" | cut -c2-10
}
```

`deploy/installer/tests/compose.bats`:
```bash
setup() {
  load helpers
  command -v docker >/dev/null 2>&1 || skip "the docker CLI isn't installed"
  ENV_FILE="$BATS_TEST_TMPDIR/test.env"
  printf 'ASSAYR_VERSION=1.2.3\nPOSTGRES_PASSWORD=unused\nASSAYR_HTTPS_PORT=443\nASSAYR_HTTP_PORT=80\n' >"$ENV_FILE"
}

compose_config() {
  docker compose --env-file "$ENV_FILE" --project-directory "$REPO_ROOT/deploy" "$@" config
}

@test "the production compose file runs versioned images and builds nothing" {
  run compose_config -f "$REPO_ROOT/deploy/compose.yaml"
  [ "$status" -eq 0 ]
  [[ "$output" == *"image: assayr-api:1.2.3"* ]]
  [[ "$output" == *"image: assayr-web:1.2.3"* ]]
  [[ "$output" == *"image: postgres:16-alpine"* ]]
  [[ "$output" != *"build:"* ]]
}

@test "malware scanning is an optional profile with a pinned image" {
  run compose_config -f "$REPO_ROOT/deploy/compose.yaml" --profile av
  [ "$status" -eq 0 ]
  [[ "$output" == *"image: clamav/clamav:1.4"* ]]
}

@test "the HTTPS override serves TLS on the HTTPS port with the certificates mounted" {
  run compose_config -f "$REPO_ROOT/deploy/compose.yaml" -f "$REPO_ROOT/deploy/compose.https.yaml"
  [ "$status" -eq 0 ]
  [[ "$output" == *"/etc/caddy/Caddyfile.https"* ]]
  [[ "$output" == *"target: 8443"* ]]
  [[ "$output" == *'published: "443"'* ]]
  [[ "$output" == *"target: /certs"* ]]
}

@test "the build override builds the images from source" {
  run compose_config -f "$REPO_ROOT/deploy/compose.yaml" -f "$REPO_ROOT/deploy/compose.build.yaml"
  [ "$status" -eq 0 ]
  [[ "$output" == *"context: "*"backend"* ]]
  [[ "$output" == *"context: "*"frontend"* ]]
}

@test "both Caddy configurations are valid" {
  docker info >/dev/null 2>&1 || skip "Docker isn't running"
  command -v openssl >/dev/null 2>&1 || skip "openssl isn't installed"
  local certs="$BATS_TEST_TMPDIR/certs" frontend="$REPO_ROOT/frontend" file
  mkdir -p "$certs"
  openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=localhost \
    -keyout "$certs/tls.key" -out "$certs/tls.crt" >/dev/null 2>&1
  if on_windows; then
    export MSYS_NO_PATHCONV=1
    certs="$(cygpath -m "$certs")"
    frontend="$(cygpath -m "$frontend")"
  fi
  for file in Caddyfile Caddyfile.https; do
    run docker run --rm -v "$frontend:/etc/caddy:ro" -v "$certs:/certs:ro" caddy:2-alpine \
      caddy validate --config "/etc/caddy/$file" --adapter caddyfile
    [ "$status" -eq 0 ] || { echo "$file: $output"; return 1; }
  done
}
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && bash deploy/installer/tests/run.sh`
Expected: FAIL — `the production compose file runs versioned images and builds nothing` (output contains `build:`), `malware scanning is an optional profile with a pinned image` (`clamav/clamav:stable`), and the HTTPS and build override tests (`compose.https.yaml` / `compose.build.yaml` not found). The Caddy test skips while Docker Desktop is stopped.

- [ ] **Step 3: Split the compose file**

Replace `deploy/compose.yaml` with:
```yaml
# Production definition of the Assayr stack. The installer runs it together with compose.https.yaml;
# development adds compose.build.yaml to build the images from source (see smoke.sh).
name: assayr

x-assayr-env: &assayr-env
  ASSAYR_DATABASE_URL: postgresql+pg8000://assayr:${POSTGRES_PASSWORD}@db:5432/assayr
  ASSAYR_ORG_NAME: ${ASSAYR_ORG_NAME:-My Organization}
  ASSAYR_SECURE_COOKIES: ${ASSAYR_SECURE_COOKIES:-false}
  ASSAYR_STORAGE_DIR: /data/blobs
  ASSAYR_MAX_UPLOAD_MB: ${ASSAYR_MAX_UPLOAD_MB:-100}
  ASSAYR_CLAMAV_HOST: ${ASSAYR_CLAMAV_HOST:-}
  ASSAYR_LICENSE_FILE: /etc/assayr/license/assayr.lic

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: assayr
      POSTGRES_USER: assayr
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in assayr.env}
    volumes:
      - dbdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U assayr -d assayr"]
      interval: 5s
      retries: 20
    restart: unless-stopped

  api:
    image: assayr-api:${ASSAYR_VERSION:-dev}
    environment: *assayr-env
    volumes:
      - blobs:/data/blobs
      - ${ASSAYR_LICENSE_DIR:-./license}:/etc/assayr/license:ro
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  worker:
    image: assayr-api:${ASSAYR_VERSION:-dev}
    entrypoint: ["assayr"]
    command: ["worker"]
    # The image HEALTHCHECK probes the API port; the worker serves no HTTP.
    healthcheck:
      disable: true
    environment: *assayr-env
    volumes:
      - blobs:/data/blobs
    depends_on:
      api:
        condition: service_healthy
    restart: unless-stopped

  web:
    image: assayr-web:${ASSAYR_VERSION:-dev}
    environment:
      ASSAYR_HOSTNAME: ${ASSAYR_HOSTNAME:-localhost}
      ASSAYR_HTTPS_PORT: ${ASSAYR_HTTPS_PORT:-443}
    ports:
      - "${ASSAYR_HTTP_PORT:-8080}:8080"
    depends_on:
      api:
        condition: service_healthy
    restart: unless-stopped

  clamav:
    image: clamav/clamav:1.4
    profiles: ["av"]
    restart: unless-stopped

volumes:
  dbdata:
  blobs:
```

`deploy/compose.https.yaml`:
```yaml
# HTTPS for the web service: Caddy serves TLS on 8443 (published on ASSAYR_HTTPS_PORT) with the
# certificate in ASSAYR_CERTS_DIR, and port 8080 redirects to HTTPS.
services:
  web:
    command: ["caddy", "run", "--config", "/etc/caddy/Caddyfile.https", "--adapter", "caddyfile"]
    ports:
      - "${ASSAYR_HTTPS_PORT:-443}:8443"
    volumes:
      - ${ASSAYR_CERTS_DIR:-./certs}:/certs:ro
```

`deploy/compose.build.yaml`:
```yaml
# Development only: build the Assayr images from source instead of running installed ones.
services:
  api:
    build: ../backend
  worker:
    build: ../backend
  web:
    build: ../frontend
```

Append to `.gitignore`:
```
deploy/license/
deploy/certs/
dist/
```

- [ ] **Step 4: Give the web image an HTTPS mode and a health endpoint**

`frontend/site.caddy`:
```
encode zstd gzip
header {
	X-Content-Type-Options nosniff
	X-Frame-Options DENY
	Referrer-Policy no-referrer
	Permissions-Policy "camera=(), microphone=(), geolocation=()"
	Content-Security-Policy "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
	-Server
}
handle /healthz {
	respond "ok" 200
}
handle /api/* {
	request_body {
		max_size 110MB
	}
	reverse_proxy {$ASSAYR_API_UPSTREAM:api:8000}
}
handle {
	root * /srv
	try_files {path} /index.html
	file_server
}
```

Replace `frontend/Caddyfile` with:
```
{
	admin off
	auto_https off
}

:8080 {
	import site.caddy
}
```

`frontend/Caddyfile.https`:
```
{
	admin off
	auto_https off
	default_sni {$ASSAYR_HOSTNAME:localhost}
}

:8443 {
	tls /certs/tls.crt /certs/tls.key
	import site.caddy
}

:8080 {
	handle /healthz {
		respond "ok" 200
	}
	handle {
		redir https://{host}:{$ASSAYR_HTTPS_PORT:443}{uri} permanent
	}
}
```

In `frontend/Dockerfile`, replace the final stage (from `FROM caddy:2-alpine` to the end) with:
```dockerfile
FROM caddy:2-alpine
COPY Caddyfile Caddyfile.https site.caddy /etc/caddy/
COPY --from=build /app/dist /srv
EXPOSE 8080 8443
HEALTHCHECK --interval=10s --timeout=3s --retries=6 CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
```

- [ ] **Step 5: Move the outside-in checks into a reusable script**

`deploy/smoke-checks.sh`:
```bash
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
```

Replace `deploy/smoke.sh` with:
```bash
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
```

- [ ] **Step 6: Run the installer checks in CI**

In `.github/workflows/ci.yml`, add this job after the `frontend` job (before `smoke`):
```yaml
  installer:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: sudo apt-get update && sudo apt-get install -y bats shellcheck
      - run: deploy/installer/tests/run.sh
        env:
          ASSAYR_REQUIRE_SHELLCHECK: "1"
```

- [ ] **Step 7: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && bash deploy/installer/tests/run.sh`
Expected: the four compose tests pass; the Caddy test skips unless Docker Desktop is running (start it from the Start menu to run it — expected to pass).

Run: `cd "E:/Work/GRC Tool/assayr/deploy" && docker compose --env-file assayr.env.example -f compose.yaml -f compose.build.yaml config --quiet && bash -n smoke.sh && bash -n smoke-checks.sh && echo OK`
Expected: `OK`.

- [ ] **Step 8: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && git add -A && git add --chmod=+x deploy/smoke-checks.sh deploy/installer/tests/run.sh && git commit -m "feat(deploy): production compose file, HTTPS web mode and installer test harness"
```

---
### Task 2: Core installer libraries — messages, prompts, platform, settings file and bundle checksums

**Files:**
- Create: `deploy/installer/lib/common.sh`, `deploy/installer/lib/platform.sh`, `deploy/installer/lib/envfile.sh`, `deploy/installer/lib/bundle.sh`
- Test: `deploy/installer/tests/common.bats`, `deploy/installer/tests/platform.bats`, `deploy/installer/tests/envfile.bats`, `deploy/installer/tests/bundle.bats`

**Interfaces:**
- Consumes: test helpers from Task 1.
- Produces:
  - `common.sh`: globals `ASSAYR_LOG`, `ASSAYR_INTERACTIVE` (1/0), `ASSAYR_ASSUME_YES` (1/0), `ASSAYR_RETRY_HINT`; `info MSG`, `warn MSG`, `die MSG` (exit 1; prints the retry hint and `Details: <log>`), `log_to FILE`, `run_logged CMD...`, `need_value OPTION VALUE`, `ask VAR QUESTION [DEFAULT] [optional]`, `ask_password VAR`, `confirm_word WORD MESSAGE`, `password_problem PW`, `text_problem LABEL VALUE`, `hostname_problem VALUE`, `email_problem VALUE`, `port_problem VALUE` (each `*_problem` prints a message or nothing, always returns 0).
  - `platform.sh`: `detect_platform` → `linux|wsl|macos|unsupported` (test overrides `ASSAYR_UNAME_S`, `ASSAYR_PROC_VERSION`), `normalize_arch NAME` → `amd64|arm64` (returns 1 otherwise), `default_install_dir PLATFORM`, `default_hostname PLATFORM`, `evaluation_notice PLATFORM`, `require_privileges PLATFORM COMMAND` (test override `ASSAYR_EUID`), `sudo_prefix`.
  - `envfile.sh`: `env_get KEY FILE`, `env_set KEY VALUE FILE` (mode 600), `env_merge_defaults EXAMPLE FILE` → prints the added keys, `random_password` → 32 letters and digits.
  - `bundle.sh`: `PROGRAM_FILES` (`assayr lib compose.yaml compose.https.yaml assayr.env.example README-INSTALL.md ARCH`), `sha256_of FILE`, `write_sums DIR`, `verify_bundle DIR` (prints the problem; returns 1), `bundle_value DIR NAME`, `version_valid V`, `version_gt A B`, `copy_program_files SRC DEST`, `load_images BUNDLE`.

- [ ] **Step 1: Write the failing tests**

`deploy/installer/tests/common.bats`:
```bash
setup() {
  load helpers
  load_libs
}

@test "text_problem refuses characters that would break the settings file" {
  local value
  for value in 'Acme $ Co' 'Acme "Co"' "Acme's" 'Acme \ Co' 'Acme # 1' 'Acme `Co`'; do
    [ -n "$(text_problem "Organisation name" "$value")" ] || { echo "accepted: $value"; return 1; }
  done
  [ -z "$(text_problem "Organisation name" "Acme Financial Services (PK) Ltd.")" ]
  [ "$(text_problem "Organisation name" "")" = "Organisation name can't be empty." ]
}

@test "hostname_problem accepts host names and IP addresses only" {
  local value
  for value in grc.corp.local localhost 10.0.0.5 assayr-01; do
    [ -z "$(hostname_problem "$value")" ] || { echo "refused: $value"; return 1; }
  done
  for value in "grc corp" -grc grc_corp ""; do
    [ -n "$(hostname_problem "$value")" ] || { echo "accepted: $value"; return 1; }
  done
}

@test "password_problem needs at least 12 characters" {
  [ "$(password_problem short)" = "The password must be at least 12 characters." ]
  [ -z "$(password_problem twelve-chars)" ]
}

@test "email_problem needs text on both sides of one @" {
  [ -z "$(email_problem admin@example.com)" ]
  [ -n "$(email_problem admin)" ]
  [ -n "$(email_problem "ad min@example.com")" ]
}

@test "port_problem accepts 1 to 65535" {
  [ -z "$(port_problem 443)" ]
  [ -n "$(port_problem 0)" ]
  [ -n "$(port_problem 70000)" ]
  [ -n "$(port_problem https)" ]
}

@test "ask keeps a value that is already set" {
  ASSAYR_INTERACTIVE=0
  FOO=preset
  ask FOO "Question" "default"
  [ "$FOO" = preset ]
}

@test "ask takes the default when running without questions" {
  ASSAYR_INTERACTIVE=0
  unset FOO
  ask FOO "Question" "default"
  [ "$FOO" = default ]
}

@test "ask without a default fails when running without questions" {
  ASSAYR_INTERACTIVE=0
  unset FOO
  run ask FOO "Question"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Set FOO when using --non-interactive."* ]]
}

@test "an optional question may stay empty" {
  ASSAYR_INTERACTIVE=0
  unset FOO
  ask FOO "Question" "" optional
  [ -z "$FOO" ]
}

@test "ask reads the answer, and asks again when a required answer is empty" {
  ASSAYR_INTERACTIVE=1
  unset FOO
  ask FOO "Question" <<'EOF'

typed answer
EOF
  [ "$FOO" = "typed answer" ]
}

@test "ask_password refuses a short password from the environment" {
  ASSAYR_INTERACTIVE=0
  PW=short
  run ask_password PW
  [ "$status" -eq 1 ]
  [[ "$output" == *"at least 12 characters"* ]]
}

@test "confirm_word cancels unless the word is typed" {
  ASSAYR_INTERACTIVE=1
  run confirm_word restore "This replaces your data." <<<"yes"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Cancelled; nothing was changed."* ]]
  run confirm_word restore "This replaces your data." <<<"restore"
  [ "$status" -eq 0 ]
}

@test "confirm_word with --yes needs no answer, and without questions it needs --yes" {
  ASSAYR_ASSUME_YES=1
  run confirm_word restore "This replaces your data."
  [ "$status" -eq 0 ]
  ASSAYR_ASSUME_YES=0
  ASSAYR_INTERACTIVE=0
  run confirm_word restore "This replaces your data."
  [ "$status" -eq 1 ]
  [[ "$output" == *"Add --yes"* ]]
}

@test "run_logged sends command output to the log only" {
  log_to "$BATS_TEST_TMPDIR/install.log"
  run run_logged echo hello-from-the-command
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  grep -q "RUN echo hello-from-the-command" "$BATS_TEST_TMPDIR/install.log"
  grep -q "^hello-from-the-command$" "$BATS_TEST_TMPDIR/install.log"
}

@test "die prints the retry hint and where the details are" {
  log_to "$BATS_TEST_TMPDIR/install.log"
  ASSAYR_RETRY_HINT="To start again: uninstall, then install."
  run die "Something broke."
  [ "$status" -eq 1 ]
  [[ "$output" == *"Error: Something broke."* ]]
  [[ "$output" == *"To start again: uninstall, then install."* ]]
  [[ "$output" == *"Details: $BATS_TEST_TMPDIR/install.log"* ]]
}

@test "need_value refuses a missing option value" {
  run need_value --dir ""
  [ "$status" -eq 1 ]
  [[ "$output" == *"--dir needs a value."* ]]
  run need_value --dir --http
  [ "$status" -eq 1 ]
}
```

`deploy/installer/tests/platform.bats`:
```bash
setup() {
  load helpers
  load_libs
  export ASSAYR_PROC_VERSION="$BATS_TEST_TMPDIR/version"
  echo "Linux version 6.8.0 (buildd@lcy02)" >"$ASSAYR_PROC_VERSION"
}

@test "detect_platform tells Linux, WSL and macOS apart" {
  ASSAYR_UNAME_S=Linux run detect_platform
  [ "$output" = linux ]
  echo "Linux version 5.15.153.1-microsoft-standard-WSL2" >"$ASSAYR_PROC_VERSION"
  ASSAYR_UNAME_S=Linux run detect_platform
  [ "$output" = wsl ]
  ASSAYR_UNAME_S=Darwin run detect_platform
  [ "$output" = macos ]
  ASSAYR_UNAME_S=MINGW64_NT-10.0 run detect_platform
  [ "$output" = unsupported ]
}

@test "normalize_arch maps Docker and uname names" {
  [ "$(normalize_arch x86_64)" = amd64 ]
  [ "$(normalize_arch amd64)" = amd64 ]
  [ "$(normalize_arch aarch64)" = arm64 ]
  [ "$(normalize_arch arm64)" = arm64 ]
  run normalize_arch ppc64le
  [ "$status" -eq 1 ]
}

@test "Linux installs in /opt/assayr, evaluation platforms in the home folder" {
  [ "$(default_install_dir linux)" = /opt/assayr ]
  [ "$(HOME=/home/sana default_install_dir macos)" = /home/sana/assayr ]
  [ "$(HOME=/home/sana default_install_dir wsl)" = /home/sana/assayr ]
  [ "$(default_hostname macos)" = localhost ]
}

@test "Linux needs root; macOS and WSL don't" {
  ASSAYR_EUID=1000 run require_privileges linux install
  [ "$status" -eq 1 ]
  [[ "$output" == *"Run this as root, for example: sudo ./assayr install"* ]]
  ASSAYR_EUID=0 run require_privileges linux install
  [ "$status" -eq 0 ]
  ASSAYR_EUID=501 run require_privileges macos install
  [ "$status" -eq 0 ]
}

@test "macOS and WSL are told the setup is for evaluation" {
  run evaluation_notice macos
  [[ "$output" == *"for evaluation"* ]]
  run evaluation_notice linux
  [ -z "$output" ]
}
```

`deploy/installer/tests/envfile.bats`:
```bash
setup() {
  load helpers
  load_libs
  ENV_FILE="$BATS_TEST_TMPDIR/assayr.env"
}

@test "env_get returns the last value of a key, or nothing" {
  printf 'A=1\nB=two words\nA=3\n' >"$ENV_FILE"
  [ "$(env_get A "$ENV_FILE")" = 3 ]
  [ "$(env_get B "$ENV_FILE")" = "two words" ]
  [ -z "$(env_get MISSING "$ENV_FILE")" ]
  [ -z "$(env_get A "$BATS_TEST_TMPDIR/no-such-file")" ]
}

@test "env_set replaces a key, keeps the others and handles = in values" {
  printf 'A=1\nB=2\n' >"$ENV_FILE"
  env_set A "x=y z" "$ENV_FILE"
  [ "$(env_get A "$ENV_FILE")" = "x=y z" ]
  [ "$(env_get B "$ENV_FILE")" = 2 ]
  [ "$(grep -c '^A=' "$ENV_FILE")" -eq 1 ]
}

@test "env_set creates the file readable by the owner only" {
  skip_on_windows
  env_set A 1 "$ENV_FILE"
  [ "$(file_mode "$ENV_FILE")" = "rw-------" ]
}

@test "env_merge_defaults adds only missing keys and reports them" {
  printf 'A=custom\n' >"$ENV_FILE"
  printf '# a comment\nA=default\nB=2\n\nC=3\n' >"$BATS_TEST_TMPDIR/example"
  run env_merge_defaults "$BATS_TEST_TMPDIR/example" "$ENV_FILE"
  [ "$output" = "B C" ]
  [ "$(env_get A "$ENV_FILE")" = custom ]
  [ "$(env_get C "$ENV_FILE")" = 3 ]
}

@test "random_password gives 32 letters and digits, different each time" {
  local first second
  first="$(random_password)"
  second="$(random_password)"
  [ "${#first}" -eq 32 ]
  [[ "$first" =~ ^[A-Za-z0-9]+$ ]]
  [ "$first" != "$second" ]
}
```

`deploy/installer/tests/bundle.bats`:
```bash
setup() {
  load helpers
  load_libs
  B="$BATS_TEST_TMPDIR/bundle"
  mkdir -p "$B/lib" "$B/images"
  echo "#!/usr/bin/env bash" >"$B/assayr"
  echo "lib" >"$B/lib/main.sh"
  echo "image" >"$B/images/api.tar"
  echo "1.2.3" >"$B/VERSION"
}

@test "a bundle with intact files passes the checksum check" {
  write_sums "$B"
  [ "$(grep -c . "$B/SHA256SUMS")" -eq 4 ]
  run verify_bundle "$B"
  [ "$status" -eq 0 ]
}

@test "a changed file is reported" {
  write_sums "$B"
  echo "tampered" >>"$B/lib/main.sh"
  run verify_bundle "$B"
  [ "$status" -eq 1 ]
  [ "$output" = "./lib/main.sh does not match its checksum." ]
}

@test "a missing file and a missing checksum list are reported" {
  write_sums "$B"
  rm "$B/images/api.tar"
  run verify_bundle "$B"
  [ "$status" -eq 1 ]
  [ "$output" = "./images/api.tar is missing." ]
  rm "$B/SHA256SUMS"
  run verify_bundle "$B"
  [ "$output" = "SHA256SUMS is missing." ]
}

@test "bundle_value reads VERSION without whitespace" {
  printf ' 1.2.3 \n' >"$B/VERSION"
  [ "$(bundle_value "$B" VERSION)" = 1.2.3 ]
}

@test "version_gt compares versions number by number" {
  version_gt 1.10.0 1.9.9
  version_gt 2.0.0 1.99.99
  version_gt 0.2.1 0.2.0
  version_gt 2.29.2-desktop.2 2.17.0
  # bats ignores a failing "! cmd", so negative cases use run !
  run ! version_gt 0.2.0 0.2.0
  run ! version_gt 0.1.9 0.2.0
}

@test "version_valid accepts MAJOR.MINOR.PATCH only" {
  version_valid 0.2.0
  version_valid 10.20.30
  run ! version_valid v0.2.0
  run ! version_valid 0.2
  run ! version_valid 0.2.0-rc1
}

@test "copy_program_files copies the program, replaces old library files and skips missing items" {
  local dest="$BATS_TEST_TMPDIR/install"
  mkdir -p "$dest/lib"
  echo "stale" >"$dest/lib/removed-in-new-version.sh"
  echo "amd64" >"$B/ARCH"
  copy_program_files "$B" "$dest"
  [ -f "$dest/assayr" ]
  [ -f "$dest/lib/main.sh" ]
  [ -f "$dest/ARCH" ]
  [ ! -e "$dest/lib/removed-in-new-version.sh" ]
  [ ! -e "$dest/VERSION" ]
  [ ! -e "$dest/images" ]
}
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && bash deploy/installer/tests/run.sh`
Expected: FAIL — every new test fails with `command not found` for `text_problem`, `detect_platform`, `env_get`, `write_sums` and the rest (the libraries don't exist yet); the compose tests still pass.

- [ ] **Step 3: Implement the libraries**

`deploy/installer/lib/common.sh`:
```bash
# shellcheck shell=bash
# Messages, the install log, prompts and input checks shared by every command.

ASSAYR_LOG="${ASSAYR_LOG:-}"
ASSAYR_INTERACTIVE="${ASSAYR_INTERACTIVE:-1}"
ASSAYR_ASSUME_YES="${ASSAYR_ASSUME_YES:-0}"
ASSAYR_RETRY_HINT="${ASSAYR_RETRY_HINT:-}"

_log_line() {
  [ -n "$ASSAYR_LOG" ] || return 0
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >>"$ASSAYR_LOG" 2>/dev/null || true
}

info() {
  printf '==> %s\n' "$*"
  _log_line "INFO $*"
}

warn() {
  printf 'Warning: %s\n' "$*" >&2
  _log_line "WARN $*"
}

die() {
  printf 'Error: %s\n' "$*" >&2
  _log_line "ERROR $*"
  if [ -n "$ASSAYR_RETRY_HINT" ]; then printf '%s\n' "$ASSAYR_RETRY_HINT" >&2; fi
  if [ -n "$ASSAYR_LOG" ]; then printf 'Details: %s\n' "$ASSAYR_LOG" >&2; fi
  exit 1
}

# log_to FILE — from now on, record every step and command output in FILE (owner-only).
log_to() {
  ASSAYR_LOG="$1"
  (umask 077 && : >>"$ASSAYR_LOG")
}

# run_logged CMD... — run a command with all its output going to the log only.
# The command line itself is logged: never pass a secret as an argument.
run_logged() {
  _log_line "RUN $*"
  if [ -n "$ASSAYR_LOG" ]; then
    "$@" >>"$ASSAYR_LOG" 2>&1
  else
    "$@" >/dev/null 2>&1
  fi
}

# need_value OPTION VALUE — stop when an option that takes a value didn't get one.
need_value() {
  if [ -z "${2:-}" ] || [ "${2#--}" != "${2:-}" ]; then die "$1 needs a value."; fi
}

# ask VAR QUESTION [DEFAULT] [optional]
# Keeps VAR when it is already set (from an option or the environment). Without questions
# (--non-interactive) it takes DEFAULT, and fails when a required value has no default.
ask() {
  local var="$1" question="$2" default="${3:-}" optional="${4:-}" answer=""
  if [ -n "${!var:-}" ]; then return 0; fi
  if [ "$ASSAYR_INTERACTIVE" != 1 ]; then
    if [ -z "$default" ] && [ "$optional" != optional ]; then die "Set $var when using --non-interactive."; fi
    printf -v "$var" '%s' "$default"
    return 0
  fi
  while :; do
    if [ -n "$default" ]; then
      read -r -p "$question [$default]: " answer || true
    else
      read -r -p "$question: " answer || true
    fi
    answer="${answer:-$default}"
    if [ -n "$answer" ] || [ "$optional" = optional ]; then break; fi
    echo "This is required."
  done
  printf -v "$var" '%s' "$answer"
}

password_problem() {
  if [ "${#1}" -lt 12 ]; then echo "The password must be at least 12 characters."; fi
}

# ask_password VAR — the administrator password: checked when given, otherwise typed twice, hidden.
ask_password() {
  local var="$1" first="" second="" problem
  if [ -n "${!var:-}" ]; then
    problem="$(password_problem "${!var}")"
    [ -z "$problem" ] || die "$problem"
    return 0
  fi
  [ "$ASSAYR_INTERACTIVE" = 1 ] || die "Set $var when using --non-interactive."
  while :; do
    read -r -s -p "Administrator password (at least 12 characters): " first || true
    echo
    problem="$(password_problem "$first")"
    if [ -n "$problem" ]; then
      echo "$problem"
      continue
    fi
    read -r -s -p "Type it again: " second || true
    echo
    if [ "$first" != "$second" ]; then
      echo "The passwords don't match."
      continue
    fi
    printf -v "$var" '%s' "$first"
    return 0
  done
}

# confirm_word WORD MESSAGE — explain, then require WORD to be typed (or --yes).
confirm_word() {
  local word="$1" answer=""
  printf '%s\n' "$2"
  if [ "$ASSAYR_ASSUME_YES" = 1 ]; then return 0; fi
  [ "$ASSAYR_INTERACTIVE" = 1 ] || die "Add --yes to confirm when running without questions."
  read -r -p "Type $word to continue: " answer || true
  [ "$answer" = "$word" ] || die "Cancelled; nothing was changed."
}

# text_problem LABEL VALUE — refuse values that would break assayr.env.
text_problem() {
  case "$2" in
    '') echo "$1 can't be empty." ;;
    *[\$\"\'\`\\#]* | *$'\n'*) echo "$1 can't contain \$, quotes, backticks, backslashes or #." ;;
  esac
}

hostname_problem() {
  local pattern='^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$'
  [[ "$1" =~ $pattern ]] || echo "\"$1\" isn't a valid hostname. Use letters, digits, dots and hyphens, for example grc.example.local."
}

email_problem() {
  local pattern='^[^@[:space:]]+@[^@[:space:]]+$'
  [[ "$1" =~ $pattern ]] || echo "\"$1\" isn't a valid email address."
}

port_problem() {
  local pattern='^[0-9]+$'
  if [[ "$1" =~ $pattern ]] && [ "$1" -ge 1 ] && [ "$1" -le 65535 ]; then return 0; fi
  echo "\"$1\" isn't a valid port. Use a number from 1 to 65535."
}
```

`deploy/installer/lib/platform.sh`:
```bash
# shellcheck shell=bash
# Which system we are on, where Assayr lives there, and who may install it.

detect_platform() {
  local kernel="${ASSAYR_UNAME_S:-$(uname -s)}" version_file="${ASSAYR_PROC_VERSION:-/proc/version}"
  case "$kernel" in
    Darwin) echo macos ;;
    Linux)
      if [ -r "$version_file" ] && grep -qi microsoft "$version_file"; then echo wsl; else echo linux; fi
      ;;
    *) echo unsupported ;;
  esac
}

# normalize_arch NAME — Docker's or uname's architecture name as amd64 or arm64.
normalize_arch() {
  case "$1" in
    x86_64 | amd64) echo amd64 ;;
    aarch64 | arm64) echo arm64 ;;
    *)
      echo "$1"
      return 1
      ;;
  esac
}

default_install_dir() {
  case "$1" in
    linux) echo /opt/assayr ;;
    *) echo "$HOME/assayr" ;;
  esac
}

default_hostname() {
  case "$1" in
    linux) hostname -f 2>/dev/null || hostname ;;
    *) echo localhost ;;
  esac
}

evaluation_notice() {
  case "$1" in
    macos | wsl) warn "This setup is for evaluation. Run Assayr in production on a Linux server." ;;
  esac
}

require_privileges() {
  if [ "$1" = linux ] && [ "${ASSAYR_EUID:-$(id -u)}" -ne 0 ]; then
    die "Run this as root, for example: sudo ./assayr $2"
  fi
}

# sudo_prefix — "sudo " where commands need root, for the hints we print.
sudo_prefix() {
  if [ "$(detect_platform)" = linux ]; then echo "sudo "; fi
}
```

`deploy/installer/lib/envfile.sh`:
```bash
# shellcheck shell=bash
# Reading and writing assayr.env (KEY=value lines; no quoting, no variables).

# env_get KEY FILE — the value of the last KEY= line, or nothing.
env_get() {
  [ -f "$2" ] || return 0
  { grep -E "^$1=" "$2" || true; } | tail -n 1 | cut -d= -f2-
}

# env_set KEY VALUE FILE — replace or add KEY; the file stays owner-only.
env_set() {
  local key="$1" value="$2" file="$3" tmp
  tmp="$(mktemp "$file.XXXXXX")"
  if [ -f "$file" ]; then
    awk -v k="$key=" 'index($0, k) != 1' "$file" >"$tmp"
  fi
  printf '%s=%s\n' "$key" "$value" >>"$tmp"
  chmod 600 "$tmp"
  mv "$tmp" "$file"
}

# env_merge_defaults EXAMPLE FILE — add settings that exist in EXAMPLE but not in FILE, with
# their default values; existing values never change. Prints the added keys.
env_merge_defaults() {
  local example="$1" file="$2" line key added=""
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in '' | '#'*) continue ;; esac
    key="${line%%=*}"
    if ! grep -qE "^$key=" "$file"; then
      printf '%s\n' "$line" >>"$file"
      added="$added $key"
    fi
  done <"$example"
  echo "${added# }"
}

# random_password — 32 random letters and digits.
random_password() {
  local chars=""
  while [ "${#chars}" -lt 32 ]; do
    chars="$chars$(head -c 256 /dev/urandom | LC_ALL=C tr -dc 'A-Za-z0-9')"
  done
  printf '%s\n' "${chars:0:32}"
}
```

`deploy/installer/lib/bundle.sh`:
```bash
# shellcheck shell=bash
# Bundle integrity, versions, program files and image loading.

# What an installation keeps from a bundle. VERSION is handled separately (written last on upgrade).
PROGRAM_FILES="assayr lib compose.yaml compose.https.yaml assayr.env.example README-INSTALL.md ARCH"

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | cut -d' ' -f1
  else
    shasum -a 256 "$1" | cut -d' ' -f1
  fi
}

# write_sums DIR — write DIR/SHA256SUMS covering every other file under DIR.
write_sums() {
  (
    cd "$1"
    find . -type f ! -name 'SHA256SUMS*' | LC_ALL=C sort | while IFS= read -r file; do
      printf '%s  %s\n' "$(sha256_of "$file")" "$file"
    done >SHA256SUMS.tmp
    mv SHA256SUMS.tmp SHA256SUMS
  )
}

# verify_bundle DIR — every file listed in DIR/SHA256SUMS exists and matches. Prints the first
# problem and returns 1.
verify_bundle() {
  local dir="$1" sum path
  if [ ! -f "$dir/SHA256SUMS" ]; then
    echo "SHA256SUMS is missing."
    return 1
  fi
  while read -r sum path; do
    [ -n "$sum" ] || continue
    path="${path#\*}"
    if [ ! -f "$dir/$path" ]; then
      echo "$path is missing."
      return 1
    fi
    if [ "$(sha256_of "$dir/$path")" != "$sum" ]; then
      echo "$path does not match its checksum."
      return 1
    fi
  done <"$dir/SHA256SUMS"
}

# bundle_value DIR NAME — the content of DIR/NAME (VERSION, ARCH) without whitespace.
bundle_value() {
  [ -f "$1/$2" ] || return 1
  tr -d '[:space:]' <"$1/$2"
}

version_valid() {
  local pattern='^[0-9]+\.[0-9]+\.[0-9]+$'
  [[ "$1" =~ $pattern ]]
}

# version_gt A B — true when A is newer than B (numbers compared part by part; suffixes such
# as "-desktop.2" are ignored).
version_gt() {
  local a="${1#v}" b="${2#v}" i x y
  for i in 1 2 3; do
    x="$(printf '%s' "$a" | cut -d. -f"$i")"
    y="$(printf '%s' "$b" | cut -d. -f"$i")"
    x="${x%%[!0-9]*}"
    y="${y%%[!0-9]*}"
    x="${x:-0}"
    y="${y:-0}"
    if [ "$x" -gt "$y" ]; then return 0; fi
    if [ "$x" -lt "$y" ]; then return 1; fi
  done
  return 1
}

# copy_program_files SRC DEST — replace DEST's program files with SRC's.
copy_program_files() {
  local src="$1" dest="$2" item
  # shellcheck disable=SC2086 # PROGRAM_FILES is a word list
  for item in $PROGRAM_FILES; do
    [ -e "$src/$item" ] || continue
    rm -rf "${dest:?}/$item"
    cp -R "$src/$item" "$dest/$item"
  done
}

# load_images BUNDLE — docker load every image listed in images/IMAGES.txt that isn't loaded yet.
load_images() {
  local bundle="$1" file ref
  while read -r file ref _; do
    [ -n "$file" ] || continue
    if docker image inspect "$ref" >/dev/null 2>&1; then
      info "Image $ref is already loaded"
    else
      info "Loading image $ref"
      run_logged docker load -i "$bundle/images/$file" || return 1
    fi
  done <"$bundle/images/IMAGES.txt"
}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && bash deploy/installer/tests/run.sh`
Expected: all tests pass (mode tests skip on Windows; the Caddy test skips without Docker).

- [ ] **Step 5: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && git add -A && git commit -m "feat(installer): core libraries for messages, prompts, platform, settings and checksums"
```

---
### Task 3: Machine checks, certificates and the compose wrapper, tested against a docker stub

**Files:**
- Create: `deploy/installer/tests/stubs/docker`, `deploy/installer/lib/checks.sh`, `deploy/installer/lib/certs.sh`, `deploy/installer/lib/compose.sh`
- Modify: `deploy/installer/tests/helpers.bash`
- Test: `deploy/installer/tests/checks.bats`, `deploy/installer/tests/certs.bats`

**Interfaces:**
- Consumes: Task 2 (`die`, `warn`, `info`, `run_logged`, `normalize_arch`, `version_gt`, `env_get`).
- Produces:
  - docker stub (`tests/stubs/docker`): records each call as one line in `$STUB_LOG`; knobs `STUB_ARCH`, `STUB_MEM`, `STUB_COMPOSE_VERSION`, `STUB_IMAGES_PRESENT`, `STUB_NO_DAEMON`, `STUB_FAIL_ON`, `STUB_FAIL_TIMES`; `docker save -o FILE REF` writes FILE; `compose … config --images` prints the four images for `$ASSAYR_VERSION`; `compose … pg_dump` prints a fake dump; `compose … run … -v HOST:/backup … -cf /backup/blobs.tar` writes `HOST/blobs.tar`.
  - helpers: `use_docker_stub` (puts the stub first on `PATH`, sets `STUB_LOG`, Linux-as-root overrides and `ASSAYR_MIN_FREE_GB=0`), `stub_images VERSION`.
  - `checks.sh`: `ASSAYR_MIN_FREE_GB` (default 10), `docker_help PLATFORM`, `check_docker PLATFORM`, `check_arch BUNDLE_ARCH`, `free_kb PATH`, `check_disk DIR`, `check_memory`, `port_in_use PORT`, `check_port PORT OPTION`, `check_openssl`.
  - `certs.sh`: `make_self_signed HOST CERT KEY`, `cert_fingerprint CERT`.
  - `compose.sh`: global `ASSAYR_DIR`; `assayr_compose ARGS...`, `wait_timeout`, `start_stack`, `api_ready`, `audit_ok`, `install_url`, `create_admin_account EMAIL PASSWORD`.

- [ ] **Step 1: Write the docker stub, the helpers and the failing tests**

`deploy/installer/tests/stubs/docker`:
```bash
#!/usr/bin/env bash
# Test double for docker. Records every call in $STUB_LOG and fakes the answers the installer needs.
#   STUB_ARCH            architecture reported by docker info (default x86_64)
#   STUB_MEM             memory in bytes reported by docker info (default 16 GiB)
#   STUB_COMPOSE_VERSION version reported by docker compose version --short (default 2.29.0)
#   STUB_IMAGES_PRESENT  space-separated image references that docker image inspect finds
#   STUB_NO_DAEMON=1     docker info fails as if the daemon were stopped
#   STUB_FAIL_ON         fail any call whose arguments contain this text ...
#   STUB_FAIL_TIMES      ... only this many times (default: every time)
set -euo pipefail
printf '%s\n' "$*" >>"${STUB_LOG:?STUB_LOG must be set}"

if [ -n "${STUB_FAIL_ON:-}" ]; then
  case "$*" in
    *"$STUB_FAIL_ON"*)
      count_file="$STUB_LOG.failures"
      count="$(cat "$count_file" 2>/dev/null || echo 0)"
      if [ -z "${STUB_FAIL_TIMES:-}" ] || [ "$count" -lt "$STUB_FAIL_TIMES" ]; then
        echo $((count + 1)) >"$count_file"
        echo "stub: failing on purpose: $*" >&2
        exit 1
      fi
      ;;
  esac
fi

last="${!#}"
case "${1:-}" in
  info)
    [ "${STUB_NO_DAEMON:-0}" != 1 ] || exit 1
    case "$*" in
      *Architecture*) echo "${STUB_ARCH:-x86_64}" ;;
      *MemTotal*) echo "${STUB_MEM:-17179869184}" ;;
    esac
    ;;
  image)
    if [ "${2:-}" = inspect ]; then
      case " ${STUB_IMAGES_PRESENT:-} " in
        *" $last "*)
          case "$*" in *--format*) echo "sha256:stub-$last" ;; esac
          exit 0
          ;;
      esac
      exit 1
    fi
    ;;
  save)
    # docker save -o FILE REF
    echo "stub image $last" >"$3"
    ;;
  compose)
    case "$*" in
      *"compose version"*) echo "${STUB_COMPOSE_VERSION:-2.29.0}" ;;
      *"config --images"*)
        printf '%s\n' "assayr-api:${ASSAYR_VERSION:-dev}" "assayr-web:${ASSAYR_VERSION:-dev}" \
          postgres:16-alpine clamav/clamav:1.4
        ;;
      *pg_dump*) echo "stub database dump" ;;
      *" run "*)
        prev="" host=""
        for arg in "$@"; do
          if [ "$prev" = -v ]; then host="${arg%%:/backup*}"; fi
          prev="$arg"
        done
        case "$*" in *"-cf /backup/blobs.tar"*) echo "stub evidence files" >"$host/blobs.tar" ;; esac
        ;;
    esac
    ;;
esac
exit 0
```

Append to `deploy/installer/tests/helpers.bash`:
```bash

# use_docker_stub — run the installer against tests/stubs/docker, as root on Linux, with no
# free-disk requirement. Every docker call is recorded in $STUB_LOG.
use_docker_stub() {
  export PATH="$BATS_TEST_DIRNAME/stubs:$PATH"
  export STUB_LOG="$BATS_TEST_TMPDIR/docker.log"
  : >"$STUB_LOG"
  export ASSAYR_UNAME_S=Linux ASSAYR_PROC_VERSION="$BATS_TEST_TMPDIR/no-proc-version" ASSAYR_EUID=0
  export ASSAYR_MIN_FREE_GB=0
}

# stub_images VERSION — the four image references a bundle of VERSION contains.
stub_images() {
  echo "assayr-api:$1 assayr-web:$1 postgres:16-alpine clamav/clamav:1.4"
}
```

`deploy/installer/tests/checks.bats`:
```bash
setup() {
  load helpers
  load_libs
  use_docker_stub
}

@test "a stopped Docker is reported with how to start it on that platform" {
  STUB_NO_DAEMON=1 run check_docker wsl
  [ "$status" -eq 1 ]
  [[ "$output" == *"Docker is installed but not running"* ]]
  [[ "$output" == *"WSL integration"* ]]
}

@test "a machine without Docker is told where to get it" {
  PATH="$BATS_TEST_TMPDIR/empty" run check_docker linux
  [ "$status" -eq 1 ]
  [[ "$output" == *"Docker is not installed."* ]]
  [[ "$output" == *"docs.docker.com/engine/install"* ]]
}

@test "Compose must be 2.17 or newer, including Docker Desktop's version strings" {
  STUB_COMPOSE_VERSION=2.12.0 run check_docker linux
  [ "$status" -eq 1 ]
  [[ "$output" == *"Docker Compose 2.12.0 is too old"* ]]
  STUB_COMPOSE_VERSION=v2.29.2-desktop.2 run check_docker macos
  [ "$status" -eq 0 ]
}

@test "a bundle for another architecture is refused with the right download named" {
  STUB_ARCH=aarch64 run check_arch amd64
  [ "$status" -eq 1 ]
  [[ "$output" == *"This bundle is for amd64 but this machine is arm64."* ]]
  [[ "$output" == *"linux-arm64-offline.tar.gz"* ]]
  STUB_ARCH=x86_64 run check_arch amd64
  [ "$status" -eq 0 ]
}

@test "not enough free disk space is refused" {
  ASSAYR_MIN_FREE_GB=100000000 run check_disk "$BATS_TEST_TMPDIR/not/created/yet"
  [ "$status" -eq 1 ]
  [[ "$output" == *"At least 100000000 GB of free disk space is needed"* ]]
}

@test "less than 4 GB of Docker memory is a warning, not an error" {
  STUB_MEM=2147483648 run check_memory
  [ "$status" -eq 0 ]
  [[ "$output" == *"less than 4 GB of memory"* ]]
}

@test "a port in use is refused with the option to choose another" {
  port_in_use() { return 0; }
  run check_port 443 --https-port
  [ "$status" -eq 1 ]
  [[ "$output" == *"Port 443 is already in use. Free it or choose another port with --https-port."* ]]
}

@test "assayr_compose adds the HTTPS file and the malware-scanning profile from the settings" {
  ASSAYR_DIR="$BATS_TEST_TMPDIR/my install"
  mkdir -p "$ASSAYR_DIR"
  printf 'ASSAYR_WEB_MODE=https\nASSAYR_MALWARE_SCAN=true\n' >"$ASSAYR_DIR/assayr.env"
  assayr_compose ps
  grep -qF -- "--project-directory $ASSAYR_DIR --env-file $ASSAYR_DIR/assayr.env -f $ASSAYR_DIR/compose.yaml -f $ASSAYR_DIR/compose.https.yaml --profile av ps" "$STUB_LOG"
  : >"$STUB_LOG"
  printf 'ASSAYR_WEB_MODE=http\nASSAYR_MALWARE_SCAN=false\n' >"$ASSAYR_DIR/assayr.env"
  assayr_compose ps
  run grep -c -e compose.https.yaml -e "--profile av" "$STUB_LOG"
  [ "$output" = 0 ]
}

@test "install_url leaves out the standard ports" {
  ASSAYR_DIR="$BATS_TEST_TMPDIR"
  printf 'ASSAYR_HOSTNAME=grc.local\nASSAYR_WEB_MODE=https\nASSAYR_HTTPS_PORT=443\n' >"$ASSAYR_DIR/assayr.env"
  [ "$(install_url)" = https://grc.local ]
  printf 'ASSAYR_HOSTNAME=grc.local\nASSAYR_WEB_MODE=https\nASSAYR_HTTPS_PORT=8443\n' >"$ASSAYR_DIR/assayr.env"
  [ "$(install_url)" = https://grc.local:8443 ]
  printf 'ASSAYR_HOSTNAME=grc.local\nASSAYR_WEB_MODE=http\nASSAYR_HTTP_PORT=8080\n' >"$ASSAYR_DIR/assayr.env"
  [ "$(install_url)" = http://grc.local:8080 ]
}

@test "create_admin_account passes the password by environment name only" {
  ASSAYR_DIR="$BATS_TEST_TMPDIR"
  printf 'ASSAYR_WEB_MODE=https\n' >"$ASSAYR_DIR/assayr.env"
  create_admin_account admin@example.com "secret-password-123"
  grep -qF -- "exec -T -e ASSAYR_ADMIN_PASSWORD api assayr create-admin --email admin@example.com" "$STUB_LOG"
  run grep -c "secret-password-123" "$STUB_LOG"
  [ "$output" = 0 ]
}
```

`deploy/installer/tests/certs.bats`:
```bash
setup() {
  load helpers
  load_libs
  command -v openssl >/dev/null 2>&1 || skip "openssl isn't installed"
  CERT="$BATS_TEST_TMPDIR/tls.crt"
  KEY="$BATS_TEST_TMPDIR/tls.key"
}

@test "the self-signed certificate covers the hostname, localhost and 127.0.0.1" {
  make_self_signed grc.corp.local "$CERT" "$KEY"
  run openssl x509 -in "$CERT" -noout -text
  [[ "$output" == *"DNS:grc.corp.local"* ]]
  [[ "$output" == *"DNS:localhost"* ]]
  [[ "$output" == *"IP Address:127.0.0.1"* ]]
}

@test "an IP address as hostname becomes an IP entry" {
  make_self_signed 10.20.30.40 "$CERT" "$KEY"
  run openssl x509 -in "$CERT" -noout -text
  [[ "$output" == *"IP Address:10.20.30.40"* ]]
}

@test "the fingerprint is a SHA-256 in colon-separated hex" {
  make_self_signed localhost "$CERT" "$KEY"
  [[ "$(cert_fingerprint "$CERT")" =~ ^([0-9A-F]{2}:){31}[0-9A-F]{2}$ ]]
}

@test "the private key is readable by the owner only" {
  skip_on_windows
  make_self_signed localhost "$CERT" "$KEY"
  [ "$(file_mode "$KEY")" = "rw-------" ]
}
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && bash deploy/installer/tests/run.sh`
Expected: FAIL — the checks and certs tests fail with `command not found` (`check_docker`, `check_arch`, `make_self_signed`, `assayr_compose`, …).

- [ ] **Step 3: Implement the checks**

`deploy/installer/lib/checks.sh`:
```bash
# shellcheck shell=bash
# Machine checks made before anything changes: Docker, Compose, architecture, disk, memory,
# ports and openssl.

ASSAYR_MIN_FREE_GB="${ASSAYR_MIN_FREE_GB:-10}"
ASSAYR_MIN_COMPOSE="2.17.0"

docker_help() {
  case "$1" in
    macos) echo "Install and start Docker Desktop (https://docs.docker.com/desktop/setup/install/mac-install/) or Colima." ;;
    wsl) echo "Start Docker Desktop on Windows and turn on WSL integration for this distribution (Settings > Resources > WSL integration)." ;;
    *) echo "Install Docker Engine (https://docs.docker.com/engine/install/) and start it: systemctl start docker" ;;
  esac
}

check_docker() {
  local platform="$1" version
  command -v docker >/dev/null 2>&1 || die "Docker is not installed. $(docker_help "$platform")"
  docker info >/dev/null 2>&1 || die "Docker is installed but not running, or this user can't use it. $(docker_help "$platform")"
  version="$(docker compose version --short 2>/dev/null)" \
    || die "The Docker Compose plugin is missing. Install it: https://docs.docker.com/compose/install/"
  version="${version#v}"
  version="${version%%-*}"
  if version_gt "$ASSAYR_MIN_COMPOSE" "$version"; then
    die "Docker Compose $version is too old; Assayr needs $ASSAYR_MIN_COMPOSE or newer."
  fi
}

# check_arch BUNDLE_ARCH — the Docker host must run the bundle's architecture.
check_arch() {
  local raw machine
  raw="$(docker info --format '{{.Architecture}}' 2>/dev/null || true)"
  machine="$(normalize_arch "$raw")" \
    || die "This machine's architecture ($raw) isn't supported. Assayr runs on x86-64 (amd64) and arm64."
  [ "$machine" = "$1" ] \
    || die "This bundle is for $1 but this machine is $machine. Download assayr-<version>-linux-$machine-offline.tar.gz instead."
}

# free_kb PATH — free space in KB on the filesystem holding PATH or its nearest existing parent.
free_kb() {
  local path="$1"
  while [ ! -e "$path" ]; do path="$(dirname "$path")"; done
  df -Pk "$path" | awk 'NR==2 {print $4}'
}

check_disk() {
  local need="$ASSAYR_MIN_FREE_GB" kb
  [ "$need" -gt 0 ] || return 0
  kb="$(free_kb "$1")"
  [ "$kb" -ge $((need * 1024 * 1024)) ] \
    || die "At least $need GB of free disk space is needed for $1 (there is $((kb / 1024 / 1024)) GB)."
}

check_memory() {
  local bytes
  bytes="$(docker info --format '{{.MemTotal}}' 2>/dev/null || echo 0)"
  if [ "${bytes:-0}" -lt $((4 * 1024 * 1024 * 1024)) ]; then
    warn "Docker has less than 4 GB of memory. Malware scanning alone needs about 2 GB: give Docker more memory, or install with ASSAYR_MALWARE_SCAN=false."
  fi
}

port_in_use() {
  (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null
}

check_port() {
  if port_in_use "$1"; then die "Port $1 is already in use. Free it or choose another port with $2."; fi
}

check_openssl() {
  command -v openssl >/dev/null 2>&1 \
    || die "openssl is needed to create a self-signed certificate. Install it, or give your own certificate with ASSAYR_TLS_CERT and ASSAYR_TLS_KEY."
}
```

- [ ] **Step 4: Implement certificates and the compose wrapper**

`deploy/installer/lib/certs.sh`:
```bash
# shellcheck shell=bash
# The self-signed certificate used when the customer doesn't supply one.

# make_self_signed HOST CERT KEY — RSA 3072, 825 days, valid for HOST, localhost and 127.0.0.1.
make_self_signed() {
  local host="$1" cert="$2" key="$3" conf first
  local ip_pattern='^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'
  if [[ "$host" =~ $ip_pattern ]]; then first="IP.1 = $host"; else first="DNS.1 = $host"; fi
  conf="$(mktemp "${TMPDIR:-/tmp}/assayr-cert.XXXXXX")"
  cat >"$conf" <<EOF
[req]
distinguished_name = dn
x509_extensions = ext
prompt = no
[dn]
CN = $host
O = Assayr self-signed
[ext]
subjectAltName = @alt
basicConstraints = critical, CA:FALSE
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
[alt]
$first
DNS.2 = localhost
IP.2 = 127.0.0.1
EOF
  if ! (umask 077 && openssl req -x509 -newkey rsa:3072 -nodes -days 825 -config "$conf" \
    -keyout "$key" -out "$cert" >/dev/null 2>&1); then
    rm -f "$conf"
    return 1
  fi
  rm -f "$conf"
  chmod 600 "$key"
  chmod 644 "$cert"
}

cert_fingerprint() {
  openssl x509 -noout -fingerprint -sha256 -in "$1" | cut -d= -f2
}
```

`deploy/installer/lib/compose.sh`:
```bash
# shellcheck shell=bash
# docker compose for the installation in $ASSAYR_DIR, and what we ask of the running stack.

ASSAYR_DIR="${ASSAYR_DIR:-}"

assayr_compose() {
  local env="$ASSAYR_DIR/assayr.env"
  local args=(compose --project-directory "$ASSAYR_DIR" --env-file "$env" -f "$ASSAYR_DIR/compose.yaml")
  if [ "$(env_get ASSAYR_WEB_MODE "$env")" = https ]; then args+=(-f "$ASSAYR_DIR/compose.https.yaml"); fi
  if [ "$(env_get ASSAYR_MALWARE_SCAN "$env")" = true ]; then args+=(--profile av); fi
  docker "${args[@]}" "$@"
}

wait_timeout() {
  local seconds
  seconds="$(env_get ASSAYR_WAIT_TIMEOUT "$ASSAYR_DIR/assayr.env")"
  echo "${seconds:-600}"
}

# start_stack — start every service and wait until all are healthy.
start_stack() {
  run_logged assayr_compose up -d --wait --wait-timeout "$(wait_timeout)"
}

api_ready() {
  run_logged assayr_compose exec -T api python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/readyz', timeout=5)"
}

# audit_ok — the audit trail's hash chain is intact.
audit_ok() {
  run_logged assayr_compose exec -T api assayr audit-verify
}

install_url() {
  local env="$ASSAYR_DIR/assayr.env" host port
  host="$(env_get ASSAYR_HOSTNAME "$env")"
  if [ "$(env_get ASSAYR_WEB_MODE "$env")" = https ]; then
    port="$(env_get ASSAYR_HTTPS_PORT "$env")"
    if [ "$port" = 443 ]; then echo "https://$host"; else echo "https://$host:$port"; fi
  else
    port="$(env_get ASSAYR_HTTP_PORT "$env")"
    if [ "$port" = 80 ]; then echo "http://$host"; else echo "http://$host:$port"; fi
  fi
}

# create_admin_account EMAIL PASSWORD — the password reaches the container through the
# environment (docker compose exec -e NAME forwards it), never on a command line.
create_admin_account() {
  (
    export ASSAYR_ADMIN_PASSWORD="$2"
    run_logged assayr_compose exec -T -e ASSAYR_ADMIN_PASSWORD api \
      assayr create-admin --email "$1" --full-name Administrator
  )
}
```

- [ ] **Step 5: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && bash deploy/installer/tests/run.sh`
Expected: all tests pass (mode tests skip on Windows).

- [ ] **Step 6: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && git add -A && git add --chmod=+x deploy/installer/tests/stubs/docker && git commit -m "feat(installer): machine checks, self-signed certificates and the compose wrapper"
```

---
### Task 4: The bundle — build script, entry command, settings template and install guide

**Files:**
- Create: `scripts/build-bundle.sh`, `deploy/installer/assayr`, `deploy/installer/lib/main.sh`, `deploy/installer/lib/cmd_misc.sh`, `deploy/installer/assayr.env.example`, `deploy/installer/README-INSTALL.md`
- Modify: `deploy/installer/tests/helpers.bash`
- Test: `deploy/installer/tests/build_bundle.bats`, `deploy/installer/tests/cli.bats`

**Interfaces:**
- Consumes: Tasks 2–3.
- Produces:
  - `scripts/build-bundle.sh VERSION ARCH OUTDIR [--no-archive]` → folder `OUTDIR/assayr-VERSION/` and, unless `--no-archive`, `OUTDIR/assayr-VERSION-linux-ARCH-offline.tar.gz`. Needs `assayr-api:VERSION` and `assayr-web:VERSION` locally; pulls third-party images when missing. Image list comes from `docker compose -f compose.yaml --profile av config --images`. `images/IMAGES.txt` lines: `FILE REF IMAGE_ID`.
  - Entry `deploy/installer/assayr` (sources the libraries that exist, calls `main "$@"`); globals `SCRIPT_DIR`, `BUNDLE_DIR`.
  - `main.sh`: `main ARGS...` (pulls `--dir DIR` and `--yes` out of any position; `install`/`upgrade` need a bundle folder; installation commands go through `use_installation COMMAND DIR`, which sets `ASSAYR_DIR` and the log), `use_installation`.
  - `cmd_misc.sh`: `usage`, `cmd_version`.
  - `assayr.env.example`: every setting the installer manages, with defaults (keys: `ASSAYR_VERSION`, `POSTGRES_PASSWORD`, `ASSAYR_HOSTNAME`, `ASSAYR_ORG_NAME`, `ASSAYR_WEB_MODE`, `ASSAYR_HTTPS_PORT`, `ASSAYR_HTTP_PORT`, `ASSAYR_SECURE_COOKIES`, `ASSAYR_MAX_UPLOAD_MB`, `ASSAYR_MALWARE_SCAN`, `ASSAYR_CLAMAV_HOST`, `ASSAYR_WAIT_TIMEOUT`).
  - helpers: `make_bundle VERSION OUTDIR` → prints the bundle folder (built with the docker stub).

- [ ] **Step 1: Write the failing tests**

Append to `deploy/installer/tests/helpers.bash`:
```bash

# make_bundle VERSION OUTDIR — build a bundle folder with the docker stub; prints its path.
make_bundle() {
  STUB_IMAGES_PRESENT="$(stub_images "$1")" \
    "$REPO_ROOT/scripts/build-bundle.sh" "$1" amd64 "$2" --no-archive >/dev/null
  printf '%s\n' "$2/assayr-$1"
}
```

`deploy/installer/tests/build_bundle.bats`:
```bash
setup() {
  load helpers
  load_libs
  use_docker_stub
  OUT="$BATS_TEST_TMPDIR/dist"
}

@test "a bundle holds the installer, the compose files, the images and checksums" {
  STUB_IMAGES_PRESENT="$(stub_images 1.2.3)" run "$REPO_ROOT/scripts/build-bundle.sh" 1.2.3 amd64 "$OUT" --no-archive
  [ "$status" -eq 0 ]
  local b="$OUT/assayr-1.2.3" f
  for f in assayr lib/main.sh lib/common.sh compose.yaml compose.https.yaml assayr.env.example \
    README-INSTALL.md VERSION ARCH SHA256SUMS images/IMAGES.txt; do
    [ -e "$b/$f" ] || { echo "missing $f"; return 1; }
  done
  [ "$(cat "$b/VERSION")" = 1.2.3 ]
  [ "$(cat "$b/ARCH")" = amd64 ]
  [ ! -e "$b/compose.build.yaml" ]
  [ "$(grep -c . "$b/images/IMAGES.txt")" -eq 4 ]
  grep -q "^assayr-api_1.2.3.tar assayr-api:1.2.3 sha256:" "$b/images/IMAGES.txt"
  grep -q "^clamav_clamav_1.4.tar clamav/clamav:1.4 sha256:" "$b/images/IMAGES.txt"
  [ -f "$b/images/postgres_16-alpine.tar" ]
  run verify_bundle "$b"
  [ "$status" -eq 0 ]
}

@test "the archive unpacks to the bundle folder" {
  STUB_IMAGES_PRESENT="$(stub_images 1.2.3)" run "$REPO_ROOT/scripts/build-bundle.sh" 1.2.3 arm64 "$OUT"
  [ "$status" -eq 0 ]
  [ -f "$OUT/assayr-1.2.3-linux-arm64-offline.tar.gz" ]
  run tar -tzf "$OUT/assayr-1.2.3-linux-arm64-offline.tar.gz"
  [[ "$output" == *"assayr-1.2.3/assayr"* ]]
  [[ "$output" == *"assayr-1.2.3/SHA256SUMS"* ]]
}

@test "a bundle can't be built without the Assayr images" {
  STUB_IMAGES_PRESENT="assayr-web:1.2.3 postgres:16-alpine clamav/clamav:1.4" \
    run "$REPO_ROOT/scripts/build-bundle.sh" 1.2.3 amd64 "$OUT" --no-archive
  [ "$status" -eq 1 ]
  [[ "$output" == *"Image assayr-api:1.2.3 is missing; build it first."* ]]
}

@test "the version and architecture are checked" {
  run "$REPO_ROOT/scripts/build-bundle.sh" v1.2.3 amd64 "$OUT"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Give a version like 0.2.0"* ]]
  run "$REPO_ROOT/scripts/build-bundle.sh" 1.2.3 x86 "$OUT"
  [ "$status" -eq 1 ]
  [[ "$output" == *"ARCH must be amd64 or arm64"* ]]
}

@test "load_images loads only the images that aren't there yet" {
  local b
  b="$(make_bundle 1.2.3 "$OUT")"
  : >"$STUB_LOG"
  STUB_IMAGES_PRESENT="postgres:16-alpine" run load_images "$b"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Image postgres:16-alpine is already loaded"* ]]
  [ "$(grep -c "^load -i " "$STUB_LOG")" -eq 3 ]
  grep -qF "load -i $b/images/assayr-api_1.2.3.tar" "$STUB_LOG"
}
```

`deploy/installer/tests/cli.bats`:
```bash
setup() {
  load helpers
  load_libs
  use_docker_stub
  OUT="$BATS_TEST_TMPDIR/dist"
}

@test "help lists the commands" {
  run "$INSTALLER/assayr" help
  [ "$status" -eq 0 ]
  local command
  for command in install upgrade status backup restore start stop restart logs create-admin uninstall version; do
    [[ "$output" == *"  $command"* ]] || { echo "help misses $command"; return 1; }
  done
}

@test "an unknown command is refused" {
  run "$INSTALLER/assayr" frobnicate
  [ "$status" -eq 1 ]
  [[ "$output" == *"Unknown command: frobnicate"* ]]
}

@test "install must run from an unpacked bundle" {
  run "$INSTALLER/assayr" install
  [ "$status" -eq 1 ]
  [[ "$output" == *"Run install from an unpacked bundle"* ]]
}

@test "version reports the bundle's version and architecture" {
  local b
  b="$(make_bundle 1.2.3 "$OUT")"
  run "$b/assayr" version
  [ "$status" -eq 0 ]
  [ "$output" = "Assayr 1.2.3 (amd64)" ]
}

@test "installation commands say where they looked when nothing is installed" {
  run "$INSTALLER/assayr" status --dir "$BATS_TEST_TMPDIR/nothing here"
  [ "$status" -eq 1 ]
  [[ "$output" == *"No Assayr installation found in $BATS_TEST_TMPDIR/nothing here."* ]]
}

@test "installation commands on Linux need root" {
  ASSAYR_EUID=1000 run "$INSTALLER/assayr" status
  [ "$status" -eq 1 ]
  [[ "$output" == *"sudo ./assayr status"* ]]
}
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && bash deploy/installer/tests/run.sh`
Expected: FAIL — `build-bundle.sh: No such file or directory` in the bundle tests and `deploy/installer/assayr: No such file or directory` in the CLI tests.

- [ ] **Step 3: Implement the entry command and dispatch**

`deploy/installer/assayr`:
```bash
#!/usr/bin/env bash
# Assayr installer and administration command. Run ./assayr help for the commands.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_DIR=""
# shellcheck source=lib/common.sh
. "$SCRIPT_DIR/lib/common.sh"
# shellcheck source=lib/platform.sh
. "$SCRIPT_DIR/lib/platform.sh"
# shellcheck source=lib/envfile.sh
. "$SCRIPT_DIR/lib/envfile.sh"
# shellcheck source=lib/bundle.sh
. "$SCRIPT_DIR/lib/bundle.sh"
# shellcheck source=lib/checks.sh
. "$SCRIPT_DIR/lib/checks.sh"
# shellcheck source=lib/certs.sh
. "$SCRIPT_DIR/lib/certs.sh"
# shellcheck source=lib/compose.sh
. "$SCRIPT_DIR/lib/compose.sh"
# shellcheck source=lib/cmd_misc.sh
. "$SCRIPT_DIR/lib/cmd_misc.sh"
# shellcheck source=lib/main.sh
. "$SCRIPT_DIR/lib/main.sh"
main "$@"
```

`deploy/installer/lib/main.sh`:
```bash
# shellcheck shell=bash
# Argument handling and dispatch for ./assayr.

main() {
  local command="${1:-help}" dir="" args=()
  if [ $# -gt 0 ]; then shift; fi
  while [ $# -gt 0 ]; do
    case "$1" in
      --dir)
        need_value "$1" "${2:-}"
        dir="$2"
        shift 2
        ;;
      --yes)
        ASSAYR_ASSUME_YES=1
        shift
        ;;
      *)
        args+=("$1")
        shift
        ;;
    esac
  done
  case "$command" in
    install | upgrade)
      [ -d "$SCRIPT_DIR/images" ] \
        || die "Run $command from an unpacked bundle (the folder that contains the images folder)."
      BUNDLE_DIR="$SCRIPT_DIR"
      if [ -n "$dir" ]; then args+=(--dir "$dir"); fi
      "cmd_$command" ${args[@]+"${args[@]}"}
      ;;
    status | start | stop | restart | logs | backup | restore | create-admin | uninstall)
      use_installation "$command" "$dir"
      "cmd_$(printf '%s' "$command" | tr - _)" ${args[@]+"${args[@]}"}
      ;;
    version) cmd_version ;;
    help | -h | --help) usage ;;
    *)
      usage >&2
      die "Unknown command: $command"
      ;;
  esac
}

# use_installation COMMAND DIR — find the installation (DIR, the folder this command lives in,
# or the platform default), then log to its install.log.
use_installation() {
  local command="$1" dir="$2" platform
  platform="$(detect_platform)"
  [ "$platform" != unsupported ] || die "This system isn't supported. Use Linux, macOS, or Windows inside WSL."
  require_privileges "$platform" "$command"
  if [ -z "$dir" ]; then
    if [ -f "$SCRIPT_DIR/assayr.env" ]; then dir="$SCRIPT_DIR"; else dir="$(default_install_dir "$platform")"; fi
  fi
  [ -f "$dir/assayr.env" ] || die "No Assayr installation found in $dir. Add --dir if it is installed elsewhere."
  ASSAYR_DIR="$(cd "$dir" && pwd)"
  log_to "$ASSAYR_DIR/install.log"
}
```

`deploy/installer/lib/cmd_misc.sh`:
```bash
# shellcheck shell=bash
# Day-to-day commands for an installation.

usage() {
  cat <<'EOF'
Assayr installer and administration

From an unpacked bundle:
  install        Install Assayr (asks a few questions; see README-INSTALL.md)
                   --dir DIR  --license FILE  --http  --https-port N  --http-port N  --non-interactive
  upgrade        Upgrade an installation to this bundle's version (backs up first, rolls back on failure)
                   --dir DIR

From the installation folder (or with --dir DIR):
  status         Version, address, services and free disk
  backup         Back up the database, evidence files and settings   --to DIR
  restore        Replace all data with a backup                      FILE [--yes]
  start          Start Assayr
  stop           Stop Assayr
  restart        Restart Assayr (after changing assayr.env or the certificate)
  logs           Follow the logs                                     [SERVICE]
  create-admin   Create another administrator account
  uninstall      Stop and remove the containers; --delete-data also deletes all data
  version        Show the version
  help           Show this help
EOF
}

cmd_version() {
  echo "Assayr $(bundle_value "$SCRIPT_DIR" VERSION || echo unknown) ($(bundle_value "$SCRIPT_DIR" ARCH || echo unknown))"
}
```

- [ ] **Step 4: Implement the settings template and the install guide**

`deploy/installer/assayr.env.example`:
```
# Assayr settings. The installer writes assayr.env from this file.
# To change a setting later, edit assayr.env and run: ./assayr restart
# Values are plain text: no quotes, no $ signs.

# Version of the Assayr images to run (set by install and upgrade; don't edit).
ASSAYR_VERSION=
# Database password (generated by the installer; letters and digits only; don't edit).
POSTGRES_PASSWORD=
# Hostname users type in the browser.
ASSAYR_HOSTNAME=localhost
ASSAYR_ORG_NAME=My Organization
# https (default) or http (evaluation, or behind your own HTTPS proxy).
ASSAYR_WEB_MODE=https
ASSAYR_HTTPS_PORT=443
ASSAYR_HTTP_PORT=80
# Must be true whenever users reach Assayr over HTTPS.
ASSAYR_SECURE_COOKIES=true
# Largest evidence file accepted, in MB.
ASSAYR_MAX_UPLOAD_MB=100
# Malware scanning with the bundled ClamAV: true or false.
ASSAYR_MALWARE_SCAN=true
ASSAYR_CLAMAV_HOST=clamav
# Seconds to wait for all services to become healthy when starting.
ASSAYR_WAIT_TIMEOUT=600
```

`deploy/installer/README-INSTALL.md`:
````markdown
# Installing Assayr

Assayr runs on your own server. Everything it needs is in this bundle: no internet access is
needed to install or run it.

| Where | Use |
|---|---|
| Linux server (x86-64 or arm64) | Production |
| macOS with Docker Desktop or Colima | Evaluation only |
| Windows 10/11 with Docker Desktop and WSL2 | Evaluation only |

## What you need

- Docker Engine 24 or newer with the Compose plugin (2.17 or newer). On macOS and Windows, Docker Desktop.
- 4 CPU cores, 8 GB of memory (16 GB recommended), 100 GB of free disk.
- Ports 443 and 80 free (or choose others with `--https-port` and `--http-port`).
- `openssl`, unless you bring your own certificate (it is installed on almost every system).
- The right bundle for the machine: `linux-amd64` for Intel/AMD servers, Windows PCs and Intel Macs;
  `linux-arm64` for Apple Silicon Macs (M1–M4) and arm64 servers.

## 1. Check the download

Compare the checksum with the one published on the release page (or sent to you separately):

```bash
sha256sum assayr-0.2.0-linux-amd64-offline.tar.gz      # Linux and WSL
shasum -a 256 assayr-0.2.0-linux-amd64-offline.tar.gz  # macOS
```

For a server without internet access, copy the file across by your usual means (USB drive,
internal file transfer) after checking it.

## 2. Install

### Linux (production)

```bash
tar -xzf assayr-0.2.0-linux-amd64-offline.tar.gz
cd assayr-0.2.0
sudo ./assayr install
```

The installer checks the machine and the bundle, then asks for:

- the **hostname** users will type in the browser (for example `grc.example.local`);
- your **organisation name**;
- an **HTTPS certificate** and key from your certificate authority — or press Enter and it creates a
  self-signed certificate (browsers warn about it until you replace it);
- the **first administrator's** email and password (at least 12 characters).

It installs to `/opt/assayr`, starts Assayr and prints the address. Open it in a browser and sign in.

### macOS (evaluation)

1. Install and start Docker Desktop (Settings > Resources: give it at least 6 GB of memory).
2. In Terminal:
   ```bash
   tar -xzf assayr-0.2.0-linux-arm64-offline.tar.gz   # amd64 on an Intel Mac
   cd assayr-0.2.0
   ./assayr install
   ```
3. Open `https://localhost` and accept the certificate warning.

It installs to `~/assayr`.

### Windows (evaluation)

1. Install Docker Desktop with the WSL 2 backend, and Ubuntu from the Microsoft Store.
2. In Docker Desktop, Settings > Resources > WSL integration: turn it on for Ubuntu.
3. Open **Ubuntu** from the Start menu, copy the bundle into your Linux home folder, and run:
   ```bash
   tar -xzf assayr-0.2.0-linux-amd64-offline.tar.gz
   cd assayr-0.2.0
   ./assayr install
   ```
4. Open `https://localhost` in your Windows browser and accept the certificate warning.

It installs to `~/assayr` inside Ubuntu.

### Install without questions

Give every answer as an environment variable and add `--non-interactive`:

```bash
sudo ASSAYR_HOSTNAME=grc.example.local ASSAYR_ORG_NAME="Example Bank" \
  ASSAYR_ADMIN_EMAIL=isms@example.com ASSAYR_ADMIN_PASSWORD='a long password' \
  ASSAYR_TLS_CERT=/root/grc.crt ASSAYR_TLS_KEY=/root/grc.key \
  ./assayr install --non-interactive
```

Leave out `ASSAYR_TLS_CERT` and `ASSAYR_TLS_KEY` for a self-signed certificate. Other options:
`--dir DIR` (another install folder), `--license FILE`, `--https-port N`, `--http-port N`,
`ASSAYR_MALWARE_SCAN=false` (no ClamAV; saves about 2 GB of memory), and `--http` (plain HTTP on
port 8080 for evaluation, or behind your own HTTPS proxy — set `ASSAYR_BEHIND_TLS_PROXY=yes` then).

## Day to day

Run these from the install folder (`/opt/assayr`, with `sudo`, on Linux; `~/assayr` elsewhere):

| Command | What it does |
|---|---|
| `./assayr status` | Version, address, services, free disk |
| `./assayr backup` | Back up the database, evidence files and settings to `backups/` |
| `./assayr restore FILE` | Replace all data with a backup (takes a safety backup first) |
| `./assayr stop` / `start` / `restart` | Stop, start or restart Assayr |
| `./assayr logs [api\|worker\|web\|db]` | Follow the logs |
| `./assayr create-admin` | Create another administrator (for example when one forgot their password) |
| `./assayr uninstall` | Stop and remove the containers; data stays. `--delete-data` removes everything |

## HTTPS certificate

To replace the self-signed certificate: put your certificate (with any intermediate certificates
after it) in `certs/tls.crt` and its key in `certs/tls.key` inside the install folder, then run
`./assayr restart`.

## Backups

Back up regularly, for example every night with cron (`0 2 * * * /opt/assayr/assayr backup`), and
copy the files in `backups/` to another machine. A backup contains the database password and the
HTTPS private key: keep backups where only administrators can read them.

To move Assayr to a new server: install the same version there, copy a backup across, and run
`./assayr restore FILE`.

## Upgrading

Unpack the new bundle anywhere and run its `upgrade` command:

```bash
tar -xzf assayr-0.3.0-linux-amd64-offline.tar.gz
cd assayr-0.3.0
sudo ./assayr upgrade
```

It backs up first, then installs the new version. If the new version doesn't start, it puts the
previous version and your data back automatically and tells you so.

## Troubleshooting

Every command writes what it did to `install.log` in the install folder (no passwords are ever
written there). `./assayr status` and `./assayr logs api` are the first things to check.
````

- [ ] **Step 5: Implement the bundle build**

`scripts/build-bundle.sh`:
```bash
#!/usr/bin/env bash
# Assemble an offline installer bundle from images on this machine.
# Usage: scripts/build-bundle.sh VERSION ARCH OUTDIR [--no-archive]
# Needs assayr-api:VERSION and assayr-web:VERSION built locally; pulls the third-party images
# listed in deploy/compose.yaml when they are missing.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../deploy/installer/lib/common.sh
. "$REPO/deploy/installer/lib/common.sh"
# shellcheck source=../deploy/installer/lib/bundle.sh
. "$REPO/deploy/installer/lib/bundle.sh"

version="${1:-}"
arch="${2:-}"
out="${3:-}"
archive=1
if [ "${4:-}" = --no-archive ]; then archive=0; fi
version_valid "$version" || die "Give a version like 0.2.0 (got '$version')."
case "$arch" in amd64 | arm64) ;; *) die "ARCH must be amd64 or arm64 (got '$arch')." ;; esac
[ -n "$out" ] || die "Give an output folder."

installer="$REPO/deploy/installer"
bundle="$out/assayr-$version"
rm -rf "$bundle"
mkdir -p "$bundle/images"
cp "$installer/assayr" "$installer/assayr.env.example" "$installer/README-INSTALL.md" "$bundle/"
cp -R "$installer/lib" "$bundle/lib"
cp "$REPO/deploy/compose.yaml" "$REPO/deploy/compose.https.yaml" "$bundle/"
chmod 755 "$bundle/assayr"
printf '%s\n' "$version" >"$bundle/VERSION"
printf '%s\n' "$arch" >"$bundle/ARCH"

images="$(ASSAYR_VERSION="$version" POSTGRES_PASSWORD=unused \
  docker compose -f "$bundle/compose.yaml" --profile av config --images | LC_ALL=C sort -u)"
: >"$bundle/images/IMAGES.txt"
# shellcheck disable=SC2086 # one image reference per word
for ref in $images; do
  case "$ref" in
    assayr-*) docker image inspect "$ref" >/dev/null 2>&1 || die "Image $ref is missing; build it first." ;;
    *) docker image inspect "$ref" >/dev/null 2>&1 || docker pull "$ref" >/dev/null ;;
  esac
  file="$(printf '%s' "$ref" | tr '/:' '__').tar"
  info "Saving $ref"
  docker save -o "$bundle/images/$file" "$ref"
  printf '%s %s %s\n' "$file" "$ref" "$(docker image inspect --format '{{.Id}}' "$ref")" >>"$bundle/images/IMAGES.txt"
done

write_sums "$bundle"
if [ "$archive" = 1 ]; then
  tarball="$out/assayr-$version-linux-$arch-offline.tar.gz"
  tar -C "$out" -czf "$tarball" "assayr-$version"
  info "Bundle written to $tarball"
else
  info "Bundle folder written to $bundle"
fi
```

- [ ] **Step 6: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && bash deploy/installer/tests/run.sh`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && git add -A && git add --chmod=+x deploy/installer/assayr scripts/build-bundle.sh && git commit -m "feat(installer): bundle build, entry command, settings template and install guide"
```

---
### Task 5: `install` and the day-to-day commands

**Files:**
- Create: `deploy/installer/lib/cmd_install.sh`
- Modify: `deploy/installer/assayr` (source the new library), `deploy/installer/lib/cmd_misc.sh`, `deploy/installer/tests/helpers.bash`
- Test: `deploy/installer/tests/install.bats`, `deploy/installer/tests/cli.bats` (append)

**Interfaces:**
- Consumes: Tasks 2–4 (`ask`, `ask_password`, `*_problem`, `detect_platform`, `require_privileges`, `check_*`, `verify_bundle`, `copy_program_files`, `load_images`, `env_set`, `random_password`, `make_self_signed`, `cert_fingerprint`, `start_stack`, `api_ready`, `install_url`, `create_admin_account`, `assayr_compose`, `confirm_word`, `make_bundle`).
- Produces:
  - `cmd_install [--dir DIR] [--license FILE] [--http] [--https-port N] [--http-port N] [--non-interactive]`; answers from `ASSAYR_HOSTNAME`, `ASSAYR_ORG_NAME`, `ASSAYR_TLS_CERT`, `ASSAYR_TLS_KEY`, `ASSAYR_BEHIND_TLS_PROXY`, `ASSAYR_ADMIN_EMAIL`, `ASSAYR_ADMIN_PASSWORD`, `ASSAYR_MALWARE_SCAN` (default `true`); helpers `collect_install_answers`, `write_install_env`, `install_certificate`, `print_install_summary`.
  - Install folder layout: `assayr`, `lib/`, `compose.yaml`, `compose.https.yaml`, `assayr.env.example`, `README-INSTALL.md`, `ARCH`, `VERSION`, `assayr.env` (600), `install.log` (600), `certs/tls.crt` (644) + `certs/tls.key` (600) in HTTPS mode, `license/` (700) with optional `assayr.lic` (600), `backups/` (700).
  - `cmd_status`, `cmd_start`, `cmd_stop`, `cmd_restart`, `cmd_logs [SERVICE]`, `cmd_create_admin [--non-interactive]`, `cmd_uninstall [--delete-data]` (with `--yes` from `main`).
  - helpers: `install_fixture BUNDLE DIR [install options]`.

- [ ] **Step 1: Write the failing tests**

Append to `deploy/installer/tests/helpers.bash`:
```bash

# install_fixture BUNDLE DIR [OPTIONS] — non-interactive install with the docker stub.
# STUB_IMAGES_PRESENT defaults to the bundle's images (set it to "" to make install load them).
install_fixture() {
  local bundle="$1" dir="$2"
  shift 2
  ASSAYR_HOSTNAME="${ASSAYR_HOSTNAME:-localhost}" ASSAYR_ORG_NAME="${ASSAYR_ORG_NAME-Test Org}" \
    ASSAYR_ADMIN_EMAIL="${ASSAYR_ADMIN_EMAIL-admin@example.com}" \
    ASSAYR_ADMIN_PASSWORD="${ASSAYR_ADMIN_PASSWORD:-test-password-123}" \
    STUB_IMAGES_PRESENT="${STUB_IMAGES_PRESENT-$(stub_images "$(cat "$bundle/VERSION")")}" \
    "$bundle/assayr" install --dir "$dir" --non-interactive --https-port 18443 --http-port 18080 "$@"
}
```

`deploy/installer/tests/install.bats`:
```bash
setup() {
  load helpers
  load_libs
  use_docker_stub
  BUNDLE="$(make_bundle 1.2.3 "$BATS_TEST_TMPDIR/dist")"
  DIR="$BATS_TEST_TMPDIR/install"
  : >"$STUB_LOG"
}

@test "install writes the settings and a certificate, starts Assayr and creates the administrator" {
  run install_fixture "$BUNDLE" "$DIR"
  [ "$status" -eq 0 ]
  local env="$DIR/assayr.env"
  [ "$(env_get ASSAYR_VERSION "$env")" = 1.2.3 ]
  [ "$(env_get ASSAYR_WEB_MODE "$env")" = https ]
  [ "$(env_get ASSAYR_HTTPS_PORT "$env")" = 18443 ]
  [ "$(env_get ASSAYR_HTTP_PORT "$env")" = 18080 ]
  [ "$(env_get ASSAYR_SECURE_COOKIES "$env")" = true ]
  [ "$(env_get ASSAYR_ORG_NAME "$env")" = "Test Org" ]
  [ "$(env_get ASSAYR_CLAMAV_HOST "$env")" = clamav ]
  [[ "$(env_get POSTGRES_PASSWORD "$env")" =~ ^[A-Za-z0-9]{32}$ ]]
  [ -f "$DIR/certs/tls.crt" ] && [ -f "$DIR/certs/tls.key" ]
  [ "$(cat "$DIR/VERSION")" = 1.2.3 ]
  [ -x "$DIR/assayr" ] || on_windows
  grep -q "up -d --wait --wait-timeout 600" "$STUB_LOG"
  grep -q "create-admin --email admin@example.com" "$STUB_LOG"
  [[ "$output" == *"Assayr 1.2.3 is running."* ]]
  [[ "$output" == *"Address:        https://localhost:18443"* ]]
  [[ "$output" == *"self-signed, SHA-256 fingerprint"* ]]
}

@test "the administrator password never reaches a command line, the log or the screen" {
  run install_fixture "$BUNDLE" "$DIR"
  [ "$status" -eq 0 ]
  run grep -c "test-password-123" "$STUB_LOG" "$DIR/install.log"
  [[ "$output" == *"docker.log:0"* ]]
  [[ "$output" == *"install.log:0"* ]]
}

@test "settings, keys and the log are readable by the owner only" {
  skip_on_windows
  install_fixture "$BUNDLE" "$DIR"
  [ "$(file_mode "$DIR/assayr.env")" = "rw-------" ]
  [ "$(file_mode "$DIR/certs/tls.key")" = "rw-------" ]
  [ "$(file_mode "$DIR/install.log")" = "rw-------" ]
  [ "$(file_mode "$DIR/backups")" = "rwx------" ]
}

@test "install refuses to run over an existing installation" {
  install_fixture "$BUNDLE" "$DIR"
  run install_fixture "$BUNDLE" "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Assayr is already installed in $DIR."* ]]
  [[ "$output" == *"./assayr upgrade"* ]]
}

@test "install refuses an organisation name that would break the settings file" {
  ASSAYR_ORG_NAME='Acme $HOME' run install_fixture "$BUNDLE" "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Organisation name can't contain"* ]]
  [ ! -e "$DIR" ]
}

@test "install without an administrator email fails when running without questions" {
  ASSAYR_ADMIN_EMAIL="" run install_fixture "$BUNDLE" "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Set ASSAYR_ADMIN_EMAIL when using --non-interactive."* ]]
}

@test "--http serves plain HTTP with secure cookies off, unless a proxy adds HTTPS" {
  run install_fixture "$BUNDLE" "$DIR" --http
  [ "$status" -eq 0 ]
  [ "$(env_get ASSAYR_WEB_MODE "$DIR/assayr.env")" = http ]
  [ "$(env_get ASSAYR_SECURE_COOKIES "$DIR/assayr.env")" = false ]
  [ ! -e "$DIR/certs/tls.crt" ]
  [[ "$output" == *"plain HTTP"* ]]
  [[ "$output" == *"http://localhost:18080"* ]]
  run grep -c compose.https.yaml "$STUB_LOG"
  [ "$output" = 0 ]

  local proxied="$BATS_TEST_TMPDIR/proxied"
  ASSAYR_BEHIND_TLS_PROXY=yes run install_fixture "$BUNDLE" "$proxied" --http
  [ "$status" -eq 0 ]
  [ "$(env_get ASSAYR_SECURE_COOKIES "$proxied/assayr.env")" = true ]
}

@test "install works in a folder whose path has spaces" {
  local spaced="$BATS_TEST_TMPDIR/my apps/assayr"
  run install_fixture "$BUNDLE" "$spaced"
  [ "$status" -eq 0 ]
  [ -f "$spaced/assayr.env" ]
  grep -qF -- "--project-directory $spaced " "$STUB_LOG"
}

@test "a modified bundle is refused before anything is written" {
  echo "# changed" >>"$BUNDLE/compose.yaml"
  run install_fixture "$BUNDLE" "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"This bundle is damaged or was modified: ./compose.yaml does not match its checksum."* ]]
  [ ! -e "$DIR" ]
}

@test "a bundle for another architecture is refused" {
  STUB_ARCH=aarch64 run install_fixture "$BUNDLE" "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"this machine is arm64"* ]]
}

@test "a licence file is copied in for the application" {
  echo "licence-data" >"$BATS_TEST_TMPDIR/acme.lic"
  run install_fixture "$BUNDLE" "$DIR" --license "$BATS_TEST_TMPDIR/acme.lic"
  [ "$status" -eq 0 ]
  [ "$(cat "$DIR/license/assayr.lic")" = licence-data ]
}

@test "images that aren't loaded yet are loaded from the bundle" {
  STUB_IMAGES_PRESENT="" run install_fixture "$BUNDLE" "$DIR"
  [ "$status" -eq 0 ]
  [ "$(grep -c "^load -i " "$STUB_LOG")" -eq 4 ]
}

@test "when Assayr doesn't start, install says how to start again" {
  STUB_FAIL_ON="--wait-timeout" run install_fixture "$BUNDLE" "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Assayr did not start."* ]]
  [[ "$output" == *"uninstall --delete-data, then run install again."* ]]
}

@test "on Linux install needs root" {
  ASSAYR_EUID=1000 run install_fixture "$BUNDLE" "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"sudo ./assayr install"* ]]
}

@test "on macOS it installs in the home folder and says it is for evaluation" {
  export HOME="$BATS_TEST_TMPDIR/home"
  mkdir -p "$HOME"
  ASSAYR_UNAME_S=Darwin ASSAYR_EUID=501 ASSAYR_HOSTNAME=localhost ASSAYR_ORG_NAME="Test Org" \
    ASSAYR_ADMIN_EMAIL=admin@example.com ASSAYR_ADMIN_PASSWORD=test-password-123 \
    STUB_IMAGES_PRESENT="$(stub_images 1.2.3)" \
    run "$BUNDLE/assayr" install --non-interactive --https-port 18443 --http-port 18080
  [ "$status" -eq 0 ]
  [ -f "$HOME/assayr/assayr.env" ]
  [[ "$output" == *"for evaluation"* ]]
}
```

Append to `deploy/installer/tests/cli.bats`:
```bash

@test "status shows the version, the address and whether the application is ready" {
  local b dir="$BATS_TEST_TMPDIR/install"
  b="$(make_bundle 1.2.3 "$OUT")"
  install_fixture "$b" "$dir" >/dev/null
  run "$dir/assayr" status
  [ "$status" -eq 0 ]
  [[ "$output" == *"Assayr 1.2.3 (amd64) in $dir"* ]]
  [[ "$output" == *"Address: https://localhost:18443"* ]]
  [[ "$output" == *"Application: ready"* ]]
}

@test "stop, start and restart drive the stack" {
  local b dir="$BATS_TEST_TMPDIR/install"
  b="$(make_bundle 1.2.3 "$OUT")"
  install_fixture "$b" "$dir" >/dev/null
  : >"$STUB_LOG"
  run "$dir/assayr" restart
  [ "$status" -eq 0 ]
  grep -q " stop$" "$STUB_LOG"
  grep -q "up -d --wait --wait-timeout 600$" "$STUB_LOG"
  [[ "$output" == *"Assayr is running at https://localhost:18443"* ]]
}

@test "create-admin creates another administrator without exposing the password" {
  local b dir="$BATS_TEST_TMPDIR/install"
  b="$(make_bundle 1.2.3 "$OUT")"
  install_fixture "$b" "$dir" >/dev/null
  : >"$STUB_LOG"
  ASSAYR_ADMIN_EMAIL=second@example.com ASSAYR_ADMIN_PASSWORD=another-password-456 \
    run "$dir/assayr" create-admin --non-interactive
  [ "$status" -eq 0 ]
  grep -q "create-admin --email second@example.com" "$STUB_LOG"
  run grep -c "another-password-456" "$STUB_LOG"
  [ "$output" = 0 ]
}

@test "uninstall keeps the data unless asked to delete it, and deleting needs confirmation" {
  local b dir="$BATS_TEST_TMPDIR/install"
  b="$(make_bundle 1.2.3 "$OUT")"
  install_fixture "$b" "$dir" >/dev/null
  : >"$STUB_LOG"
  run "$dir/assayr" uninstall
  [ "$status" -eq 0 ]
  grep -q "down --remove-orphans$" "$STUB_LOG"
  [ -f "$dir/assayr.env" ]

  run "$dir/assayr" uninstall --delete-data </dev/null
  [ "$status" -eq 1 ]
  [[ "$output" == *"Cancelled; nothing was changed."* ]]
  [ -f "$dir/assayr.env" ]

  run "$dir/assayr" uninstall --delete-data --yes
  [ "$status" -eq 0 ]
  grep -q "down -v --remove-orphans$" "$STUB_LOG"
  grep -q "image rm assayr-api:1.2.3 assayr-web:1.2.3" "$STUB_LOG"
  [ ! -e "$dir" ]
}
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && bash deploy/installer/tests/run.sh`
Expected: FAIL — install tests fail with `cmd_install: command not found`; the new CLI tests fail at `install_fixture` for the same reason.

- [ ] **Step 3: Implement install**

In `deploy/installer/assayr`, add before the `cmd_misc.sh` line:
```bash
# shellcheck source=lib/cmd_install.sh
. "$SCRIPT_DIR/lib/cmd_install.sh"
```

`deploy/installer/lib/cmd_install.sh`:
```bash
# shellcheck shell=bash
# ./assayr install — the first installation, from an unpacked bundle.

cmd_install() {
  local dir="" license="" web_mode=https https_port=443 http_port="" platform problem
  while [ $# -gt 0 ]; do
    case "$1" in
      --dir)
        need_value "$1" "${2:-}"
        dir="$2"
        shift 2
        ;;
      --license)
        need_value "$1" "${2:-}"
        license="$2"
        shift 2
        ;;
      --http)
        web_mode=http
        shift
        ;;
      --https-port)
        need_value "$1" "${2:-}"
        https_port="$2"
        shift 2
        ;;
      --http-port)
        need_value "$1" "${2:-}"
        http_port="$2"
        shift 2
        ;;
      --non-interactive)
        ASSAYR_INTERACTIVE=0
        shift
        ;;
      *) die "Unknown option for install: $1. Run ./assayr help." ;;
    esac
  done
  if [ -z "$http_port" ]; then
    if [ "$web_mode" = https ]; then http_port=80; else http_port=8080; fi
  fi
  problem="$(port_problem "$https_port")$(port_problem "$http_port")"
  [ -z "$problem" ] || die "$problem"

  platform="$(detect_platform)"
  [ "$platform" != unsupported ] || die "This system isn't supported. Install on Linux, on macOS, or on Windows inside WSL."
  require_privileges "$platform" install
  evaluation_notice "$platform"
  dir="${dir:-$(default_install_dir "$platform")}"
  [ ! -f "$dir/assayr.env" ] \
    || die "Assayr is already installed in $dir. To move to a newer version, run ./assayr upgrade from the new bundle."

  info "Checking this machine"
  check_docker "$platform"
  check_arch "$(bundle_value "$BUNDLE_DIR" ARCH)"
  check_disk "$dir"
  check_memory
  check_port "$http_port" --http-port
  if [ "$web_mode" = https ]; then check_port "$https_port" --https-port; fi
  if [ -n "$license" ] && [ ! -f "$license" ]; then die "Licence file not found: $license"; fi

  info "Checking the bundle"
  problem="$(verify_bundle "$BUNDLE_DIR")" \
    || die "This bundle is damaged or was modified: $problem Download it again and compare its checksum with the one on the release page."

  collect_install_answers "$platform" "$web_mode"

  info "Writing the installation to $dir"
  mkdir -p "$dir"
  ASSAYR_DIR="$(cd "$dir" && pwd)"
  log_to "$ASSAYR_DIR/install.log"
  ASSAYR_RETRY_HINT="To start again: $(sudo_prefix)$ASSAYR_DIR/assayr uninstall --delete-data, then run install again."
  copy_program_files "$BUNDLE_DIR" "$ASSAYR_DIR"
  cp "$BUNDLE_DIR/VERSION" "$ASSAYR_DIR/VERSION"
  mkdir -p "$ASSAYR_DIR/certs" "$ASSAYR_DIR/license" "$ASSAYR_DIR/backups"
  chmod 700 "$ASSAYR_DIR/license" "$ASSAYR_DIR/backups"
  write_install_env "$web_mode" "$https_port" "$http_port"
  install_certificate "$web_mode"
  if [ -n "$license" ]; then
    cp "$license" "$ASSAYR_DIR/license/assayr.lic"
    chmod 600 "$ASSAYR_DIR/license/assayr.lic"
  fi

  info "Loading the container images (this takes a few minutes)"
  load_images "$BUNDLE_DIR" || die "Loading the images failed."
  info "Starting Assayr (the first start prepares the database)"
  start_stack || die "Assayr did not start. See $(sudo_prefix)$ASSAYR_DIR/assayr logs api"
  info "Creating the administrator account"
  create_admin_account "$ASSAYR_ADMIN_EMAIL" "$ASSAYR_ADMIN_PASSWORD" \
    || die "Assayr is running, but creating the administrator failed. Try again with: $(sudo_prefix)$ASSAYR_DIR/assayr create-admin"
  ASSAYR_RETRY_HINT=""
  print_install_summary "$web_mode"
}

collect_install_answers() {
  local platform="$1" web_mode="$2" problem
  ask ASSAYR_HOSTNAME "Hostname users will type in the browser" "$(default_hostname "$platform")"
  problem="$(hostname_problem "$ASSAYR_HOSTNAME")"
  [ -z "$problem" ] || die "$problem"
  ask ASSAYR_ORG_NAME "Organisation name" "My Organization"
  problem="$(text_problem "Organisation name" "$ASSAYR_ORG_NAME")"
  [ -z "$problem" ] || die "$problem"
  if [ "$web_mode" = https ]; then
    ask ASSAYR_TLS_CERT "HTTPS certificate file (press Enter to create a self-signed one)" "" optional
    if [ -n "$ASSAYR_TLS_CERT" ]; then
      ask ASSAYR_TLS_KEY "Private key file for that certificate"
      [ -f "$ASSAYR_TLS_CERT" ] || die "Certificate file not found: $ASSAYR_TLS_CERT"
      [ -f "$ASSAYR_TLS_KEY" ] || die "Key file not found: $ASSAYR_TLS_KEY"
    else
      check_openssl
    fi
  else
    ask ASSAYR_BEHIND_TLS_PROXY "Is there an HTTPS proxy in front of Assayr? (yes/no)" "no"
  fi
  ask ASSAYR_ADMIN_EMAIL "Administrator email"
  problem="$(email_problem "$ASSAYR_ADMIN_EMAIL")"
  [ -z "$problem" ] || die "$problem"
  ask_password ASSAYR_ADMIN_PASSWORD
}

write_install_env() {
  local web_mode="$1" https_port="$2" http_port="$3" env="$ASSAYR_DIR/assayr.env"
  local secure=true scan="${ASSAYR_MALWARE_SCAN:-true}"
  if [ "$web_mode" = http ]; then
    case "${ASSAYR_BEHIND_TLS_PROXY:-no}" in
      y | Y | yes | Yes | YES) secure=true ;;
      *)
        secure=false
        warn "Assayr will be served over plain HTTP. Use this only for evaluation."
        ;;
    esac
  fi
  (umask 077 && cp "$ASSAYR_DIR/assayr.env.example" "$env")
  env_set ASSAYR_VERSION "$(bundle_value "$BUNDLE_DIR" VERSION)" "$env"
  env_set POSTGRES_PASSWORD "$(random_password)" "$env"
  env_set ASSAYR_HOSTNAME "$ASSAYR_HOSTNAME" "$env"
  env_set ASSAYR_ORG_NAME "$ASSAYR_ORG_NAME" "$env"
  env_set ASSAYR_WEB_MODE "$web_mode" "$env"
  env_set ASSAYR_HTTPS_PORT "$https_port" "$env"
  env_set ASSAYR_HTTP_PORT "$http_port" "$env"
  env_set ASSAYR_SECURE_COOKIES "$secure" "$env"
  env_set ASSAYR_MALWARE_SCAN "$scan" "$env"
  if [ "$scan" = true ]; then
    env_set ASSAYR_CLAMAV_HOST clamav "$env"
  else
    env_set ASSAYR_CLAMAV_HOST "" "$env"
  fi
}

install_certificate() {
  local cert="$ASSAYR_DIR/certs/tls.crt" key="$ASSAYR_DIR/certs/tls.key"
  [ "$1" = https ] || return 0
  if [ -n "${ASSAYR_TLS_CERT:-}" ]; then
    cp "$ASSAYR_TLS_CERT" "$cert"
    (umask 077 && cp "$ASSAYR_TLS_KEY" "$key")
  else
    info "Creating a self-signed certificate for $ASSAYR_HOSTNAME"
    make_self_signed "$ASSAYR_HOSTNAME" "$cert" "$key" || die "Creating the self-signed certificate failed."
  fi
  chmod 644 "$cert"
  chmod 600 "$key"
}

print_install_summary() {
  local sudo
  sudo="$(sudo_prefix)"
  echo
  echo "Assayr $(bundle_value "$ASSAYR_DIR" VERSION) is running."
  echo "  Address:        $(install_url)"
  echo "  Administrator:  $ASSAYR_ADMIN_EMAIL"
  if [ "$1" = https ] && [ -z "${ASSAYR_TLS_CERT:-}" ]; then
    echo "  Certificate:    self-signed, SHA-256 fingerprint $(cert_fingerprint "$ASSAYR_DIR/certs/tls.crt")"
    echo "                  Browsers warn about it until you replace it with one from your certificate authority."
  fi
  echo
  echo "Next steps:"
  echo "  - Back up regularly: $sudo$ASSAYR_DIR/assayr backup"
  if [ "$1" = https ]; then
    echo "  - To use your own certificate, replace tls.crt and tls.key in $ASSAYR_DIR/certs, then run: $sudo$ASSAYR_DIR/assayr restart"
  fi
  echo "  - Status and logs: $sudo$ASSAYR_DIR/assayr status, $sudo$ASSAYR_DIR/assayr logs"
}
```

- [ ] **Step 4: Implement the day-to-day commands**

Append to `deploy/installer/lib/cmd_misc.sh`:
```bash

cmd_status() {
  local backups
  echo "Assayr $(bundle_value "$ASSAYR_DIR" VERSION) ($(bundle_value "$ASSAYR_DIR" ARCH)) in $ASSAYR_DIR"
  echo "Address: $(install_url)"
  echo
  assayr_compose ps --format 'table {{.Service}}\t{{.State}}\t{{.Health}}' || true
  echo
  if api_ready; then
    echo "Application: ready"
  else
    echo "Application: not ready (see: $(sudo_prefix)$ASSAYR_DIR/assayr logs api)"
  fi
  backups="$(find "$ASSAYR_DIR/backups" -maxdepth 1 -name 'assayr-*.tar.gz' | wc -l | tr -d ' ')"
  echo "Backups: $backups in $ASSAYR_DIR/backups"
  df -Ph "$ASSAYR_DIR" | awk 'NR==2 {print "Free disk: " $4}'
}

cmd_start() {
  info "Starting Assayr"
  start_stack || die "Assayr did not start. See: $(sudo_prefix)$ASSAYR_DIR/assayr logs api"
  info "Assayr is running at $(install_url)"
}

cmd_stop() {
  info "Stopping Assayr"
  run_logged assayr_compose stop || die "Stopping Assayr failed."
}

cmd_restart() {
  cmd_stop
  cmd_start
}

cmd_logs() {
  assayr_compose logs --tail 200 --follow "$@"
}

cmd_create_admin() {
  local problem
  while [ $# -gt 0 ]; do
    case "$1" in
      --non-interactive)
        ASSAYR_INTERACTIVE=0
        shift
        ;;
      *) die "Unknown option for create-admin: $1" ;;
    esac
  done
  ask ASSAYR_ADMIN_EMAIL "Administrator email"
  problem="$(email_problem "$ASSAYR_ADMIN_EMAIL")"
  [ -z "$problem" ] || die "$problem"
  ask_password ASSAYR_ADMIN_PASSWORD
  info "Creating the administrator $ASSAYR_ADMIN_EMAIL"
  create_admin_account "$ASSAYR_ADMIN_EMAIL" "$ASSAYR_ADMIN_PASSWORD" \
    || die "Creating the administrator failed. A user with that email may already exist."
  info "Done. $ASSAYR_ADMIN_EMAIL can sign in at $(install_url)"
}

cmd_uninstall() {
  local delete=0 version
  while [ $# -gt 0 ]; do
    case "$1" in
      --delete-data)
        delete=1
        shift
        ;;
      *) die "Unknown option for uninstall: $1" ;;
    esac
  done
  if [ "$delete" = 0 ]; then
    info "Stopping Assayr and removing its containers"
    run_logged assayr_compose down --remove-orphans || die "Removing the containers failed."
    info "Done. The data, settings and backups are kept in $ASSAYR_DIR and in Docker volumes. To bring Assayr back: $(sudo_prefix)$ASSAYR_DIR/assayr start"
    return 0
  fi
  confirm_word delete "This permanently deletes Assayr and all its data: the database, the evidence files, the settings, the certificates and every backup in $ASSAYR_DIR."
  version="$(bundle_value "$ASSAYR_DIR" VERSION 2>/dev/null || true)"
  run_logged assayr_compose down -v --remove-orphans || die "Removing the containers and data volumes failed."
  if [ -n "$version" ]; then
    run_logged docker image rm "assayr-api:$version" "assayr-web:$version" || true
  fi
  ASSAYR_LOG=""
  rm -rf "${ASSAYR_DIR:?}"
  echo "Assayr has been removed."
}
```

- [ ] **Step 5: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && bash deploy/installer/tests/run.sh`
Expected: all tests pass (mode tests skip on Windows).

- [ ] **Step 6: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && git add -A && git commit -m "feat(installer): install, status, start, stop, create-admin and uninstall"
```

---
### Task 6: Backup and restore

**Files:**
- Create: `deploy/installer/lib/backup.sh`
- Modify: `deploy/installer/assayr` (source the new library), `deploy/installer/lib/cmd_misc.sh`
- Test: `deploy/installer/tests/backup.bats`

**Interfaces:**
- Consumes: Tasks 2–5 (`assayr_compose`, `start_stack`, `audit_ok`, `run_logged`, `write_sums`, `verify_bundle`, `bundle_value`, `env_get`, `version_gt`, `confirm_word`, `install_fixture`, `make_bundle`).
- Produces:
  - `do_backup DEST_DIR` → sets global `BACKUP_FILE` to `DEST_DIR/assayr-<version>-<UTC yyyymmddThhmmssZ>.tar.gz` (mode 600); returns 1 and leaves nothing behind on failure. Archive layout: one folder `assayr-<version>-<stamp>/` with `db.dump`, `blobs.tar`, `assayr.env`, `certs/`, `license/`, `manifest.txt` (`version=`, `created=`), `SHA256SUMS`.
  - `read_backup ARCHIVE WORKDIR` → sets `RESTORE_FOLDER`, or sets `RESTORE_PROBLEM` and returns 1.
  - `restore_data FOLDER` → replaces the database and evidence files, then starts the stack.
  - `cmd_backup [--to DIR]`, `cmd_restore FILE` (`--yes` from `main`).

- [ ] **Step 1: Write the failing tests**

`deploy/installer/tests/backup.bats`:
```bash
setup() {
  load helpers
  load_libs
  use_docker_stub
  BUNDLE="$(make_bundle 1.2.3 "$BATS_TEST_TMPDIR/dist")"
  DIR="$BATS_TEST_TMPDIR/install"
  install_fixture "$BUNDLE" "$DIR" >/dev/null
  : >"$STUB_LOG"
}

only_backup() {
  find "$DIR/backups" -maxdepth 1 -name 'assayr-*.tar.gz' | head -n 1
}

# repack_backup FILE EDIT — unpack FILE, run EDIT in its folder, write it back as FILE.
repack_backup() {
  local file="$1" edit="$2" work="$BATS_TEST_TMPDIR/repack" folder
  rm -rf "$work"
  mkdir -p "$work"
  tar -C "$work" -xzf "$file"
  folder="$(find "$work" -mindepth 1 -maxdepth 1 -type d)"
  (cd "$folder" && eval "$edit")
  tar -C "$work" -czf "$file" "$(basename "$folder")"
}

@test "backup writes one archive with the database, evidence files, settings and a manifest" {
  run "$DIR/assayr" backup
  [ "$status" -eq 0 ]
  [[ "$output" == *"Backup written to $DIR/backups/assayr-1.2.3-"* ]]
  [[ "$output" == *"where only administrators can read it"* ]]
  local file
  file="$(only_backup)"
  run tar -tzf "$file"
  local part
  for part in db.dump blobs.tar assayr.env certs/tls.crt certs/tls.key manifest.txt SHA256SUMS; do
    [[ "$output" == *"/$part"* ]] || { echo "missing $part"; return 1; }
  done
  grep -q "exec -T db pg_dump -U assayr -d assayr -Fc" "$STUB_LOG"
  [ -z "$(find "$DIR/backups" -name '.backup.*')" ]
}

@test "backup archives are readable by the owner only" {
  skip_on_windows
  "$DIR/assayr" backup >/dev/null
  [ "$(file_mode "$(only_backup)")" = "rw-------" ]
}

@test "backup --to writes the archive to another folder" {
  run "$DIR/assayr" backup --to "$BATS_TEST_TMPDIR/offsite copies"
  [ "$status" -eq 0 ]
  [ -n "$(find "$BATS_TEST_TMPDIR/offsite copies" -name 'assayr-1.2.3-*.tar.gz')" ]
}

@test "a failed backup leaves nothing behind" {
  STUB_FAIL_ON=pg_dump run "$DIR/assayr" backup
  [ "$status" -eq 1 ]
  [[ "$output" == *"The backup failed. Nothing was written."* ]]
  [ -z "$(find "$DIR/backups" -mindepth 1)" ]
}

@test "restore takes a safety backup, then puts back the database and the evidence files" {
  "$DIR/assayr" backup >/dev/null
  local file
  file="$(only_backup)"
  : >"$STUB_LOG"
  sleep 1 # the safety backup gets its own timestamp
  run "$DIR/assayr" restore "$file" --yes
  [ "$status" -eq 0 ]
  [[ "$output" == *"Restore complete. The audit trail is intact."* ]]
  [ "$(find "$DIR/backups" -maxdepth 1 -name 'assayr-*.tar.gz' | wc -l | tr -d ' ')" -eq 2 ]
  # line TEXT — line number in the docker log of the last call containing TEXT
  line() { grep -n -- "$1" "$STUB_LOG" | tail -n 1 | cut -d: -f1; }
  [ "$(line pg_dump)" -lt "$(line dropdb)" ]
  [ "$(line dropdb)" -lt "$(line createdb)" ]
  [ "$(line createdb)" -lt "$(line pg_restore)" ]
  [ "$(line pg_restore)" -lt "$(line 'tar -C /data/blobs -xf')" ]
  [ "$(line 'tar -C /data/blobs -xf')" -lt "$(line --wait-timeout)" ]
  [ -z "$(find "$DIR/backups" -name '.restore.*')" ]
}

@test "restore asks for confirmation" {
  "$DIR/assayr" backup >/dev/null
  run "$DIR/assayr" restore "$(only_backup)" </dev/null
  [ "$status" -eq 1 ]
  [[ "$output" == *"Cancelled; nothing was changed."* ]]
  run grep -c dropdb "$STUB_LOG"
  [ "$output" = 0 ]
}

@test "restore refuses a damaged backup" {
  echo "not a backup" >"$BATS_TEST_TMPDIR/broken.tar.gz"
  run "$DIR/assayr" restore "$BATS_TEST_TMPDIR/broken.tar.gz" --yes
  [ "$status" -eq 1 ]
  [[ "$output" == *"This backup can't be used: it can't be unpacked."* ]]

  "$DIR/assayr" backup >/dev/null
  local file
  file="$(only_backup)"
  repack_backup "$file" 'echo tampered >>db.dump'
  run "$DIR/assayr" restore "$file" --yes
  [ "$status" -eq 1 ]
  [[ "$output" == *"./db.dump does not match its checksum."* ]]
  run grep -c dropdb "$STUB_LOG"
  [ "$output" = 0 ]
}

@test "restore refuses a backup from a newer version" {
  "$DIR/assayr" backup >/dev/null
  local file
  file="$(only_backup)"
  repack_backup "$file" "printf 'version=9.9.9\ncreated=20991231T000000Z\n' >manifest.txt && . '$INSTALLER/lib/bundle.sh' && write_sums ."
  run "$DIR/assayr" restore "$file" --yes
  [ "$status" -eq 1 ]
  [[ "$output" == *"This backup was made by Assayr 9.9.9, which is newer than the installed 1.2.3."* ]]
}

@test "when the restore fails, it points to the safety backup" {
  "$DIR/assayr" backup >/dev/null
  local file
  file="$(only_backup)"
  sleep 1
  STUB_FAIL_ON=pg_restore run "$DIR/assayr" restore "$file" --yes
  [ "$status" -eq 1 ]
  [[ "$output" == *"The restore failed. The data from just before it is in $DIR/backups/assayr-1.2.3-"* ]]
}
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && bash deploy/installer/tests/run.sh`
Expected: FAIL — `backup` and `restore` fail with `cmd_backup: command not found` / `cmd_restore: command not found`.

- [ ] **Step 3: Implement backup and restore**

In `deploy/installer/assayr`, add before the `cmd_install.sh` line:
```bash
# shellcheck source=lib/backup.sh
. "$SCRIPT_DIR/lib/backup.sh"
```

`deploy/installer/lib/backup.sh`:
```bash
# shellcheck shell=bash
# Backups: one archive with the database dump, the evidence files, the settings and a manifest.

BACKUP_FILE=""
RESTORE_FOLDER=""
RESTORE_PROBLEM=""

# do_backup DEST_DIR — sets BACKUP_FILE. On failure returns 1 and leaves nothing behind.
do_backup() {
  local dest="$1" version stamp name work
  BACKUP_FILE=""
  version="$(bundle_value "$ASSAYR_DIR" VERSION)"
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  name="assayr-$version-$stamp"
  if [ ! -d "$dest" ]; then
    mkdir -p "$dest" || return 1
    chmod 700 "$dest"
  fi
  dest="$(cd "$dest" && pwd)"
  if [ -e "$dest/$name.tar.gz" ]; then name="$name-2"; fi
  work="$(mktemp -d "$dest/.backup.XXXXXX")" || return 1
  mkdir "$work/$name"
  if ! backup_parts "$work/$name"; then
    rm -rf "$work"
    return 1
  fi
  printf 'version=%s\ncreated=%s\n' "$version" "$stamp" >"$work/$name/manifest.txt"
  write_sums "$work/$name"
  if ! (umask 077 && tar -C "$work" -czf "$dest/$name.tar.gz" "$name"); then
    rm -rf "$work" "$dest/$name.tar.gz"
    return 1
  fi
  chmod 600 "$dest/$name.tar.gz"
  rm -rf "$work"
  BACKUP_FILE="$dest/$name.tar.gz"
}

backup_parts() {
  local part="$1"
  run_logged assayr_compose up -d --wait db || return 1
  _log_line "RUN pg_dump"
  assayr_compose exec -T db pg_dump -U assayr -d assayr -Fc >"$part/db.dump" 2>>"${ASSAYR_LOG:-/dev/null}" || return 1
  run_logged assayr_compose run --rm --no-deps -T --user root --entrypoint tar -v "$part:/backup" api \
    -C /data/blobs -cf /backup/blobs.tar . || return 1
  cp "$ASSAYR_DIR/assayr.env" "$part/assayr.env"
  cp -R "$ASSAYR_DIR/certs" "$part/certs"
  cp -R "$ASSAYR_DIR/license" "$part/license"
}

# read_backup ARCHIVE WORKDIR — unpack and check a backup. Sets RESTORE_FOLDER, or sets
# RESTORE_PROBLEM and returns 1.
read_backup() {
  local archive="$1" work="$2" folder problem
  RESTORE_FOLDER=""
  RESTORE_PROBLEM=""
  if ! tar -C "$work" -xzf "$archive" 2>/dev/null; then
    RESTORE_PROBLEM="it can't be unpacked."
    return 1
  fi
  folder="$(find "$work" -mindepth 1 -maxdepth 1 -type d -name 'assayr-*' | head -n 1)"
  if [ -z "$folder" ] || [ ! -f "$folder/manifest.txt" ]; then
    RESTORE_PROBLEM="it has no manifest."
    return 1
  fi
  if ! problem="$(verify_bundle "$folder")"; then
    RESTORE_PROBLEM="$problem"
    return 1
  fi
  RESTORE_FOLDER="$folder"
}

# restore_data FOLDER — replace the database and the evidence files, then start Assayr.
restore_data() {
  local folder="$1"
  run_logged assayr_compose stop api worker web || return 1
  run_logged assayr_compose up -d --wait db || return 1
  run_logged assayr_compose exec -T db dropdb -U assayr --if-exists assayr || return 1
  run_logged assayr_compose exec -T db createdb -U assayr -O assayr assayr || return 1
  _log_line "RUN pg_restore"
  assayr_compose exec -T db pg_restore -U assayr -d assayr --no-owner --exit-on-error \
    <"$folder/db.dump" >>"${ASSAYR_LOG:-/dev/null}" 2>&1 || return 1
  run_logged assayr_compose run --rm --no-deps -T --user root --entrypoint sh -v "$folder:/backup:ro" api \
    -c 'find /data/blobs -mindepth 1 -delete && tar -C /data/blobs -xf /backup/blobs.tar && chown -R assayr:assayr /data/blobs' \
    || return 1
  start_stack
}
```

Append to `deploy/installer/lib/cmd_misc.sh`:
```bash

cmd_backup() {
  local dest="$ASSAYR_DIR/backups"
  while [ $# -gt 0 ]; do
    case "$1" in
      --to)
        need_value "$1" "${2:-}"
        dest="$2"
        shift 2
        ;;
      *) die "Unknown option for backup: $1" ;;
    esac
  done
  info "Backing up Assayr"
  do_backup "$dest" || die "The backup failed. Nothing was written."
  info "Backup written to $BACKUP_FILE"
  echo "It contains the database password and the HTTPS private key: keep it where only administrators can read it."
}

cmd_restore() {
  local file="" work backup_version installed created safety
  while [ $# -gt 0 ]; do
    case "$1" in
      -*) die "Unknown option for restore: $1" ;;
      *)
        file="$1"
        shift
        ;;
    esac
  done
  [ -n "$file" ] || die "Give the backup file: ./assayr restore FILE"
  [ -f "$file" ] || die "Backup file not found: $file"
  work="$(mktemp -d "$ASSAYR_DIR/backups/.restore.XXXXXX")"
  # shellcheck disable=SC2064 # expand $work now
  trap "rm -rf '$work'" EXIT
  read_backup "$file" "$work" || die "This backup can't be used: $RESTORE_PROBLEM"
  backup_version="$(env_get version "$RESTORE_FOLDER/manifest.txt")"
  created="$(env_get created "$RESTORE_FOLDER/manifest.txt")"
  installed="$(bundle_value "$ASSAYR_DIR" VERSION)"
  if version_gt "$backup_version" "$installed"; then
    die "This backup was made by Assayr $backup_version, which is newer than the installed $installed. Upgrade to $backup_version or later first."
  fi
  confirm_word restore "Restoring replaces all current Assayr data with the backup taken at $created (Assayr $backup_version)."
  info "Taking a safety backup of the current data"
  do_backup "$ASSAYR_DIR/backups" || die "The safety backup failed, so nothing was restored."
  safety="$BACKUP_FILE"
  info "Restoring the database and the evidence files"
  restore_data "$RESTORE_FOLDER" \
    || die "The restore failed. The data from just before it is in $safety. To put it back: $(sudo_prefix)$ASSAYR_DIR/assayr restore $safety"
  if audit_ok; then
    info "Restore complete. The audit trail is intact."
  else
    warn "Restore complete, but the audit trail check failed. See $ASSAYR_LOG"
  fi
}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && bash deploy/installer/tests/run.sh`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && git add -A && git commit -m "feat(installer): backup and restore with integrity checks and a safety backup"
```

---
### Task 7: Upgrade with automatic rollback

**Files:**
- Create: `deploy/installer/lib/cmd_upgrade.sh`
- Modify: `deploy/installer/assayr` (source the new library)
- Test: `deploy/installer/tests/upgrade.bats`

**Interfaces:**
- Consumes: Tasks 2–6 (`do_backup`/`BACKUP_FILE`, `read_backup`/`RESTORE_FOLDER`, `restore_data`, `copy_program_files`, `load_images`, `verify_bundle`, `env_set`, `env_merge_defaults`, `start_stack`, `api_ready`, `audit_ok`, `install_url`, checks).
- Produces: `cmd_upgrade [--dir DIR] [--non-interactive]`, `finish_interrupted_upgrade`, `rollback_upgrade BACKUP_FILE`. Install-folder contract: during an upgrade the old program files and `assayr.env` sit in `.previous/`; `VERSION` changes only after the new version is healthy; `.previous/` is removed on success and after a rollback.

- [ ] **Step 1: Write the failing tests**

`deploy/installer/tests/upgrade.bats`:
```bash
setup() {
  load helpers
  load_libs
  use_docker_stub
  OLD="$(make_bundle 1.2.3 "$BATS_TEST_TMPDIR/dist")"
  NEW="$(make_bundle 1.3.0 "$BATS_TEST_TMPDIR/dist")"
  DIR="$BATS_TEST_TMPDIR/install"
  install_fixture "$OLD" "$DIR" >/dev/null
  : >"$STUB_LOG"
  export STUB_IMAGES_PRESENT="$(stub_images 1.2.3) $(stub_images 1.3.0)"
}

@test "upgrade moves to the new version, keeps a backup and removes the old images" {
  run "$NEW/assayr" upgrade --dir "$DIR"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Assayr is now 1.3.0 and running at https://localhost:18443."* ]]
  [ "$(cat "$DIR/VERSION")" = 1.3.0 ]
  [ "$(env_get ASSAYR_VERSION "$DIR/assayr.env")" = 1.3.0 ]
  [ ! -e "$DIR/.previous" ]
  [ -n "$(find "$DIR/backups" -name 'assayr-1.2.3-*.tar.gz')" ]
  grep -q "image rm assayr-api:1.2.3 assayr-web:1.2.3" "$STUB_LOG"
  grep -q "exec -T api assayr audit-verify" "$STUB_LOG"
}

@test "upgrade keeps existing settings and adds new ones with their defaults" {
  env_set ASSAYR_ORG_NAME "Custom Org" "$DIR/assayr.env"
  grep -v '^ASSAYR_WAIT_TIMEOUT=' "$DIR/assayr.env" >"$DIR/assayr.env.tmp"
  mv "$DIR/assayr.env.tmp" "$DIR/assayr.env"
  run "$NEW/assayr" upgrade --dir "$DIR"
  [ "$status" -eq 0 ]
  [[ "$output" == *"New settings added with their defaults: ASSAYR_WAIT_TIMEOUT"* ]]
  [ "$(env_get ASSAYR_ORG_NAME "$DIR/assayr.env")" = "Custom Org" ]
  [ "$(env_get ASSAYR_WAIT_TIMEOUT "$DIR/assayr.env")" = 600 ]
}

@test "the same or an older version is refused" {
  run "$OLD/assayr" upgrade --dir "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Assayr 1.2.3 is installed and this bundle is 1.2.3. upgrade only moves to a newer version."* ]]
  "$NEW/assayr" upgrade --dir "$DIR" >/dev/null
  run "$OLD/assayr" upgrade --dir "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Assayr 1.3.0 is installed and this bundle is 1.2.3."* ]]
}

@test "a new version that doesn't start is rolled back with the data from before the upgrade" {
  STUB_FAIL_ON="--wait-timeout" STUB_FAIL_TIMES=1 run "$NEW/assayr" upgrade --dir "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Assayr 1.3.0 did not start correctly. Rolling back to 1.2.3."* ]]
  [[ "$output" == *"The upgrade to 1.3.0 failed and was rolled back to 1.2.3. Your data is as it was before the upgrade."* ]]
  [ "$(cat "$DIR/VERSION")" = 1.2.3 ]
  [ "$(env_get ASSAYR_VERSION "$DIR/assayr.env")" = 1.2.3 ]
  [ ! -e "$DIR/.previous" ]
  grep -q pg_restore "$STUB_LOG"
  run grep -c "image rm assayr-api:1.2.3" "$STUB_LOG"
  [ "$output" = 0 ]
}

@test "when the rollback fails too, the message says where the data is" {
  STUB_FAIL_ON="--wait-timeout" run "$NEW/assayr" upgrade --dir "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"the automatic rollback failed too. Your data is safe in $DIR/backups/assayr-1.2.3-"* ]]
}

@test "a failed backup stops the upgrade before anything changes" {
  STUB_FAIL_ON=pg_dump run "$NEW/assayr" upgrade --dir "$DIR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"The backup before the upgrade failed, so nothing was changed."* ]]
  [ "$(env_get ASSAYR_VERSION "$DIR/assayr.env")" = 1.2.3 ]
  run grep -c "load -i" "$STUB_LOG"
  [ "$output" = 0 ]
}

@test "an interrupted upgrade is put back before the next one" {
  mkdir "$DIR/.previous"
  cp "$DIR/assayr.env" "$DIR/.previous/assayr.env"
  env_set ASSAYR_ORG_NAME "Before the interruption" "$DIR/.previous/assayr.env"
  env_set ASSAYR_ORG_NAME "Half upgraded" "$DIR/assayr.env"
  run "$NEW/assayr" upgrade --dir "$DIR"
  [ "$status" -eq 0 ]
  [[ "$output" == *"An earlier upgrade did not finish."* ]]
  [ "$(env_get ASSAYR_ORG_NAME "$DIR/assayr.env")" = "Before the interruption" ]
  [ "$(cat "$DIR/VERSION")" = 1.3.0 ]
}

@test "upgrade without an installation says so" {
  run "$NEW/assayr" upgrade --dir "$BATS_TEST_TMPDIR/elsewhere"
  [ "$status" -eq 1 ]
  [[ "$output" == *"No Assayr installation found in $BATS_TEST_TMPDIR/elsewhere."* ]]
}
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && bash deploy/installer/tests/run.sh`
Expected: FAIL — every upgrade test fails with `cmd_upgrade: command not found`.

- [ ] **Step 3: Implement upgrade**

In `deploy/installer/assayr`, add before the `cmd_misc.sh` line:
```bash
# shellcheck source=lib/cmd_upgrade.sh
. "$SCRIPT_DIR/lib/cmd_upgrade.sh"
```

`deploy/installer/lib/cmd_upgrade.sh`:
```bash
# shellcheck shell=bash
# ./assayr upgrade — move an installation to this bundle's version, rolling back on failure.

cmd_upgrade() {
  local dir="" platform new old backup added problem
  while [ $# -gt 0 ]; do
    case "$1" in
      --dir)
        need_value "$1" "${2:-}"
        dir="$2"
        shift 2
        ;;
      --non-interactive)
        ASSAYR_INTERACTIVE=0
        shift
        ;;
      *) die "Unknown option for upgrade: $1. Run ./assayr help." ;;
    esac
  done
  platform="$(detect_platform)"
  [ "$platform" != unsupported ] || die "This system isn't supported. Use Linux, macOS, or Windows inside WSL."
  require_privileges "$platform" upgrade
  dir="${dir:-$(default_install_dir "$platform")}"
  [ -f "$dir/assayr.env" ] \
    || die "No Assayr installation found in $dir. Use ./assayr install, or add --dir if it is installed elsewhere."
  ASSAYR_DIR="$(cd "$dir" && pwd)"
  log_to "$ASSAYR_DIR/install.log"
  finish_interrupted_upgrade

  new="$(bundle_value "$BUNDLE_DIR" VERSION)"
  old="$(bundle_value "$ASSAYR_DIR" VERSION)"
  version_gt "$new" "$old" \
    || die "Assayr $old is installed and this bundle is $new. upgrade only moves to a newer version."

  info "Checking this machine"
  check_docker "$platform"
  check_arch "$(bundle_value "$BUNDLE_DIR" ARCH)"
  check_disk "$ASSAYR_DIR"
  info "Checking the bundle"
  problem="$(verify_bundle "$BUNDLE_DIR")" \
    || die "This bundle is damaged or was modified: $problem Download it again and compare its checksum with the one on the release page."

  info "Backing up Assayr $old before the upgrade"
  do_backup "$ASSAYR_DIR/backups" || die "The backup before the upgrade failed, so nothing was changed."
  backup="$BACKUP_FILE"
  info "Loading the $new images (this takes a few minutes)"
  load_images "$BUNDLE_DIR" || die "Loading the images failed; nothing else was changed."

  info "Installing the $new program files"
  mkdir "$ASSAYR_DIR/.previous"
  copy_program_files "$ASSAYR_DIR" "$ASSAYR_DIR/.previous"
  cp "$ASSAYR_DIR/assayr.env" "$ASSAYR_DIR/.previous/assayr.env"
  copy_program_files "$BUNDLE_DIR" "$ASSAYR_DIR"
  env_set ASSAYR_VERSION "$new" "$ASSAYR_DIR/assayr.env"
  added="$(env_merge_defaults "$ASSAYR_DIR/assayr.env.example" "$ASSAYR_DIR/assayr.env")"
  if [ -n "$added" ]; then info "New settings added with their defaults: $added"; fi

  info "Starting Assayr $new (the database is migrated on start)"
  if start_stack && api_ready && audit_ok; then
    cp "$BUNDLE_DIR/VERSION" "$ASSAYR_DIR/VERSION"
    rm -rf "$ASSAYR_DIR/.previous"
    run_logged docker image rm "assayr-api:$old" "assayr-web:$old" || true
    info "Assayr is now $new and running at $(install_url). The backup taken before the upgrade is $backup"
    return 0
  fi
  warn "Assayr $new did not start correctly. Rolling back to $old."
  if rollback_upgrade "$backup"; then
    die "The upgrade to $new failed and was rolled back to $old. Your data is as it was before the upgrade."
  fi
  die "The upgrade to $new failed and the automatic rollback failed too. Your data is safe in $backup. Restore it with the $old bundle's command: ./assayr restore $backup"
}

# finish_interrupted_upgrade — an upgrade stopped half-way leaves .previous/: put it back.
finish_interrupted_upgrade() {
  [ -d "$ASSAYR_DIR/.previous" ] || return 0
  warn "An earlier upgrade did not finish. Putting back the program files and settings of Assayr $(bundle_value "$ASSAYR_DIR" VERSION) first."
  copy_program_files "$ASSAYR_DIR/.previous" "$ASSAYR_DIR"
  cp "$ASSAYR_DIR/.previous/assayr.env" "$ASSAYR_DIR/assayr.env"
  rm -rf "$ASSAYR_DIR/.previous"
}

# rollback_upgrade BACKUP_FILE — previous program files and settings, then the data from BACKUP_FILE.
rollback_upgrade() {
  local backup="$1" work ok=1
  run_logged assayr_compose down --remove-orphans || true
  copy_program_files "$ASSAYR_DIR/.previous" "$ASSAYR_DIR"
  cp "$ASSAYR_DIR/.previous/assayr.env" "$ASSAYR_DIR/assayr.env"
  rm -rf "$ASSAYR_DIR/.previous"
  work="$(mktemp -d "$ASSAYR_DIR/backups/.rollback.XXXXXX")"
  if read_backup "$backup" "$work" && restore_data "$RESTORE_FOLDER" && api_ready; then ok=0; fi
  rm -rf "$work"
  return "$ok"
}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && bash deploy/installer/tests/run.sh`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && git add -A && git commit -m "feat(installer): upgrade with a backup first and automatic rollback"
```

---
### Task 8: Release workflow with the end-to-end test of real bundles

**Files:**
- Create: `.github/workflows/release.yml`, `deploy/installer/tests/e2e.sh`, `deploy/installer/tests/clamav-offline.sh`, `deploy/installer/MANUAL-CHECKS.md`

**Interfaces:**
- Consumes: everything above; `deploy/smoke-checks.sh` (Task 1); `scripts/build-bundle.sh` (Task 4).
- Produces: `e2e.sh BUNDLE.tar.gz NEXT_BUNDLE_DIR BROKEN_BUNDLE_DIR` (run as root on Linux with real Docker; exits 0 only if every step passes); `clamav-offline.sh` (release gate); workflow `release` — tag `v*` builds, tests and publishes; `workflow_dispatch` with input `version` builds and tests only; artifacts `bundle-amd64`, `bundle-arm64`; Release assets `assayr-<v>-linux-{amd64,arm64}-offline.tar.gz` and `SHA256SUMS.txt`.

- [ ] **Step 1: Write the end-to-end test and the ClamAV gate**

`deploy/installer/tests/e2e.sh`:
```bash
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
  if [ -f "$dir/assayr" ]; then "$dir/assayr" uninstall --delete-data --yes >/dev/null 2>&1 || true; fi
  rm -rf "$work"
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
```

`deploy/installer/tests/clamav-offline.sh`:
```bash
#!/usr/bin/env bash
# Release gate: the ClamAV image in the bundle must carry a virus database and start without
# internet access, because customer servers may have none.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
image="$(ASSAYR_VERSION=unused POSTGRES_PASSWORD=unused \
  docker compose -f "$HERE/../../compose.yaml" --profile av config --images | grep '^clamav/')"
docker image inspect "$image" >/dev/null 2>&1 || docker pull "$image" >/dev/null

docker run --rm --network none --entrypoint sh "$image" -c 'ls /var/lib/clamav/*.c?d' \
  || { echo "The image $image has no virus database" >&2; exit 1; }

name=assayr-clamav-offline-check
docker rm -f "$name" >/dev/null 2>&1 || true
trap 'docker rm -f "$name" >/dev/null 2>&1 || true' EXIT
docker run -d --name "$name" --network none "$image" >/dev/null
for _ in $(seq 1 60); do
  if docker logs "$name" 2>&1 | grep -q 'clamd started'; then
    echo "$image starts and loads its virus database without internet access"
    exit 0
  fi
  sleep 5
done
docker logs "$name" 2>&1 | tail -n 40
echo "$image did not start without internet access" >&2
exit 1
```

- [ ] **Step 2: Write the release workflow**

`.github/workflows/release.yml`:
```yaml
name: release

# A tag v<version> builds both bundles, tests them end to end and publishes a GitHub Release.
# Run by hand with a version to build and test without publishing.
on:
  push:
    tags: ["v*"]
  workflow_dispatch:
    inputs:
      version:
        description: "Version to build and test (not published), e.g. 0.2.0"
        required: true

permissions:
  contents: write

jobs:
  installer-checks:
    strategy:
      matrix:
        os: [ubuntu-24.04, macos-14]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - name: Install bats and shellcheck
        run: |
          if [ "$RUNNER_OS" = macOS ]; then
            brew install bats-core shellcheck
          else
            sudo apt-get update && sudo apt-get install -y bats shellcheck
          fi
      - name: Installer checks (on macOS with the system bash 3.2 first on PATH)
        env:
          ASSAYR_REQUIRE_SHELLCHECK: "1"
        run: |
          if [ "$RUNNER_OS" = macOS ]; then export PATH="/bin:/usr/bin:$PATH"; bash --version | head -n1; fi
          deploy/installer/tests/run.sh

  bundle:
    needs: installer-checks
    strategy:
      fail-fast: false
      matrix:
        include:
          - arch: amd64
            runner: ubuntu-24.04
          - arch: arm64
            runner: ubuntu-24.04-arm
    runs-on: ${{ matrix.runner }}
    env:
      ARCH: ${{ matrix.arch }}
      INPUT_VERSION: ${{ inputs.version }}
    steps:
      - uses: actions/checkout@v4
      - name: Work out the version
        run: |
          if [ "$GITHUB_REF_TYPE" = tag ]; then v="${GITHUB_REF_NAME#v}"; else v="$INPUT_VERSION"; fi
          [[ "$v" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Not a version: $v" >&2; exit 1; }
          if [ "$GITHUB_REF_TYPE" = tag ]; then
            grep -q "^version = \"$v\"" backend/pyproject.toml || { echo "backend/pyproject.toml is not $v" >&2; exit 1; }
            grep -q "\"version\": \"$v\"" frontend/package.json || { echo "frontend/package.json is not $v" >&2; exit 1; }
          fi
          echo "VERSION=$v" >>"$GITHUB_ENV"
      - name: Build the Assayr images
        run: |
          docker build -t "assayr-api:$VERSION" backend
          docker build -t "assayr-web:$VERSION" frontend
      - name: ClamAV works offline
        run: deploy/installer/tests/clamav-offline.sh
      - name: Build the bundle
        run: scripts/build-bundle.sh "$VERSION" "$ARCH" dist
      - name: Build the test bundles (a newer working version and a newer broken one)
        run: |
          docker tag "assayr-api:$VERSION" assayr-api:99.0.0
          docker tag "assayr-web:$VERSION" assayr-web:99.0.0
          printf 'FROM assayr-api:%s\nENTRYPOINT ["sh", "-c", "echo broken on purpose; exit 1"]\n' "$VERSION" \
            | docker build -t assayr-api:99.1.0 -
          docker tag "assayr-web:$VERSION" assayr-web:99.1.0
          scripts/build-bundle.sh 99.0.0 "$ARCH" dist/test --no-archive
          scripts/build-bundle.sh 99.1.0 "$ARCH" dist/test --no-archive
      - name: Remove the images so the installer must load them from the bundles
        run: |
          images="$(ASSAYR_VERSION="$VERSION" POSTGRES_PASSWORD=unused docker compose -f deploy/compose.yaml --profile av config --images)"
          # shellcheck disable=SC2086
          docker image rm $images assayr-api:99.0.0 assayr-web:99.0.0 assayr-api:99.1.0 assayr-web:99.1.0
      - name: End-to-end test
        run: sudo deploy/installer/tests/e2e.sh "dist/assayr-$VERSION-linux-$ARCH-offline.tar.gz" dist/test/assayr-99.0.0 dist/test/assayr-99.1.0
      - uses: actions/upload-artifact@v4
        with:
          name: bundle-${{ matrix.arch }}
          path: dist/assayr-*-offline.tar.gz
          retention-days: 7
          if-no-files-found: error

  publish:
    if: github.ref_type == 'tag'
    needs: bundle
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/download-artifact@v4
        with:
          pattern: bundle-*
          path: dist
          merge-multiple: true
      - name: Create the release
        env:
          GH_TOKEN: ${{ github.token }}
          TAG: ${{ github.ref_name }}
        run: |
          cd dist
          sha256sum assayr-*.tar.gz >SHA256SUMS.txt
          {
            echo "Offline installer bundles for Assayr ${TAG#v}."
            echo
            echo "- linux-amd64: Linux x86-64 servers, Windows (Docker Desktop with WSL2), Intel Macs"
            echo "- linux-arm64: Apple Silicon Macs, arm64 Linux servers"
            echo
            echo "Unpack the bundle and read README-INSTALL.md. Check the download against these SHA-256 checksums:"
            echo
            echo '```'
            cat SHA256SUMS.txt
            echo '```'
          } >notes.md
          gh release create "$TAG" assayr-*.tar.gz SHA256SUMS.txt --repo "$GITHUB_REPOSITORY" \
            --title "Assayr ${TAG#v}" --notes-file notes.md
```

- [ ] **Step 3: Write the manual checklist for Docker Desktop**

`deploy/installer/MANUAL-CHECKS.md`:
```markdown
# Manual checks on Docker Desktop (macOS and Windows)

GitHub's macOS and Windows runners can't run Docker, so these are checked by hand before the
first release to clients and whenever anything under `deploy/` changes. Use the bundles from the
release workflow's artifacts (run it by hand with a version) or from a release.

Record the date, the Assayr version, the machine and the result of each line in the release notes
or the pull request.

## macOS (Apple Silicon: arm64 bundle; Intel: amd64 bundle)

- [ ] Docker Desktop running with at least 6 GB of memory.
- [ ] `./assayr install` with the defaults (self-signed certificate) finishes and prints `https://localhost`.
- [ ] The browser opens `https://localhost` after accepting the warning; sign in works.
- [ ] Upload a small PDF to A.5.1; it leaves "verifying" within a minute.
- [ ] `./assayr backup`, then `./assayr restore <file>` (type `restore`) finish without errors.
- [ ] `./assayr status` shows every service running and "Application: ready".
- [ ] Turn Wi-Fi off, `./assayr restart`: Assayr comes back and evidence verification still works (ClamAV offline).
- [ ] `./assayr uninstall --delete-data` (type `delete`) removes `~/assayr` and the containers.

## Windows 11 (amd64 bundle, Docker Desktop with WSL2 and Ubuntu)

- [ ] WSL integration on for Ubuntu; in Ubuntu, `docker info` works.
- [ ] The bundle copied into the Ubuntu home folder (not `/mnt/c/...`), then `./assayr install` finishes.
- [ ] Windows browser opens `https://localhost`; sign in works.
- [ ] Evidence upload verified; backup and restore work; status is ready.
- [ ] Restart Windows, start Docker Desktop: Assayr comes back on its own (restart policy).
- [ ] `./assayr uninstall --delete-data` removes everything.
```

- [ ] **Step 4: Check the new scripts locally**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && bash -n deploy/installer/tests/e2e.sh && bash -n deploy/installer/tests/clamav-offline.sh && bash deploy/installer/tests/run.sh`
Expected: no syntax errors; all bats tests pass (shellcheck runs in CI).

- [ ] **Step 5: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && git add -A && git add --chmod=+x deploy/installer/tests/e2e.sh deploy/installer/tests/clamav-offline.sh && git commit -m "ci: release workflow that builds, tests end to end and publishes the offline bundles"
```

- [ ] **Step 6: Run the release workflow on the branch (build and test, no publishing)**

This pushes the feature branch to the public GitHub repository, which the user approved for this project on 2026-10-10; confirm with them first if that approval is not in the current session.

Run: `cd "E:/Work/GRC Tool/assayr" && git push -u origin HEAD && gh workflow run release.yml --ref "$(git branch --show-current)" -f version=0.2.0 && sleep 5 && gh run watch "$(gh run list --workflow release.yml --limit 1 --json databaseId -q '.[0].databaseId')" --exit-status`
Expected: `installer-checks` passes on Ubuntu and macOS; both `bundle` jobs pass, each log ending with `=== End-to-end test passed`; `publish` is skipped. If a job fails, read its log with `gh run view --log-failed`, fix with a failing test first where the failure is in installer code, and run the workflow again.

---
### Task 9: Version 0.2.0, documentation and the vault

**Files:**
- Modify: `backend/pyproject.toml`, `backend/uv.lock`, `frontend/package.json`, `frontend/package-lock.json`, `README.md`
- Modify (vault, outside the repo): `E:/Work/GRC Tool/Assayr-Vault/06-Architecture/Deployment On-Prem.md`, `E:/Work/GRC Tool/Assayr-Vault/06-Architecture/ADRs/ADR-001 On-prem first containerised deployment.md`, `E:/Work/GRC Tool/Assayr-Vault/03-Product/Non-Functional Requirements.md`

**Interfaces:**
- Consumes: Tasks 1–8.
- Produces: application version `0.2.0` in both packages (the release workflow refuses a tag that doesn't match); documentation of the install paths.

- [ ] **Step 1: Bump the version**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && sed -i 's/^version = "0.1.0"$/version = "0.2.0"/' backend/pyproject.toml && (cd backend && uv lock) && (cd frontend && npm version 0.2.0 --no-git-tag-version) && grep -n '^version' backend/pyproject.toml && grep -n '"version"' frontend/package.json`
Expected: `version = "0.2.0"` and `"version": "0.2.0",`; `uv lock` reports the project at 0.2.0.

- [ ] **Step 2: Update the README**

In `README.md`, replace the whole `## Run the full stack` section (up to, not including, `## Administration`) with:
````markdown
## Run the full stack

Requires Docker. Builds the images from source:

```bash
cd deploy
cp assayr.env.example assayr.env      # then set POSTGRES_PASSWORD
docker compose --env-file assayr.env -f compose.yaml -f compose.build.yaml up -d --build --wait
docker compose --env-file assayr.env -f compose.yaml -f compose.build.yaml exec api assayr create-admin --email you@example.com
# open http://localhost:8080
```

`deploy/smoke.sh` runs the same steps end to end and tears the stack down.

## Install for customers

Customers install from an offline bundle, not from source. Pushing a tag `v<version>` (matching
`backend/pyproject.toml` and `frontend/package.json`) runs `.github/workflows/release.yml`, which
builds `assayr-<version>-linux-amd64-offline.tar.gz` and `…-linux-arm64-…`, tests each end to end
(install, backup/restore, upgrade, rollback) and publishes them as a GitHub Release. Run the
workflow by hand with a version to build and test without publishing.

Inside a bundle, `./assayr install` sets everything up; `deploy/installer/README-INSTALL.md` is
the customer guide and `deploy/installer/MANUAL-CHECKS.md` the Docker Desktop checklist.
Installer unit tests: `deploy/installer/tests/run.sh`. To build a bundle locally (Docker needed):
build `assayr-api:<v>` and `assayr-web:<v>`, then `scripts/build-bundle.sh <v> amd64 dist`.
````

- [ ] **Step 3: Update the vault**

In `E:/Work/GRC Tool/Assayr-Vault/06-Architecture/Deployment On-Prem.md`, replace the `## Install (single node)` section's code block and the line after it with:
````markdown
```bash
# 1. Check the bundle's SHA-256 against the release page, then unpack it
tar -xzf assayr-0.2.0-linux-amd64-offline.tar.gz && cd assayr-0.2.0

# 2. Install: checks the machine and the bundle, asks for hostname, organisation, certificate
#    (or makes a self-signed one) and the first administrator, then starts everything
sudo ./assayr install

# Later, from /opt/assayr
sudo ./assayr status | backup | restore FILE | start | stop | restart | logs | create-admin | uninstall
# Upgrades run from the new bundle: backs up first, rolls back automatically on failure
sudo ./assayr upgrade
```
First login opens the [[FR-24 ISMS Setup Wizard]] (when it exists; until then the dashboard).

macOS (Docker Desktop or Colima) and Windows (Docker Desktop, run inside WSL) are supported for
evaluation only, installing to `~/assayr`. Bundles: `linux-amd64` (servers, Windows, Intel Macs)
and `linux-arm64` (Apple Silicon, arm64 servers), built and tested by the release workflow.
````

Append to `E:/Work/GRC Tool/Assayr-Vault/06-Architecture/ADRs/ADR-001 On-prem first containerised deployment.md`:
```markdown

**Update (Oct 2026, v0.2.0).** The single-node Compose install and the offline bundle are built (`./assayr` installer, GitHub Release per tag). Bundle integrity uses SHA256SUMS in the bundle plus checksums published on the release page; cryptographic signing (cosign) is deferred until offline key distribution is designed. Helm is not built yet.
```

Append to `E:/Work/GRC Tool/Assayr-Vault/03-Product/Non-Functional Requirements.md`:
```markdown

## Build status (v0.2.0, Oct 2026)
NFR-OPS-1: Docker Compose single-node install and the offline installer bundle are done (Linux production; macOS and Windows/WSL for evaluation), with upgrade + automatic rollback and backup/restore. Helm chart deferred; bundle signing deferred (SHA-256 checksums in v1).
```

- [ ] **Step 4: Verify everything**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest -W error -q) && (cd frontend && npm run typecheck && npx vitest run --testTimeout=10000 && npm run build) && bash deploy/installer/tests/run.sh`
Expected: every command succeeds (backend 298 passed, 1 skipped; frontend 54 passed; installer tests all pass).

- [ ] **Step 5: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && git add -A && git commit -m "chore: version 0.2.0 and installer documentation"
```

- [ ] **Step 6: Hand back for the release decision**

Pushing the tag publishes downloadable bundles on the public repository, so it is the user's call. Report to the user that, after merging to `main`, `git tag v0.2.0 && git push origin main v0.2.0` publishes the release, and that `MANUAL-CHECKS.md` should be run on a Mac and a Windows PC before the first client gets a bundle.

---

## Self-Review Notes

- **Spec coverage:** bundle per architecture with installer, compose, images, VERSION, SHA256SUMS, README (Tasks 1, 4); release workflow with lint on Linux and macOS, per-arch build and e2e, publish on tags only (Task 8); platform rules, bash 3.2, GNU/BSD tools (Tasks 2–3, global constraints, macOS CI with `/bin/bash`); install steps 1–9 incl. checks, integrity, questions/flags/env, files and modes, image loading, start, admin without exposing the password, licence slot, summary with fingerprint (Tasks 3–5); HTTPS with customer or self-signed certificate, redirect, `--http` with proxy question (Tasks 1, 3, 5); upgrade with checks, backup, images, `.previous`, settings merge, health + audit check, automatic rollback, old images removed (Task 7); backup contents, warning, restore with checksum check, newer-version refusal, typed confirmation, safety backup, audit check (Task 6); error-handling table rows (Tasks 3–7); manual checklist (Task 8); vault updates (Task 9). Refinements of the spec are listed in the header.
- **Type consistency checked:** `ASSAYR_DIR`, `BUNDLE_DIR`, `SCRIPT_DIR`, `BACKUP_FILE`, `RESTORE_FOLDER`, `RESTORE_PROBLEM`; `env_get KEY FILE` / `env_set KEY VALUE FILE`; `bundle_value DIR NAME`; `verify_bundle DIR` (prints problem); `copy_program_files SRC DEST`; `check_arch BUNDLE_ARCH`; `check_disk DIR`; `create_admin_account EMAIL PASSWORD`; test helpers `use_docker_stub`, `stub_images`, `make_bundle`, `install_fixture`; the stub's knobs match their uses (`STUB_FAIL_ON="--wait-timeout"` only matches `start_stack`, never the `up -d --wait db` calls).
- **Placeholder scan:** none; every code step carries the full code.
