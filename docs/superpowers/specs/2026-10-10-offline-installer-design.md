# Assayr offline installer — design

Date: 2026-10-10 · Status: draft for review · Vault: NFR-OPS-1, ADR-001, `06-Architecture/Deployment On-Prem.md`

## Goal

A customer's IT team installs, upgrades, backs up and restores Assayr on their own machine from one downloaded archive, with no internet access needed during install or at runtime. Users then work in a browser.

- **Production:** a Linux server (x86-64 or arm64) with Docker Engine and the Compose plugin.
- **Evaluation only:** macOS with Docker Desktop or Colima, and Windows with Docker Desktop through WSL2. The installer says so when it detects these platforms.
- **Success:** a customer with a fresh Linux VM and Docker goes from download to signing in over HTTPS in under 15 minutes with one command, and can upgrade to the next version without losing data.

Decided with the product owner: one bash installer (`./assayr`) for all three platforms, run inside WSL on Windows; bundles built and tested by GitHub Actions and published as GitHub Releases (the repository is public); v1 covers install, HTTPS, upgrade, and backup/restore. Trial licensing is a separate design that follows this one; the installer only provides the slot for a licence file.

## Out of scope (v1)

- Kubernetes / Helm, high-availability topologies, external Postgres or S3 storage.
- Installing Docker itself. The installer checks for it and links to the official install steps.
- Cryptographic signing of bundles (cosign). v1 checks integrity with SHA256SUMS; the checksum is also shown on the Release page so it can be confirmed through a second channel. Signing needs offline key distribution and is recorded as deferred in the vault.
- A PowerShell installer or a Windows setup.exe.
- Licence enforcement (next design).
- Automatic Docker Desktop testing on Mac or Windows; covered by a manual checklist.

## 1. The bundle and how it is built

Two bundles per version:

| File | For |
|---|---|
| `assayr-<version>-linux-amd64-offline.tar.gz` | Linux x86-64 servers, Windows (Docker Desktop via WSL2), Intel Macs |
| `assayr-<version>-linux-arm64-offline.tar.gz` | Apple Silicon Macs, arm64 Linux servers |

Each unpacks to `assayr-<version>/`:

```
assayr                    # the installer command (bash)
lib/                      # its helper scripts, sourced by assayr
compose.yaml              # production compose file: image tags only, no build sections
Caddyfile.https           # TLS on :8443, HTTP :8080 redirects to HTTPS
Caddyfile.http            # plain HTTP on :8080 (evaluation or behind the customer's TLS proxy)
assayr.env.example        # every setting, documented
images/                   # docker save archives: assayr-api, assayr-web, postgres:16-alpine, clamav
VERSION                   # e.g. 0.2.0
SHA256SUMS                # checksum of every other file in the bundle
README-INSTALL.md         # one-page guide: Linux, macOS, Windows/WSL sections
```

### Repository changes

- `deploy/compose.yaml` becomes the production definition: `image: assayr-api:${ASSAYR_VERSION}` and `assayr-web:${ASSAYR_VERSION}`, third-party images pinned by digest, no `build:` sections. It mounts `${ASSAYR_CERTS_DIR}` read-only into `web`, and the chosen Caddyfile.
- New `deploy/compose.build.yaml` adds the `build:` sections back for development. `deploy/smoke.sh` and the README use `-f compose.yaml -f compose.build.yaml`.
- The installer lives in `deploy/installer/` (`assayr`, `lib/*.sh`, Caddyfiles, `README-INSTALL.md`), its tests in `deploy/installer/tests/`.
- `scripts/build-bundle.sh <version> <arch>` assembles a bundle from locally built images. CI calls it; anyone with Docker can run it too.
- The version comes from the git tag `v<version>`; `backend/pyproject.toml` and `frontend/package.json` are bumped to match in the release commit.

### Release workflow (`.github/workflows/release.yml`)

Triggered by pushing a tag `v*` or by hand (`workflow_dispatch` with a version input, which builds and tests but does not publish).

1. **Lint job** (ubuntu and macos runners): `shellcheck` on every installer script, then the `bats` unit tests. The macOS run catches bash 3.2 and BSD-tool problems.
2. **Bundle jobs**, one per architecture, in parallel (`ubuntu-24.04` for amd64, `ubuntu-24.04-arm` for arm64): build the two Assayr images, pull the pinned third-party images, run `build-bundle.sh`, then run the end-to-end tests (section 3) against the bundle.
3. **Publish job**, only for tag pushes and only if every job passed: create the GitHub Release with both bundles and a `SHA256SUMS.txt` covering them, plus release notes listing the checksums.

Expected size: 600–900 MB per bundle, most of it ClamAV.

