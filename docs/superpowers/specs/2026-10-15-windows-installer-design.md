# Windows installer (v0.3.0) — design

Date: 2026-10-15
Status: approved in conversation, awaiting spec review

## Goal

A client downloads one file, `Assayr-Setup-<version>.exe`, from the GitHub Release page, runs it on a
Windows Server VM and has a working, production Assayr installation. No Docker, no WSL, no internet
access during installation, and nothing leaves the client's network.

## Decisions

| Question | Decision | Why |
|---|---|---|
| Who runs it | Production on Windows Server | Clients whose IT runs only Windows |
| Where | Windows Server VMs on the client's own VMware / Hyper-V | Usually no nested virtualization, so WSL2 and Docker are out |
| Approach | Native Windows services, bundled runtimes | Works on any VM; behaves like normal Windows software |
| Installer tool | Inno Setup | Free, single .exe, wizard pages, silent mode, upgrade detection |
| Service wrapper | WinSW (MIT) | Runs any executable as a service, log rotation, dependencies |
| Code signing | Unsigned for v0.3.0; pipeline signs automatically when a certificate is added to GitHub secrets | No certificate yet; SmartScreen "Run anyway" is acceptable for now |
| Version | 0.3.0, distribution release only, no new GRC features | Keep the release focused |

Out of scope: ARM64 Windows, Windows on 32-bit, a domain-joined service account wizard, clustering,
online ClamAV updates by default, the local LLM (it is not in the product yet).

## Supported platforms

Windows Server 2019, 2022, 2025 (x64). Windows 10/11 x64 work too (for evaluation). The installer
blocks older or 32-bit systems.

## Layout

```
C:\Program Files\Assayr\            program, replaced on upgrade
  python\        embedded CPython 3.12 with the backend and its dependencies installed
  pgsql\         PostgreSQL 16 binaries
  caddy\         caddy.exe
  clamav\        clamd.exe, freshclam.exe, bundled signatures (copied to data on first install)
  web\           built frontend
  services\      WinSW executables and XML definitions
  assayr-admin.cmd
  VERSION

<data dir> (default C:\ProgramData\Assayr, chosen at install, kept on upgrade and uninstall)
  db\            PostgreSQL cluster
  blobs\         evidence files
  certs\         tls.crt, tls.key
  clamav\        signature database
  backups\
  logs\
  Caddyfile      generated
  assayr.env     settings, including the generated database password
  install.log    every installer/admin action; never passwords
```

The data directory ACL grants full control to Administrators, SYSTEM and the service accounts only.
The program directory's path is recorded in the registry (`HKLM\SOFTWARE\Assayr`: `InstallDir`,
`DataDir`, `Version`).

## Services

| Service name | Display name | Runs | Listens | Depends on |
|---|---|---|---|---|
| `AssayrDb` | Assayr Database | `postgres.exe -D <data>\db` | 127.0.0.1:5432 (port configurable if taken) | – |
| `AssayrClamAV` | Assayr ClamAV | `clamd.exe` | 127.0.0.1:3310 | – (omitted when scanning is off) |
| `AssayrApi` | Assayr API | `python -m uvicorn assayr.main:create_app --factory` | 127.0.0.1:8000 | AssayrDb |
| `AssayrWorker` | Assayr Worker | `python -m assayr worker` | – | AssayrDb, AssayrClamAV |
| `AssayrWeb` | Assayr Web | `caddy run --config <data>\Caddyfile` | 0.0.0.0:443 and :80 (configurable) | AssayrApi |

All start automatically (delayed start for API/Worker/Web). Each runs as a virtual service account
(`NT SERVICE\<name>`), not LocalSystem. Restart-on-failure: 3 attempts, 10 s apart. The firewall
gets inbound rules for the HTTPS and HTTP ports only.

