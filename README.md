# Assayr

**On-premise GRC for ISO/IEC 27001: every control, piece of evidence and risk stays on your own servers.**

Assayr is a governance, risk and compliance platform that organisations install inside their own network.
It holds every ISO/IEC 27001:2022 requirement and all 93 Annex A controls, checks each piece of uploaded
evidence automatically, keeps compliance status current as evidence arrives or expires, and runs the full
risk assessment and treatment cycle through to a Statement of Applicability. Nothing is sent to the cloud:
no telemetry, no outbound calls, and it installs on servers with no internet access.

## What it does

| Area | Capability |
|---|---|
| **Controls** | The ISO/IEC 27001:2022 catalogue (clauses 4–10 and Annex A) with evidence slots that say exactly what each control needs |
| **Qatar NIA v2.1** | All 355 NIA controls in 26 domains, mapped to ISO 27001 so evidence is shared; NIA-only controls tracked on their own; applicability with reasons. Assayr ships control IDs and its own summaries; the official NCSA text is imported from your organisation's copy and stays in your installation |
| **Policies, procedures and guidelines** | A document register with owners, approval, versions, review dates and files, linked to controls; every control page lists its policies, procedures and guidelines |
| **Evidence** | Upload, versioning and expiry; every file is malware-scanned and verified automatically (dates, approvals, versions, freshness) with the reasons shown, and uncertain files go to a reviewer queue |
| **Compliance status** | Control status derived from evidence, never ticked by hand: compliant, in review, in progress, at risk, not started, non-compliant, with readiness scores and history |
| **Dashboard** | ISO 27001 and NIA compliance with partial progress, evidence and risk monitoring (open / in progress / closed), owner gaps, readiness trend and status charts |
| **Risk** | Risk register with a guided assessment wizard, risk owners, treatment plans, residual-risk acceptance, snapshots and comparison, register export |
| **Assets** | Asset inventory with owners and classification, linked to risks |
| **Statement of Applicability** | Generated from controls and risks, with traceability checks and executive approval |
| **Audit trail** | Tamper-evident (hash-chained) record of every change |

## Download and install

Download from the [latest release](https://github.com/Hamzaviour/Assayr/releases/latest) and check the file
against `SHA256SUMS.txt` on the same page.

| Your server | Download | Guide |
|---|---|---|
| **Windows Server 2019 / 2022 / 2025** | `Assayr-Setup-<version>.exe`: run it and follow the wizard (native Windows services, no Docker) | [Windows install guide](deploy/windows/README-INSTALL-WINDOWS.md) |
| **Linux** (x86-64) | `assayr-<version>-linux-amd64-offline.tar.gz`: unpack, then `sudo ./assayr install` | [Linux install guide](deploy/installer/README-INSTALL.md) |
| **Linux** (arm64) | `assayr-<version>-linux-arm64-offline.tar.gz` | [Linux install guide](deploy/installer/README-INSTALL.md) |

**You need:** 4 CPU cores, 8 GB of memory (16 GB recommended), 100 GB of free disk and ports 443/80. The
installers contain everything else (database, web server, malware scanner), set up HTTPS (your certificate
or a self-signed one), create the first administrator, and schedule nightly backups. Upgrading means running
the newer installer: it backs up first and puts the previous version back automatically if the new one does
not start. Backups are the same format on Windows and Linux, so you can move between them.

## Security and privacy

- Runs entirely on your infrastructure; works air-gapped. No telemetry and no outbound connections.
- Only the HTTPS and HTTP ports are reachable from the network; the database, API and scanner listen on
  localhost only.
- Every upload is scanned with ClamAV; uploaded files are stored content-addressed and checksummed.
- Passwords are hashed with Argon2id; sessions expire on idle and absolute timeouts; roles limit who can do what.
- Backups contain the database password and the HTTPS key, so keep them where only administrators can read them.

## Roadmap

- **Next:** internal audit reports (NIA internal audit workbook layout).
- **Then:** training and awareness (videos and mandatory assessments).

---

## For developers

| Path | What |
|---|---|
| `backend/` | FastAPI service (`assayr` Python package), Alembic migrations, `assayr` CLI |
| `frontend/` | React + Vite single-page app, served by Caddy in production |
| `deploy/` | Docker Compose stack, Linux offline installer (`deploy/installer/`), Windows installer (`deploy/windows/`) |
| `docs/superpowers/` | Design specs and implementation plans |

### Develop locally

On the original development machine, source the cache redirection script first (its C: drive is full):
`source scripts/dev-env.sh` (Git Bash) or `. .\scripts\dev-env.ps1` (PowerShell).

Backend:

```bash
cd backend
uv sync --python 3.12
cp .env.example .env
uv run assayr migrate && uv run assayr seed
uv run assayr create-admin --email you@example.com
uv run uvicorn assayr.main:create_app --factory --reload --port 8000
uv run assayr worker               # in a second terminal: verifies uploaded evidence
uv run pytest
```

Frontend (proxies `/api` to port 8000):

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
npm test
```

### Run the full stack with Docker

```bash
cd deploy
cp assayr.env.example assayr.env      # then set POSTGRES_PASSWORD
docker compose --env-file assayr.env -f compose.yaml -f compose.build.yaml up -d --build --wait
docker compose --env-file assayr.env -f compose.yaml -f compose.build.yaml exec api assayr create-admin --email you@example.com
# open http://localhost:8080
```

`deploy/smoke.sh` runs the same steps end to end and tears the stack down.

### Releases

Pushing a tag `v<version>` (matching `backend/pyproject.toml` and `frontend/package.json`) runs
`.github/workflows/release.yml`. It builds the two Linux bundles and the Windows installer, tests each end to
end on a clean machine (install, evidence upload, backup/restore, upgrade, rollback after a failed upgrade,
uninstall), and only then publishes the GitHub Release. Branch pushes that change `deploy/`, and manual runs
with a version, build and test without publishing.

- Linux bundle: build `assayr-api:<v>` and `assayr-web:<v>`, then `scripts/build-bundle.sh <v> amd64 dist`.
  Installer unit tests: `deploy/installer/tests/run.sh`.
- Windows installer: `deploy/windows/build.ps1 -Version <v> -Out <dir>` stages pinned, hash-checked runtimes;
  then Inno Setup 7: `ISCC /DVersion=<v> /DStage=<dir>\stage /DOutDir=<out> deploy\windows\assayr.iss`.
  Manual pre-release checks: `deploy/windows/MANUAL-CHECKS.md`.

### Administration commands

| Command | Purpose |
|---|---|
| `assayr migrate` | Apply database migrations |
| `assayr seed` | Load the ISO/IEC 27001:2022 catalogue, the risk methodology and the threat, vulnerability and template libraries (safe to repeat) |
| `assayr create-admin --email …` | Create an administrator (password from prompt or `ASSAYR_ADMIN_PASSWORD`) |
| `assayr audit-verify` | Check the audit trail's hash chain (exit code 2 if broken) |
| `assayr worker [--once]` | Run background jobs (evidence verification, scheduled status checks) |
| `assayr win …` | Windows installation management, used by the installer and the Assayr Admin console |

Product specs, brand and design live in the Obsidian vault at `../Assayr-Vault` (start at `00-Home/Home.md`).