**ClamAV offline.** Whether the official `clamav/clamav` image carries a virus database usable without internet is verified in the first implementation task. If it does, malware scanning is on by default. If it does not, the bundle includes a database snapshot taken at build time, mounted into the ClamAV container, and the installer reports its date. Either way, `freshclam` failing on an air-gapped network must not stop the stack.

## 2. Installer commands and the install flow

```
./assayr install [--dir DIR] [--license FILE] [--http] [--https-port N] [--http-port N] [--non-interactive]
./assayr status
./assayr upgrade [--dir DIR]           # run from the new bundle's folder
./assayr backup [--to DIR]
./assayr restore FILE
./assayr start | stop | restart
./assayr logs [SERVICE]
./assayr create-admin
./assayr uninstall [--delete-data]
./assayr version
```

After installation the `assayr` command, `lib/`, compose files and `VERSION` live in the install folder, so day-to-day commands run from there. `upgrade` is the only command run from a new bundle.

### Platform rules

| Platform | Detected by | Install folder | Privileges | Default hostname |
|---|---|---|---|---|
| Linux | `uname -s` = Linux, not WSL | `/opt/assayr` | must run as root (sudo) | `hostname -f` |
| WSL | Linux with `microsoft` in `/proc/version` | `~/assayr` | normal user | `localhost` |
| macOS | `uname -s` = Darwin | `~/assayr` | normal user | `localhost` |

On WSL and macOS the installer prints: "This setup is for evaluation. Run Assayr in production on a Linux server."

The scripts are written for bash 3.2 (no associative arrays, no `${var,,}`, no `mapfile`) and work with both GNU and BSD tools (`sha256sum` or `shasum -a 256`; no `sed -i`; `mktemp` with a template).

### `install`, in order

Each step prints one line saying what it is doing, and on failure stops with a plain message saying what went wrong and what to do next.

1. **Checks:** platform; Docker running and Compose v2 present; the machine's architecture matches the bundle ("This bundle is for arm64 but this machine is x86-64 — download the amd64 bundle"); at least 10 GB free in the install folder's filesystem; the HTTPS port (default 443) and HTTP port (default 80) free; `openssl` available (needed for the self-signed certificate); not already installed in the target folder ("Assayr is already installed in /opt/assayr — use `./assayr upgrade`").
2. **Integrity:** every file listed in `SHA256SUMS` matches; otherwise "This bundle is damaged or was modified. Download it again and compare the checksum with the Release page."
3. **Questions** (each also accepted as a flag or an environment variable for `--non-interactive`): hostname; organisation name; HTTPS certificate and key files, or Enter for a self-signed certificate; first administrator's email and password (typed twice, hidden, at least 12 characters, checked before anything is written).
4. **Files** in the install folder: `assayr.env` with `ASSAYR_VERSION`, a random 32-character database password (letters and digits), `ASSAYR_SECURE_COOKIES=true`, the ports, hostname and organisation name, file mode 600; `certs/tls.crt` and `certs/tls.key` (key mode 600); the program files copied from the bundle; `backups/` (mode 700).
5. **Images:** `docker load` for each archive in `images/`, skipping an image whose exact tag already exists.
6. **Start:** `docker compose up -d --wait`. The API migrates and seeds the database when it starts (existing entrypoint).
7. **First administrator:** `docker compose exec -e ASSAYR_ADMIN_PASSWORD api assayr create-admin --email …`. The installer exports the password only in its own environment for that one call (`-e NAME` without a value forwards it), so it never appears on a command line, in the shell history or in the installer log.
8. **Licence:** with `--license FILE`, the file is copied to `license/assayr.lic` (mode 600) and mounted read-only into the API at `/etc/assayr/license/assayr.lic`, with `ASSAYR_LICENSE_FILE` set. The application ignores it until the licensing work lands.
9. **Summary:** the address (`https://<hostname>`), the admin email, the certificate's SHA-256 fingerprint when self-signed (so users can confirm the browser warning), and next steps: schedule `./assayr backup`, replace the self-signed certificate.

Rules: secrets are never printed or written to `install.log` (the installer logs every step to `<dir>/install.log`, mode 600); a failed install leaves a message naming what was created and how to retry (`./assayr uninstall --delete-data` then install again); nothing is ever deleted without the explicit flag and a typed confirmation.

## 3. HTTPS, upgrade, backup/restore, and testing

### HTTPS

