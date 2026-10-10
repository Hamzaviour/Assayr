# Assayr

On-premise GRC for ISO/IEC 27001: keep every control, piece of evidence and risk on your own servers.
Product specs, brand and design live in the Obsidian vault at `../Assayr-Vault` (start at `00-Home/Home.md`).

What it covers today: the ISO/IEC 27001:2022 catalogue with evidence slots, evidence upload with automatic verification and review,
derived control status and readiness, a risk register with a guided assessment wizard, treatment and residual-risk acceptance,
an asset inventory, and a Statement of Applicability with traceability checks and executive approval.

## Layout

| Path | What |
|---|---|
| `backend/` | FastAPI service (`assayr` Python package), Alembic migrations, `assayr` CLI |
| `frontend/` | React + Vite single-page app, served by Caddy in production |
| `deploy/` | Docker Compose stack and smoke test |
| `docs/superpowers/plans/` | Implementation plans |

## Develop locally

Every command assumes the cache redirection script has been sourced (the dev machine's C: drive is full):

```bash
source scripts/dev-env.sh            # Git Bash
# . .\scripts\dev-env.ps1            # PowerShell
```

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

## Run the full stack

Requires Docker.

```bash
cd deploy
cp assayr.env.example assayr.env      # then set POSTGRES_PASSWORD
docker compose --env-file assayr.env up -d --build --wait
docker compose --env-file assayr.env exec api assayr create-admin --email you@example.com
# open http://localhost:8080
```

`deploy/smoke.sh` runs the same steps end to end and tears the stack down.

The stack serves plain HTTP on port 8080 for evaluation. Put it behind TLS and set
`ASSAYR_SECURE_COOKIES=true` before real use.

## Administration

| Command | Purpose |
|---|---|
| `assayr migrate` | Apply database migrations |
| `assayr seed` | Load the ISO/IEC 27001:2022 catalogue, the risk methodology and the threat, vulnerability and template libraries (safe to repeat) |
| `assayr create-admin --email …` | Create an administrator (password from prompt or `ASSAYR_ADMIN_PASSWORD`) |
| `assayr audit-verify` | Check the audit trail's hash chain (exit code 2 if broken) |
| `assayr worker [--once]` | Run background jobs (evidence verification, scheduled status checks) |