The Caddyfile mirrors the Linux web image: serve `web\`, reverse-proxy `/api/*` to 127.0.0.1:8000,
redirect HTTP to HTTPS with 301, the same security headers, TLS from `certs\`. With `--http` mode
(plain HTTP behind the customer's proxy) it serves HTTP on the HTTP port only.

## Setup wizard (first install)

1. Welcome and licence.
2. System check. Blocks: not Administrator, not x64, Windows older than Server 2019 / Windows 10,
   chosen ports in use (names the owning process, lets the user pick other ports). Warns: < 8 GB RAM,
   < 100 GB free on the data drive, < 4 cores.
3. Server: hostname (default: machine FQDN), organisation name, HTTPS/HTTP ports.
4. Certificate: PEM `.crt` + `.key`, or `.pfx` + password (converted to PEM), or generate
   self-signed (by the Python CLI using `cryptography`; valid 2 years, SAN = hostname and localhost).
5. First administrator: email, password twice, minimum 12 characters.
6. Options: malware scanning on/off; data directory.
7. Progress: copy files → write `assayr.env` with random DB password → `initdb` (scram-sha-256,
   UTF8) → register services → start DB → `assayr migrate` → `assayr seed` → `assayr create-admin`
   (password on stdin) → firewall rules → start remaining services → wait for
   `https://localhost:<port>/api/health` (up to 3 minutes).
8. Finish: shows the address; "Open Assayr" checkbox. Start Menu: Open Assayr, Assayr Admin
   (opens a console in the install dir), Back up now.

A failure at any step shows the failing step and points to `install.log`; already-registered services
and the half-made data directory are removed when the data directory was new.

Silent install: `Assayr-Setup-<v>.exe /VERYSILENT /SUPPRESSMSGBOXES /CONFIG=answers.ini`. The ini holds
every wizard answer except passwords; `ASSAYR_ADMIN_PASSWORD` (and `ASSAYR_PFX_PASSWORD`) come from
the environment. Exit code 0 on success, non-zero with the reason in `install.log`.

## Admin commands

`assayr-admin.cmd` calls the bundled Python CLI with the install's settings:
`status`, `start`, `stop`, `restart`, `logs [api|worker|web|db]`, `backup`, `restore FILE`,
`create-admin`, `update-signatures FILE|DIR`. Start/stop act on the Windows services in dependency
order.

## Backup and restore

Format is identical to the Linux bundle's: `assayr-<version>-<UTCstamp>.tar.gz` containing one folder
with `manifest.txt` (`version=`, `created=`), `db.dump` (`pg_dump -Fc`), `blobs.tar`, `assayr.env`,
`certs/`, `license/` and `SHA256SUMS`. The Windows implementation is Python (`tarfile`, `hashlib`,
bundled `pg_dump`/`pg_restore`); the Linux Bash implementation is unchanged. The archive appears in
`backups\` only once complete (write to a temp name, then rename).

Restore: verify checksums and required parts, refuse a backup from a newer version, take a safety
backup, stop API/Worker, drop and recreate the database, `pg_restore`, replace blobs, restore certs,
run migrations, start services. Settings that describe the machine (paths, ports, DB password) are
kept from the target install, so a Linux backup restores on Windows and the other way round.

Nightly backup: a Scheduled Task created at install (02:00 daily, SYSTEM), keeping the newest 14
scheduled backups. Manual and pre-upgrade backups are never pruned.

## Upgrade and rollback

Running a newer Setup on a machine with Assayr installed shows "Upgrade <old> → <new>" and skips the
settings pages.

1. Back up (abort the upgrade if the backup fails).
2. Stop services; move `C:\Program Files\Assayr` to `Assayr.previous`.
3. Install new program files; update service definitions; run `assayr migrate`.
4. Start services; wait for health.
5. On failure: stop services, put `Assayr.previous` back, restore the pre-upgrade backup's database,
   start the old version, report "Upgrade failed; <old> has been restored" with the log path.
6. On success: delete `Assayr.previous`.

Running an older Setup over a newer install is blocked. Same version: offers "Repair" (reinstall
program files, keep data).

## Uninstall

Removes services, scheduled task, firewall rules, shortcuts, program files and registry key. The data
directory stays unless "Also delete all data" is ticked (unticked by default; a confirmation dialog
recommends a backup first).

## Backend changes (shared code)

- `assayr` CLI gains `backup`, `restore`, `update-signatures`, `gen-cert` and `healthcheck` commands
  used by the Windows admin tool (Linux keeps its Bash commands).
- Paths go through `pathlib`; no POSIX-only calls. Worker stops cleanly on the CTRL_BREAK / stop signal
  WinSW sends.
- `pg8000`, `pypdfium2`, `python-docx`, `openpyxl`, `argon2-cffi` all ship Windows wheels; add
  `cryptography` for certificate handling.
- Backend tests run on Windows in CI as well as Linux.

## Build (GitHub Actions)

New job `windows` in `release.yml` on `windows-2022`:

1. Download pinned component archives listed in `deploy/windows/components.json` (URL, version,
   SHA-256): Python embeddable, PostgreSQL Windows binaries, Caddy, ClamAV win64, WinSW. Fail on any
   hash mismatch.
2. Install the backend wheel and dependencies into the embedded Python (`pip install --target`).
3. Build the frontend (`npm ci && npm run build`).
4. Fetch current ClamAV signatures with `freshclam` into the bundle.
5. Compile with Inno Setup (`ISCC.exe deploy/windows/assayr.iss`).
6. If `WINDOWS_SIGNING_CERT` secret is set, sign the exe (and the uninstaller) with `signtool`.
7. Run the end-to-end test (below); publish only if it passes. The exe joins the Linux bundles on the
   Release and in `SHA256SUMS.txt`.

## Testing

Automatic on every release build (`windows-2022` runner, a clean Windows Server VM):

1. Silent install → health check green.
2. Log in through the API; upload a document; it is verified.
3. Upload the EICAR test file; it is rejected as malware.
4. Backup; change data; restore; the change is gone.
5. Upgrade from the previous build (built in the same job with a lower version); data survives.
6. Upgrade with a deliberately broken build → automatic rollback; old version runs with the data.
7. Uninstall → services gone, data directory kept; reinstall over the kept data works.

Plus: backend unit tests on Windows; Pester tests for the PowerShell helper scripts; a manual checklist
(`deploy/windows/MANUAL-CHECKS.md`) for Windows Server 2019, the wizard UI, and SmartScreen behaviour.

## Documentation

`deploy/windows/README-INSTALL-WINDOWS.md` (client guide), linked from the Release notes and the
repo README.

## Risks

| Risk | Mitigation |
|---|---|
| ClamAV on Windows needs ~2 GB RAM | Option to turn scanning off; warning in the system check |
| SmartScreen warning on an unsigned exe | Documented; signing wired in, enabled by adding the secret |
| Port 443 used by IIS on the server | System check names the process and offers other ports |
| Antivirus on the server quarantines bundled binaries | Document exclusions for the program and data directories |
| Installer size (~500 MB) | Within GitHub's 2 GB asset limit |