- Default: `Caddyfile.https`. Caddy listens on 8443 inside the container with `tls /certs/tls.crt /certs/tls.key`, published on the HTTPS port (443); port 8080 is published on the HTTP port (80) and redirects to HTTPS. The existing security headers move into a shared snippet used by both Caddyfiles.
- Self-signed certificate: generated by `openssl` for 825 days, with subject alternative names for the hostname, `localhost` and `127.0.0.1`.
- `--http`: `Caddyfile.http`, plain HTTP on 8080 only, for evaluation or behind the customer's own TLS proxy. The installer asks whether a TLS proxy is in front; if not, it sets `ASSAYR_SECURE_COOKIES=false` and warns that this is for evaluation only.
- Replacing the certificate later: put the new files in `certs/` and run `./assayr restart`.

### Upgrade

Run from the new bundle: `sudo ./assayr upgrade` (finds `/opt/assayr`, or `--dir`).

1. Checks as for install, plus: an installation exists; the new version is newer than the installed one (downgrades are refused).
2. Integrity of the new bundle.
3. Full backup (same as `./assayr backup`) into `backups/`.
4. Load the new images.
5. Keep the current program files in `.previous/`, copy in the new ones, set `ASSAYR_VERSION`, and add any settings that are new in `assayr.env.example` with their defaults (existing values are never changed).
6. `docker compose up -d --wait`; the API runs the database migrations on start. Then check `/api/v1/readyz` and run `assayr audit-verify`.
7. **On failure, roll back automatically:** stop the stack, restore the program files from `.previous/`, restore the database and evidence from the backup taken in step 3, start the previous version, and report "Upgrade to 0.3.0 failed and was rolled back to 0.2.0. Your data is as it was before the upgrade. Details: install.log". Old images stay until the next successful upgrade, then are removed.

### Backup and restore

`./assayr backup` writes `backups/assayr-<version>-<UTC timestamp>.tar.gz` (mode 600) containing:

- `db.dump` — `pg_dump -Fc` from the database container;
- `blobs.tar` — the evidence files from the blob volume;
- `assayr.env`, `certs/` and `license/` — so a restore on a new machine works;
- `manifest.json` — Assayr version, time, and checksums of the parts.

The printed message warns that the backup contains the database password and the private key and must be stored securely. The stack keeps running during a backup; evidence files are written once and never changed, and `pg_dump` is consistent.

`./assayr restore FILE`:

1. Verifies the manifest checksums; refuses a backup from a newer Assayr version than the one installed.
2. Asks the user to type `restore` (or `--yes` for scripts), since current data is replaced.
3. Takes a safety backup of the current data first.
4. Stops the application services, recreates the database and runs `pg_restore`, replaces the evidence volume's contents, and starts the stack. An older backup is migrated forward by the API on start.
5. Runs `audit-verify` to confirm the audit trail's hash chain is intact and reports the result.

### Testing

- **Unit (`bats`, on Linux and macOS runners):** platform and architecture detection, version comparison, checksum verification (pass and tampered), env-file writing (new file, upgrade merge that keeps existing values), password validation, argument parsing. Docker is replaced by a stub on `PATH` that records its calls.
- **`shellcheck`** with no warnings on every script.
- **End-to-end, per architecture, in the release workflow** against the real bundle on a fresh runner:
  1. `install --non-interactive` with a self-signed certificate;
  2. smoke checks over HTTPS: sign in, risk methodology served, 93 controls in the SoA, an evidence upload verified by the worker (from today's `smoke.sh`);
  3. create a risk, `backup`, delete the risk, `restore`, and confirm the risk is back and `audit-verify` passes;
  4. upgrade to a second bundle built from the same images retagged as a higher version, and confirm data survived;
  5. upgrade to a deliberately broken bundle (an API image that exits on start) and confirm the automatic rollback leaves the previous version running with its data;
  6. `install` again is refused; a tampered bundle is refused.
- **Manual checklist** (`deploy/installer/MANUAL-CHECKS.md`) for macOS with Docker Desktop and Windows 11 with Docker Desktop + WSL2: install, sign in, upload evidence, backup, restore, uninstall. Run before the first client release and whenever the installer changes.

## Error handling summary

| Situation | Behaviour |
|---|---|
| Docker missing or stopped | Stop; say how to install or start it for the detected platform |
| Wrong architecture bundle | Stop; name the right bundle |
| Port in use | Stop; name the port and suggest `--https-port` / `--http-port` |
| Damaged bundle | Stop before changing anything |
| Install already present | Refuse; point to `upgrade` |
| Upgrade fails health checks | Automatic rollback to the previous version and data |
| Restore of a newer backup | Refuse |
| Any failure | Message plus the path to `install.log`; no secrets in either |

## Vault updates (with the implementation)

- `06-Architecture/Deployment On-Prem.md`: replace the illustrative install block with the real commands; note Mac and Windows as evaluation-only.
- `ADR-001`: note that bundle signing is deferred and integrity uses SHA256SUMS in v1.
- `NFR-OPS-1`: build status — Compose single-node and offline bundle done; Helm deferred.
