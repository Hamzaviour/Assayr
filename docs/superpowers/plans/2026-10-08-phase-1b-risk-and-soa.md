# Assayr Phase 1b — Risk Management and Statement of Applicability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the ISO 27001 risk cycle (clauses 6.1.2, 6.1.3, 8.2, 8.3) inside Assayr: identify risks from seeded libraries or templates, rate them in a guided wizard with a live heatmap, link mitigating controls (whose evidence-backed status suggests the current risk), plan treatment, accept residual risk at the right authority level, freeze snapshots — and generate a Statement of Applicability whose justifications trace back to those risks, with traceability checks, versioned executive approval and spreadsheet export.

**Architecture:** New backend packages `assets`, `risk`, `tasks` and `soa`, following the Phase 0/1a patterns (SQLAlchemy models + one Alembic migration, pure-function services with unit tests, FastAPI routers with scope-aware permissions and the hash-chained audit log). The risk methodology is a versioned JSON definition; every level, band and authority decision is a pure function of it. Risk status is **derived** from facts (assessments, treatment, actions, acceptance, dates) and cached on the row, like control status ([[ADR-005 Derived control status]]). SoA applicability lives on the control; risk-based justifications are computed live from risk links; submitted SoA versions are frozen JSON. The frontend adds Risks (table / board / heatmap), a six-step assessment wizard, risk detail, snapshots, assets and SoA pages.

**Tech Stack:** existing stack only (FastAPI, SQLAlchemy 2, Alembic, pg8000, openpyxl for XLSX, React 19, TanStack Router/Query, Tailwind v4). No new dependencies.

**Spec:** Obsidian vault `E:\Work\GRC Tool\Assayr-Vault`: `03-Product/Requirements/FR-06 Risk Management.md`, `FR-07 Statement of Applicability.md`, `FR-08 Asset Inventory.md`, `03-Product/Risk Methodology.md`, `03-Product/RBAC Matrix.md`, `05-Workflows/WF-07 Risk Assessment.md`, `WF-08 Risk Treatment.md`, `WF-09 SoA Generation.md`, `05-Workflows/State Machines.md` (Risk, Task), `06-Architecture/Data Model.md` (Risk ERD), `07-Design/Screens/Screen - Risk Register.md`, `Screen - Risk Assessment Wizard.md`, `Screen - SoA.md`, `07-Design/Design System.md` (heat tokens, Heatmap5x5).

**Phase 1 split (re-cut after 1a):**
- **1a (done):** evidence upload, verification, review, scoring, attestation, readiness.
- **1b (this plan):** risk methodology, threat/vulnerability/template libraries, minimal asset inventory, risk register, assessment wizard, treatment with actions, residual-risk acceptance, snapshots, risk register export, SoA with traceability checks, versions, approval and export.
- **1c:** policy and document management (FR-09), tasks and remediation UI (FR-10, building on this plan's `task` table), mandatory clause documents as evidence slots.
- **1d:** local AI (`V-RELEVANCE`), OCR, digital signatures, live progress over SSE, notifications and reminders (FR-17), PDF reports and evidence packs (FR-16).

**Deliberate deviations from the spec (Task 16 records them in the vault):**
- The methodology is stored as a versioned definition and every computation reads it, but there is no editing API or screen yet; organisations configure scales and thresholds in the setup wizard (FR-24), a later phase. Only the default version exists in 1b (FR-06.1 partially).
- Risk score bands are made contiguous so every possible score has a band: Very low 1–3, Low 4–6, **Medium 7–10, High 11–16, Critical 17–25** (the methodology table lists Medium "8–10" etc. because 7, 11, 13, 14, 17–19 and 21–24 are not products of two 1–5 ratings; the result is identical).
- Threats and vulnerabilities are seeded and can be extended; risk templates are seeded and read-only in 1b (FR-06.4 partially).
- Treatment actions are rows in a generic `task` table (Data Model) managed from the risk page; the cross-module task list and "my tasks" screen are FR-10 in 1c.
- Assessment campaigns (FR-06.10, Should), triggered reassessment (FR-06.12, Should), opportunities (FR-06.14, Could) and semi-quantitative mode (FR-06.15, Could) are deferred. Links to vendors and incidents (FR-06.5) wait for those modules.
- Exports are XLSX only in 1b; branded PDF exports of the register, treatment plan and SoA (FR-06.13, FR-07.5) come with reporting in 1d.
- SoA version diff (FR-07.6, Should) and justification templates (FR-07.7, Should) are deferred; bulk applicability and source editing is included.
- Escalation of risk acceptance is shown in the product (the risk states who must accept it and only they get the button); notifications to that person come with FR-17 in 1d.
- SoA approval is the Executive's permission only (WF-09 "Executive approves"); the ISMS Manager prepares. The RBAC Matrix shows "CRUA" for the ISMS Manager, which would let a manager approve their own SoA; a manager who must approve also holds the Executive role, and the preparer can never approve their own version.
- The asset inventory is minimal: the FR-08.2 core fields, no import (FR-08.3), custom types, dependency graph or review campaign. Contributors cannot create assets yet (matrix "CR").

## Global Constraints

- Everything from the Phase 0 and 1a plans still applies: Python ≥3.12, permissive in-process dependencies only (ADR-009), no outbound network calls at runtime, UTC storage, deny-by-default RBAC, hash-chained audit trail for every change, sentence-case UI copy, Strata tokens, `source scripts/dev-env.sh` before every command.
- **Commit messages carry no `Co-Authored-By` or any Claude attribution** — the user is the only contributor (standing instruction, 2026-10-08).
- No new dependencies. XLSX uses openpyxl (already a dependency).
- Status vocabularies used verbatim by API, UI and database — risk: `draft`, `assessed`, `reassessing`, `treatment_planned`, `in_treatment`, `treated`, `accepted`, `review_due`, `closed`; task: `todo`, `in_progress`, `blocked`, `done`, `cancelled`; SoA version: `pending`, `approved`, `returned`; treatment option: `modify`, `retain`, `avoid`, `share`; approach: `event`, `asset`.
- Risk score = likelihood × consequence (1–25). Overall consequence = the highest of the five dimensions (financial, operational, legal, reputation, data).
- Acceptance authority by the band of the **current** level: Very low / Low / Medium → the risk owner (own risks) or higher; High → ISMS Manager or higher; Critical → Executive ("top management") only. Acceptance lasts 365 days, Critical 90 days.
- Suggested current level: each linked control reduces its axis by 1 level if `compliant`, 0.5 if `at_risk`, 0 otherwise; the total reduction per axis is rounded down and capped at 2; a level never drops below 1. The owner may change it only with a reason.
- Review cadence by band of the current level: Very low and Low 365 days, Medium 182, High 90, Critical 31.
- Codes: risks `R-001`, assets `AST-001`, threats `T01`, vulnerabilities `V01`, templates `RT01`; never reused within a scope.
- Every spreadsheet cell that comes from user input and starts with `=`, `+`, `-`, `@`, a tab or a carriage return is written with a leading apostrophe.
- Dates shown as `14 Feb 2026`.

## Review Focus

- A risk owner accepting their own High risk, or an ISMS Manager accepting a Critical one, must be refused with a message saying who has to accept it; an Executive can accept anything; nobody can accept a risk whose treatment actions are still open → Task 8 (`test_acceptance_needs_the_right_authority`, `test_acceptance_waits_for_open_actions`).
- Excluding a control that an active risk lists as mitigating must be refused (naming the risks), and an excluded control cannot be linked to a risk; if the database ends up that way anyway the traceability check reports it → Task 6 (`test_excluded_controls_cannot_be_linked`), Task 10 (`test_excluding_a_control_that_mitigates_a_risk_is_refused`, `test_excluded_control_that_mitigates_a_risk_is_reported`).
- An approved SoA version must never change: later edits to applicability don't alter it, it can't be approved or returned twice, and the person who prepared it can't approve it even if they hold the Executive role → Task 11 (`test_approved_version_is_frozen`, `test_preparer_cannot_approve_their_own_version`).
- An owner who overrides the suggested current level without a reason, a target worse than the current level, a current level worse than the inherent level, a missing consequence area or a rating outside the scale must each be refused with a plain message → Task 7 (`test_finalize_validation`).
- A risk title like `=HYPERLINK("http://evil","click")` must not become a live formula in exported spreadsheets → Task 9 (`test_export_neutralises_formulas`), Task 11 (`test_soa_export_lists_every_control`).

---

## File Structure

```
backend/src/assayr/
├── identity/rbac.py               # + risks/assets/soa permissions
├── identity/people_router.py      # GET /people (owner pickers)
├── catalogue/access.py            # + rights_for(), has_perm()
├── catalogue/models.py            # + Control.applicable, soa_sources, soa_justification, exclusion_reason
├── assets/{__init__,models,schemas,router}.py
├── risk/
│   ├── models.py                  # MethodologyVersion, Threat, Vulnerability, RiskTemplate, Risk, RiskControl,
│   │                              # risk_asset/risk_threat/risk_vulnerability, RiskAssessment, RiskAcceptance, RiskSnapshot
│   ├── methodology.py             # DEFAULT_METHODOLOGY + pure functions (bands, consequence, suggestion, authority)
│   ├── data/library.json          # 40 threats, 60 vulnerabilities, 25 risk templates
│   ├── seed.py                    # ensure_methodology(), ensure_risk_library()
│   ├── library_router.py          # GET /risk-methodology, GET/POST /risk-library…
│   ├── schemas.py                 # LevelOut, RiskRowOut, RiskDetailOut, inputs
│   ├── service.py                 # codes, assessments, derived status, refresh, output builders
│   ├── snapshots.py               # snapshot rows, compare()
│   └── router.py                  # /risks…, /risk-snapshots…
├── tasks/{__init__,models,router}.py   # Task model, PATCH /tasks/{id}
├── soa/{__init__,models,schemas,service,router}.py
├── exports.py                     # safe_cell(), xlsx_response()
├── scoring/service.py             # excluded controls
├── scoring/jobs.py                # scheduled check also refreshes risk statuses
├── cli.py                         # seed also loads methodology + risk library
└── migrations/versions/0005_risk_assets_soa.py
backend/tests/
├── risk_helpers.py                # assessed_risk() via the API
└── test_people.py, test_risk_models.py, test_methodology.py, test_risk_library.py, test_assets_api.py,
    test_risk_api.py, test_risk_assessment.py, test_risk_treatment.py, test_risk_snapshots.py,
    test_soa_api.py, test_soa_versions.py (+ edits: conftest, test_rbac, test_scoring, test_cli)
frontend/src/
├── styles/tokens.css, styles/global.css   # heat-1…5 tokens
├── api/types.ts                   # + risk, methodology, library, asset, SoA types
├── api/risks.ts, api/assets.ts, api/soa.ts, api/people.ts
├── components/LevelPill.tsx, components/Heatmap.tsx, components/icons.tsx (+ asset, snapshot)
├── components/AppShell.tsx        # Risks, Assets, SoA enabled
├── pages/Risks.tsx, RiskNew.tsx, RiskWizard.tsx, RiskDetail.tsx, RiskSnapshots.tsx, Assets.tsx, Soa.tsx (+ tests)
├── test/render.tsx                # ME gets the new permissions
└── router.tsx                     # + /risks, /risks/new, /risks/snapshots, /risks/$code, /risks/$code/assess, /assets, /soa
Assayr-Vault: Risk Methodology (bands), FR-06/07/08 status notes, ADR-011 Derived risk status
```

---

### Task 1: Permissions, people directory and a shared rights helper

**Files:**
- Modify: `backend/src/assayr/identity/rbac.py`, `backend/src/assayr/catalogue/access.py`, `backend/src/assayr/main.py`, `backend/tests/test_rbac.py`
- Create: `backend/src/assayr/identity/people_router.py`
- Test: `backend/tests/test_people.py`

**Interfaces:**
- Produces: `Perm.RISKS_READ` (`"risks:read"`), `RISKS_WRITE`, `RISKS_WRITE_OWN`, `RISKS_ACCEPT_MEDIUM_OWN`, `RISKS_ACCEPT_HIGH`, `RISKS_ACCEPT_CRITICAL`, `ASSETS_READ`, `ASSETS_WRITE`, `ASSETS_WRITE_OWN`, `SOA_READ`, `SOA_WRITE`, `SOA_APPROVE`; `rights_for(user, scope_id, owner_id, all_perm, own_perm) -> EditRights`; `has_perm(user, scope_id, perm) -> bool`; `GET /api/v1/people` → `[{id, full_name, email, roles: [str]}]` (active users, sorted by name; needs `controls:read`).

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_rbac.py`, replace the expected list in `test_permissions_are_a_sorted_union` with:
```python
        "assets:read",
        "assets:write",
        "audit_log:read",
        "controls:read",
        "controls:write",
        "evidence:review",
        "risks:accept_high",
        "risks:read",
        "risks:write",
        "settings:manage",
        "soa:read",
        "soa:write",
        "users:manage",
```
and append:
```python
def test_acceptance_permissions_follow_the_authority_levels():
    assert "risks:accept_critical" in permissions_for([("executive", None)])
    assert "risks:accept_high" in permissions_for([("isms_manager", None)])
    assert "risks:accept_medium_own" in permissions_for([("risk_owner", None)])
    assert "soa:approve" not in permissions_for([("isms_manager", None)])
```

`backend/tests/test_people.py`:
```python
from assayr.catalogue.access import has_perm, rights_for
from assayr.identity.rbac import Perm
from tests.conftest import create_user, sign_in


def test_people_lists_active_users_for_owner_pickers(client, db):
    create_user(db, "sana@acme.com", full_name="Sana Malik")
    create_user(db, "bilal@acme.com", roles=(("risk_owner", None),), full_name="Bilal Khan")
    create_user(db, "gone@acme.com", full_name="Gone User", active=False)
    sign_in(client, "sana@acme.com")
    body = client.get("/api/v1/people").json()
    assert [(p["full_name"], p["roles"]) for p in body] == [
        ("Bilal Khan", ["risk_owner"]),
        ("Sana Malik", ["isms_manager"]),
    ]


def test_people_needs_a_reading_role(client, db):
    create_user(db, "emp@acme.com", roles=(("employee", None),))
    sign_in(client, "emp@acme.com")
    assert client.get("/api/v1/people").status_code == 403


def test_rights_for_owner_and_manager(db, seeded):
    manager = create_user(db, "sana@acme.com")
    owner = create_user(db, "bilal@acme.com", roles=(("risk_owner", None),))
    mine = rights_for(owner, seeded.id, owner.id, Perm.RISKS_WRITE, Perm.RISKS_WRITE_OWN)
    theirs = rights_for(owner, seeded.id, manager.id, Perm.RISKS_WRITE, Perm.RISKS_WRITE_OWN)
    assert (mine.all, mine.own, theirs.any) == (False, True, False)
    assert rights_for(manager, seeded.id, None, Perm.RISKS_WRITE, Perm.RISKS_WRITE_OWN).all
    assert has_perm(manager, seeded.id, Perm.SOA_WRITE) and not has_perm(owner, seeded.id, Perm.SOA_WRITE)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_people.py tests/test_rbac.py`
Expected: FAIL — `ImportError: cannot import name 'has_perm'` and the rbac union mismatch.

- [ ] **Step 3: Implement**

In `backend/src/assayr/identity/rbac.py`, extend `Perm` and replace `ROLE_PERMISSIONS`:
```python
class Perm(StrEnum):
    CONTROLS_READ = "controls:read"
    CONTROLS_WRITE = "controls:write"
    CONTROLS_WRITE_OWN = "controls:write_own"
    USERS_MANAGE = "users:manage"
    AUDIT_LOG_READ = "audit_log:read"
    SETTINGS_MANAGE = "settings:manage"
    EVIDENCE_REVIEW = "evidence:review"
    RISKS_READ = "risks:read"
    RISKS_WRITE = "risks:write"
    RISKS_WRITE_OWN = "risks:write_own"
    RISKS_ACCEPT_MEDIUM_OWN = "risks:accept_medium_own"
    RISKS_ACCEPT_HIGH = "risks:accept_high"
    RISKS_ACCEPT_CRITICAL = "risks:accept_critical"
    ASSETS_READ = "assets:read"
    ASSETS_WRITE = "assets:write"
    ASSETS_WRITE_OWN = "assets:write_own"
    SOA_READ = "soa:read"
    SOA_WRITE = "soa:write"
    SOA_APPROVE = "soa:approve"


_READ_ALL = frozenset({Perm.CONTROLS_READ, Perm.RISKS_READ, Perm.ASSETS_READ, Perm.SOA_READ})

ROLE_PERMISSIONS: dict[Role, frozenset[Perm]] = {
    Role.PLATFORM_ADMIN: _READ_ALL | {Perm.USERS_MANAGE, Perm.SETTINGS_MANAGE, Perm.AUDIT_LOG_READ},
    Role.ISMS_MANAGER: _READ_ALL
    | {
        Perm.CONTROLS_WRITE,
        Perm.AUDIT_LOG_READ,
        Perm.EVIDENCE_REVIEW,
        Perm.RISKS_WRITE,
        Perm.RISKS_ACCEPT_HIGH,
        Perm.ASSETS_WRITE,
        Perm.SOA_WRITE,
    },
    Role.CONTROL_OWNER: _READ_ALL | {Perm.CONTROLS_WRITE_OWN, Perm.ASSETS_WRITE_OWN},
    Role.RISK_OWNER: _READ_ALL | {Perm.RISKS_WRITE_OWN, Perm.RISKS_ACCEPT_MEDIUM_OWN},
    Role.CONTRIBUTOR: _READ_ALL,
    Role.INTERNAL_AUDITOR: _READ_ALL | {Perm.AUDIT_LOG_READ},
    Role.EXTERNAL_AUDITOR: _READ_ALL,
    Role.EXECUTIVE: _READ_ALL | {Perm.RISKS_ACCEPT_CRITICAL, Perm.SOA_APPROVE},
    Role.EMPLOYEE: frozenset(),
    Role.VIEWER: _READ_ALL,
}
```

Replace `backend/src/assayr/catalogue/access.py`:
```python
import uuid
from dataclasses import dataclass

from assayr.identity.models import User
from assayr.identity.rbac import Perm, grant_for


@dataclass(frozen=True)
class EditRights:
    all: bool
    own: bool

    @property
    def any(self) -> bool:
        return self.all or self.own


def _pairs(user: User) -> list[tuple[str, uuid.UUID | None]]:
    return [(a.role, a.scope_id) for a in user.role_assignments]


def has_perm(user: User, scope_id: uuid.UUID, perm: Perm) -> bool:
    return grant_for(_pairs(user), perm).allows(scope_id)


def rights_for(
    user: User, scope_id: uuid.UUID, owner_id: uuid.UUID | None, all_perm: Perm, own_perm: Perm
) -> EditRights:
    """`all`: may edit any record of this kind in the scope. `own`: may edit this one because they own it."""
    return EditRights(
        all=has_perm(user, scope_id, all_perm),
        own=owner_id is not None and owner_id == user.id and has_perm(user, scope_id, own_perm),
    )


def edit_rights(user: User, scope_id: uuid.UUID, owner_id: uuid.UUID | None) -> EditRights:
    return rights_for(user, scope_id, owner_id, Perm.CONTROLS_WRITE, Perm.CONTROLS_WRITE_OWN)
```

`backend/src/assayr/identity/people_router.py`:
```python
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.db import get_session
from assayr.identity.deps import require
from assayr.identity.models import User
from assayr.identity.rbac import Perm

router = APIRouter(tags=["people"])


class PersonOut(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    roles: list[str]


@router.get("/people", response_model=list[PersonOut])
def list_people(_grant=Depends(require(Perm.CONTROLS_READ)), db: Session = Depends(get_session)) -> list[PersonOut]:
    """Active users, for owner and assignee pickers. Anyone who can read controls may see who works on them."""
    users = db.scalars(select(User).where(User.is_active.is_(True)).order_by(User.full_name))
    return [
        PersonOut(
            id=u.id, full_name=u.full_name, email=u.email, roles=sorted({a.role for a in u.role_assignments})
        )
        for u in users
    ]
```

In `backend/src/assayr/main.py` add `from assayr.identity.people_router import router as people_router` and `app.include_router(people_router, prefix="/api/v1")`.

- [ ] **Step 4: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest -W error`
Expected: all pass (the existing control PATCH and evidence upload tests prove `edit_rights` still behaves the same).

- [ ] **Step 5: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(identity): risk, asset and SoA permissions and a people directory"
```

---

### Task 2: Data model and migration for assets, risks, tasks and the SoA

**Files:**
- Create: `backend/src/assayr/assets/__init__.py` (empty), `backend/src/assayr/assets/models.py`, `backend/src/assayr/risk/__init__.py` (empty), `backend/src/assayr/risk/models.py`, `backend/src/assayr/tasks/__init__.py` (empty), `backend/src/assayr/tasks/models.py`, `backend/src/assayr/soa/__init__.py` (empty), `backend/src/assayr/soa/models.py`, `backend/src/assayr/migrations/versions/0005_risk_assets_soa.py`
- Modify: `backend/src/assayr/catalogue/models.py`, `backend/src/assayr/models.py`
- Test: `backend/tests/test_risk_models.py` (migration drift is covered by `test_migrations.py`)

**Interfaces:**
- Produces: `Asset` (`scope_id, code, seq, name, type, owner_id, classification, confidentiality, integrity, availability, location, description, lifecycle`, `owner`), constants `ASSET_TYPES`, `CLASSIFICATIONS`, `LIFECYCLES`; `MethodologyVersion(version_no, name, definition, effective_from)`; `Threat`, `Vulnerability` (`code, name, category, description, is_custom`); `RiskTemplate(code, title, scenario, category, threat_codes, vulnerability_codes, control_codes, likelihood, consequence)`; `Risk` (`scope_id, code, seq, title, description, approach, category, owner_id, status, treatment_option, treatment_note, treatment_budget, treatment_due, review_due, closed_at, close_reason, template_code`; relationships `owner`, `control_links`, `assets`, `threats`, `vulnerabilities`); `RiskControl(risk_id, control_id, axis, control)`; `RiskAssessment(risk_id, methodology_version_id, likelihood, consequence, current_l, current_c, current_reason, suggested, target_l, target_c, rationale, assessed_by_id, created_at, finalized_at)`; `RiskAcceptance(risk_id, assessment_id, band, score, authority, statement, accepted_by_id, accepted_at, expires_at)`; `RiskSnapshot(scope_id, label, taken_at, taken_by_id, methodology_version_id, rows)`; `Task(scope_id, entity_type, entity_id, title, assignee_id, due, status, created_by_id, done_at, assignee)`; `SoaVersion(scope_id, version_no, status, entries, prepared_by_id, prepared_at, decided_by_id, decided_at, decision_note)`; `Control.applicable` (default `True`), `Control.soa_sources`, `Control.soa_justification`, `Control.exclusion_reason`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_risk_models.py`:
```python
from sqlalchemy import func, select

from assayr.assets.models import Asset
from assayr.catalogue.models import Control
from assayr.risk.models import Risk, RiskControl, Threat
from assayr.tasks.models import Task


def test_risk_links_load_and_cascade(db, seeded):
    control = db.scalar(select(Control).where(Control.code == "A.8.13"))
    asset = Asset(scope_id=seeded.id, code="AST-001", seq=1, name="File server", type="server")
    risk = Risk(scope_id=seeded.id, code="R-001", seq=1, title="Ransomware encrypts file servers")
    risk.assets.append(asset)
    risk.threats.append(Threat(code="TX1", name="Test threat", category="Test"))
    risk.control_links.append(RiskControl(control=control, axis="likelihood"))
    db.add(risk)
    db.commit()
    db.expire_all()
    loaded = db.scalar(select(Risk))
    assert loaded.status == "draft" and loaded.approach == "event"
    assert [a.code for a in loaded.assets] == ["AST-001"]
    assert [link.control.code for link in loaded.control_links] == ["A.8.13"]
    db.delete(loaded)
    db.commit()
    assert db.scalar(select(func.count()).select_from(RiskControl)) == 0
    assert db.scalar(select(func.count()).select_from(Asset)) == 1


def test_controls_are_applicable_by_default(db, seeded):
    assert db.scalar(select(Control).limit(1)).applicable is True


def test_tasks_default_to_todo(db, seeded):
    task = Task(scope_id=seeded.id, entity_type="risk", entity_id="x", title="Enable MFA")
    db.add(task)
    db.commit()
    assert task.status == "todo" and task.created_at.utcoffset().total_seconds() == 0
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_risk_models.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'assayr.assets'`.

- [ ] **Step 3: Implement the models**

`backend/src/assayr/assets/models.py`:
```python
import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from assayr.db import Base, IdMixin, TimestampMixin
from assayr.identity.models import User

ASSET_TYPES = (
    "information",
    "application",
    "server",
    "endpoint",
    "network_device",
    "cloud_service",
    "facility",
    "people",
    "supplier_service",
)
CLASSIFICATIONS = ("public", "internal", "confidential", "restricted")
LIFECYCLES = ("planned", "in_use", "retired")


class Asset(IdMixin, TimestampMixin, Base):
    """An information or associated asset (A.5.9) used in asset-based risk assessment."""

    __tablename__ = "asset"
    __table_args__ = (UniqueConstraint("scope_id", "code", name="uq_asset_scope_code"),)

    scope_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(20))
    seq: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(30))
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    classification: Mapped[str] = mapped_column(String(20), default="internal")
    confidentiality: Mapped[int] = mapped_column(Integer, default=3)
    integrity: Mapped[int] = mapped_column(Integer, default=3)
    availability: Mapped[int] = mapped_column(Integer, default=3)
    location: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    lifecycle: Mapped[str] = mapped_column(String(20), default="in_use")

    owner: Mapped[User | None] = relationship(lazy="joined")
```

`backend/src/assayr/risk/models.py`:
```python
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Column, Date, ForeignKey, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from assayr.assets.models import Asset
from assayr.catalogue.models import Control
from assayr.db import Base, IdMixin, TimestampMixin, UTCDateTime, utcnow
from assayr.identity.models import User

risk_asset = Table(
    "risk_asset",
    Base.metadata,
    Column("risk_id", ForeignKey("risk.id", ondelete="CASCADE"), primary_key=True),
    Column("asset_id", ForeignKey("asset.id", ondelete="CASCADE"), primary_key=True),
)
risk_threat = Table(
    "risk_threat",
    Base.metadata,
    Column("risk_id", ForeignKey("risk.id", ondelete="CASCADE"), primary_key=True),
    Column("threat_id", ForeignKey("threat.id", ondelete="CASCADE"), primary_key=True),
)
risk_vulnerability = Table(
    "risk_vulnerability",
    Base.metadata,
    Column("risk_id", ForeignKey("risk.id", ondelete="CASCADE"), primary_key=True),
    Column("vulnerability_id", ForeignKey("vulnerability.id", ondelete="CASCADE"), primary_key=True),
)


class MethodologyVersion(IdMixin, Base):
    """A frozen risk methodology definition; assessments record which version rated them."""

    __tablename__ = "methodology_version"

    version_no: Mapped[int] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(String(120))
    definition: Mapped[dict] = mapped_column(JSON)
    effective_from: Mapped[datetime] = mapped_column(UTCDateTime)


class Threat(IdMixin, Base):
    __tablename__ = "threat"

    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(60))
    description: Mapped[str | None] = mapped_column(Text)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)


class Vulnerability(IdMixin, Base):
    __tablename__ = "vulnerability"

    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(60))
    description: Mapped[str | None] = mapped_column(Text)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)


class RiskTemplate(IdMixin, Base):
    """A ready-made risk scenario (Assayr-authored) so nobody starts from a blank page."""

    __tablename__ = "risk_template"

    code: Mapped[str] = mapped_column(String(20), unique=True)
    title: Mapped[str] = mapped_column(String(300))
    scenario: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(60))
    threat_codes: Mapped[list] = mapped_column(JSON)
    vulnerability_codes: Mapped[list] = mapped_column(JSON)
    control_codes: Mapped[list] = mapped_column(JSON)
    likelihood: Mapped[int] = mapped_column(Integer)
    consequence: Mapped[dict] = mapped_column(JSON)


class Risk(IdMixin, TimestampMixin, Base):
    __tablename__ = "risk"
    __table_args__ = (UniqueConstraint("scope_id", "code", name="uq_risk_scope_code"),)

    scope_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(20))
    seq: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    approach: Mapped[str] = mapped_column(String(10), default="event")
    category: Mapped[str | None] = mapped_column(String(60))
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(30), default="draft")
    treatment_option: Mapped[str | None] = mapped_column(String(10))
    treatment_note: Mapped[str | None] = mapped_column(Text)
    treatment_budget: Mapped[str | None] = mapped_column(String(100))
    treatment_due: Mapped[date | None] = mapped_column(Date)
    review_due: Mapped[date | None] = mapped_column(Date)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    close_reason: Mapped[str | None] = mapped_column(Text)
    template_code: Mapped[str | None] = mapped_column(String(20))

    owner: Mapped[User | None] = relationship(lazy="joined")
    control_links: Mapped[list[RiskControl]] = relationship(
        back_populates="risk", cascade="all, delete-orphan", lazy="selectin"
    )
    assets: Mapped[list[Asset]] = relationship(secondary=risk_asset, lazy="selectin", order_by=Asset.seq)
    threats: Mapped[list[Threat]] = relationship(secondary=risk_threat, lazy="selectin", order_by=Threat.code)
    vulnerabilities: Mapped[list[Vulnerability]] = relationship(
        secondary=risk_vulnerability, lazy="selectin", order_by=Vulnerability.code
    )


class RiskControl(Base):
    """A control that mitigates a risk, and which axis (likelihood or consequence) it reduces."""

    __tablename__ = "risk_control"

    risk_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("risk.id", ondelete="CASCADE"), primary_key=True)
    control_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("control.id", ondelete="CASCADE"), primary_key=True)
    axis: Mapped[str] = mapped_column(String(12), default="likelihood")

    risk: Mapped[Risk] = relationship(back_populates="control_links")
    control: Mapped[Control] = relationship(lazy="joined")


class RiskAssessment(IdMixin, Base):
    """One rating of a risk. Open (finalized_at is null) while being worked on; frozen once finalized."""

    __tablename__ = "risk_assessment"

    risk_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("risk.id", ondelete="CASCADE"), index=True)
    methodology_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodology_version.id"))
    likelihood: Mapped[int | None] = mapped_column(Integer)
    consequence: Mapped[dict | None] = mapped_column(JSON)
    current_l: Mapped[int | None] = mapped_column(Integer)
    current_c: Mapped[int | None] = mapped_column(Integer)
    current_reason: Mapped[str | None] = mapped_column(Text)
    suggested: Mapped[dict | None] = mapped_column(JSON)
    target_l: Mapped[int | None] = mapped_column(Integer)
    target_c: Mapped[int | None] = mapped_column(Integer)
    rationale: Mapped[str | None] = mapped_column(Text)
    assessed_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    finalized_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class RiskAcceptance(IdMixin, Base):
    __tablename__ = "risk_acceptance"

    risk_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("risk.id", ondelete="CASCADE"), index=True)
    assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("risk_assessment.id", ondelete="CASCADE"))
    band: Mapped[str] = mapped_column(String(20))
    score: Mapped[int] = mapped_column(Integer)
    authority: Mapped[str] = mapped_column(String(20))
    statement: Mapped[str] = mapped_column(Text)
    accepted_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    accepted_at: Mapped[datetime] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)


class RiskSnapshot(IdMixin, Base):
    """A frozen copy of the register (clause 8.2 record)."""

    __tablename__ = "risk_snapshot"

    scope_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(200))
    taken_at: Mapped[datetime] = mapped_column(UTCDateTime)
    taken_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    methodology_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodology_version.id"))
    rows: Mapped[list] = mapped_column(JSON)
```

`backend/src/assayr/tasks/models.py`:
```python
import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from assayr.db import Base, IdMixin, TimestampMixin, UTCDateTime
from assayr.identity.models import User

TASK_STATUSES = ("todo", "in_progress", "blocked", "done", "cancelled")


class Task(IdMixin, TimestampMixin, Base):
    """A unit of work attached to any record (a risk treatment action in 1b)."""

    __tablename__ = "task"
    __table_args__ = (Index("ix_task_entity", "entity_type", "entity_id"),)

    scope_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"))
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(300))
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    due: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="todo")
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    done_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id], lazy="joined")
```

`backend/src/assayr/soa/models.py`:
```python
import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from assayr.db import Base, IdMixin, UTCDateTime


class SoaVersion(IdMixin, Base):
    """A submitted Statement of Applicability. Entries are frozen when it is submitted."""

    __tablename__ = "soa_version"
    __table_args__ = (UniqueConstraint("scope_id", "version_no", name="uq_soa_version_scope_no"),)

    scope_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"))
    version_no: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    entries: Mapped[list] = mapped_column(JSON)
    prepared_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    prepared_at: Mapped[datetime] = mapped_column(UTCDateTime)
    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    decision_note: Mapped[str | None] = mapped_column(Text)
```

In `backend/src/assayr/catalogue/models.py`, add `Boolean` and `true` to the `sqlalchemy` import and add to `Control` after `score`:
```python
    applicable: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    soa_sources: Mapped[list | None] = mapped_column(JSON)
    soa_justification: Mapped[str | None] = mapped_column(Text)
    exclusion_reason: Mapped[str | None] = mapped_column(Text)
```

Add to `backend/src/assayr/models.py` (keep the existing imports):
```python
from assayr.assets.models import Asset  # noqa: F401
from assayr.risk.models import (  # noqa: F401
    MethodologyVersion,
    Risk,
    RiskAcceptance,
    RiskAssessment,
    RiskControl,
    RiskSnapshot,
    RiskTemplate,
    Threat,
    Vulnerability,
)
from assayr.soa.models import SoaVersion  # noqa: F401
from assayr.tasks.models import Task  # noqa: F401
```

- [ ] **Step 4: Write migration 0005**

`backend/src/assayr/migrations/versions/0005_risk_assets_soa.py`:
```python
"""assets, risk register, tasks and statement of applicability

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _user_fk(column: str, table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["user_account.id"], name=f"fk_{table}_{column}_user_account", ondelete="SET NULL"
    )


def _scope_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(["scope_id"], ["scope.id"], name=f"fk_{table}_scope_id_scope", ondelete="CASCADE")


def _library_table(name: str) -> None:
    op.create_table(
        name,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_custom", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=f"pk_{name}"),
        sa.UniqueConstraint("code", name=f"uq_{name}_code"),
    )


def _link_table(name: str, other: str) -> None:
    op.create_table(
        name,
        sa.Column("risk_id", sa.Uuid(), nullable=False),
        sa.Column(f"{other}_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["risk_id"], ["risk.id"], name=f"fk_{name}_risk_id_risk", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            [f"{other}_id"], [f"{other}.id"], name=f"fk_{name}_{other}_id_{other}", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("risk_id", f"{other}_id", name=f"pk_{name}"),
    )


def upgrade() -> None:
    op.add_column("control", sa.Column("applicable", sa.Boolean(), server_default=sa.true(), nullable=False))
    op.add_column("control", sa.Column("soa_sources", sa.JSON(), nullable=True))
    op.add_column("control", sa.Column("soa_justification", sa.Text(), nullable=True))
    op.add_column("control", sa.Column("exclusion_reason", sa.Text(), nullable=True))

    op.create_table(
        "asset",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("classification", sa.String(length=20), nullable=False),
        sa.Column("confidentiality", sa.Integer(), nullable=False),
        sa.Column("integrity", sa.Integer(), nullable=False),
        sa.Column("availability", sa.Integer(), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("lifecycle", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        _scope_fk("asset"),
        _user_fk("owner_id", "asset"),
        sa.PrimaryKeyConstraint("id", name="pk_asset"),
        sa.UniqueConstraint("scope_id", "code", name="uq_asset_scope_code"),
    )
    op.create_table(
        "methodology_version",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_methodology_version"),
        sa.UniqueConstraint("version_no", name="uq_methodology_version_version_no"),
    )
    _library_table("threat")
    _library_table("vulnerability")
    op.create_table(
        "risk_template",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("scenario", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=False),
        sa.Column("threat_codes", sa.JSON(), nullable=False),
        sa.Column("vulnerability_codes", sa.JSON(), nullable=False),
        sa.Column("control_codes", sa.JSON(), nullable=False),
        sa.Column("likelihood", sa.Integer(), nullable=False),
        sa.Column("consequence", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_risk_template"),
        sa.UniqueConstraint("code", name="uq_risk_template_code"),
    )
    op.create_table(
        "risk",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("approach", sa.String(length=10), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=True),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("treatment_option", sa.String(length=10), nullable=True),
        sa.Column("treatment_note", sa.Text(), nullable=True),
        sa.Column("treatment_budget", sa.String(length=100), nullable=True),
        sa.Column("treatment_due", sa.Date(), nullable=True),
        sa.Column("review_due", sa.Date(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_reason", sa.Text(), nullable=True),
        sa.Column("template_code", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        _scope_fk("risk"),
        _user_fk("owner_id", "risk"),
        sa.PrimaryKeyConstraint("id", name="pk_risk"),
        sa.UniqueConstraint("scope_id", "code", name="uq_risk_scope_code"),
    )
    _link_table("risk_asset", "asset")
    _link_table("risk_threat", "threat")
    _link_table("risk_vulnerability", "vulnerability")
    op.create_table(
        "risk_control",
        sa.Column("risk_id", sa.Uuid(), nullable=False),
        sa.Column("control_id", sa.Uuid(), nullable=False),
        sa.Column("axis", sa.String(length=12), nullable=False),
        sa.ForeignKeyConstraint(["risk_id"], ["risk.id"], name="fk_risk_control_risk_id_risk", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["control_id"], ["control.id"], name="fk_risk_control_control_id_control", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("risk_id", "control_id", name="pk_risk_control"),
    )
    op.create_table(
        "risk_assessment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("risk_id", sa.Uuid(), nullable=False),
        sa.Column("methodology_version_id", sa.Uuid(), nullable=False),
        sa.Column("likelihood", sa.Integer(), nullable=True),
        sa.Column("consequence", sa.JSON(), nullable=True),
        sa.Column("current_l", sa.Integer(), nullable=True),
        sa.Column("current_c", sa.Integer(), nullable=True),
        sa.Column("current_reason", sa.Text(), nullable=True),
        sa.Column("suggested", sa.JSON(), nullable=True),
        sa.Column("target_l", sa.Integer(), nullable=True),
        sa.Column("target_c", sa.Integer(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("assessed_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["risk_id"], ["risk.id"], name="fk_risk_assessment_risk_id_risk", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["methodology_version_id"],
            ["methodology_version.id"],
            name="fk_risk_assessment_methodology_version_id_methodology_version",
        ),
        _user_fk("assessed_by_id", "risk_assessment"),
        sa.PrimaryKeyConstraint("id", name="pk_risk_assessment"),
    )
    op.create_index("ix_risk_assessment_risk_id", "risk_assessment", ["risk_id"])
    op.create_table(
        "risk_acceptance",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("risk_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("band", sa.String(length=20), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("authority", sa.String(length=20), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("accepted_by_id", sa.Uuid(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["risk_id"], ["risk.id"], name="fk_risk_acceptance_risk_id_risk", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["risk_assessment.id"],
            name="fk_risk_acceptance_assessment_id_risk_assessment",
            ondelete="CASCADE",
        ),
        _user_fk("accepted_by_id", "risk_acceptance"),
        sa.PrimaryKeyConstraint("id", name="pk_risk_acceptance"),
    )
    op.create_index("ix_risk_acceptance_risk_id", "risk_acceptance", ["risk_id"])
    op.create_table(
        "risk_snapshot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("taken_by_id", sa.Uuid(), nullable=True),
        sa.Column("methodology_version_id", sa.Uuid(), nullable=False),
        sa.Column("rows", sa.JSON(), nullable=False),
        _scope_fk("risk_snapshot"),
        _user_fk("taken_by_id", "risk_snapshot"),
        sa.ForeignKeyConstraint(
            ["methodology_version_id"],
            ["methodology_version.id"],
            name="fk_risk_snapshot_methodology_version_id_methodology_version",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_risk_snapshot"),
    )
    op.create_index("ix_risk_snapshot_scope_id", "risk_snapshot", ["scope_id"])
    op.create_table(
        "task",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("assignee_id", sa.Uuid(), nullable=True),
        sa.Column("due", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        _scope_fk("task"),
        _user_fk("assignee_id", "task"),
        _user_fk("created_by_id", "task"),
        sa.PrimaryKeyConstraint("id", name="pk_task"),
    )
    op.create_index("ix_task_entity", "task", ["entity_type", "entity_id"])
    op.create_table(
        "soa_version",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("entries", sa.JSON(), nullable=False),
        sa.Column("prepared_by_id", sa.Uuid(), nullable=True),
        sa.Column("prepared_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by_id", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        _scope_fk("soa_version"),
        _user_fk("prepared_by_id", "soa_version"),
        _user_fk("decided_by_id", "soa_version"),
        sa.PrimaryKeyConstraint("id", name="pk_soa_version"),
        sa.UniqueConstraint("scope_id", "version_no", name="uq_soa_version_scope_no"),
    )


def downgrade() -> None:
    op.drop_table("soa_version")
    op.drop_index("ix_task_entity", table_name="task")
    op.drop_table("task")
    op.drop_index("ix_risk_snapshot_scope_id", table_name="risk_snapshot")
    op.drop_table("risk_snapshot")
    op.drop_index("ix_risk_acceptance_risk_id", table_name="risk_acceptance")
    op.drop_table("risk_acceptance")
    op.drop_index("ix_risk_assessment_risk_id", table_name="risk_assessment")
    op.drop_table("risk_assessment")
    op.drop_table("risk_control")
    op.drop_table("risk_vulnerability")
    op.drop_table("risk_threat")
    op.drop_table("risk_asset")
    op.drop_table("risk")
    op.drop_table("risk_template")
    op.drop_table("vulnerability")
    op.drop_table("threat")
    op.drop_table("methodology_version")
    op.drop_table("asset")
    with op.batch_alter_table("control") as batch:
        batch.drop_column("exclusion_reason")
        batch.drop_column("soa_justification")
        batch.drop_column("soa_sources")
        batch.drop_column("applicable")
```
(`RiskSnapshot.scope_id` is declared with `index=True` in the model, matching `ix_risk_snapshot_scope_id`.)

- [ ] **Step 5: Run the whole backend suite**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest -W error`
Expected: all pass, including `test_migrations_match_models_and_downgrade_cleanly`.

- [ ] **Step 6: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(risk): data model for assets, risks, tasks and the statement of applicability"
```

---
### Task 3: The risk methodology as pure functions

**Files:**
- Create: `backend/src/assayr/risk/methodology.py`
- Test: `backend/tests/test_methodology.py`

**Interfaces:**
- Consumes: `MethodologyVersion` (Task 2).
- Produces: `DEFAULT_METHODOLOGY: dict` (keys `name`, `likelihood` [{level, label, guidance}], `consequence` {`levels` [{level, label}], `dimensions` [{key, label, guidance: [5 strings]}]}, `bands` [{key, label, min, max, above_appetite, treatment_required, authority, review_days, rule}], `acceptance_days` {default, critical}, `max_control_reduction`); `AUTHORITY_ORDER`, `AUTHORITY_LABEL`; `active_methodology(db) -> MethodologyVersion | None`; `dimension_keys(definition) -> list[str]`; `overall_consequence(definition, ratings: dict | None) -> int | None`; `band_for(definition, likelihood, consequence) -> dict`; `suggest_current(definition, likelihood, consequence, links: Iterable[tuple[axis, control_status]]) -> tuple[int, int]`; `authority_allows(held: str | None, required: str) -> bool`; `acceptance_days(definition, band_key) -> int`; `rating_error(definition, *, likelihood=None, consequence=None, current=(None, None), target=(None, None)) -> str | None`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_methodology.py`:
```python
import pytest

from assayr.risk.methodology import DEFAULT_METHODOLOGY as M
from assayr.risk.methodology import (
    acceptance_days,
    authority_allows,
    band_for,
    overall_consequence,
    rating_error,
    suggest_current,
)

FULL = {"financial": 2, "operational": 5, "legal": 3, "reputation": 4, "data": 1}


def test_every_possible_score_has_exactly_one_band():
    for likelihood in range(1, 6):
        for consequence in range(1, 6):
            score = likelihood * consequence
            assert len([b for b in M["bands"] if b["min"] <= score <= b["max"]]) == 1, score


@pytest.mark.parametrize(
    "likelihood,consequence,band",
    [(1, 3, "very_low"), (2, 3, "low"), (2, 4, "medium"), (3, 4, "high"), (4, 4, "high"), (4, 5, "critical")],
)
def test_band_for(likelihood, consequence, band):
    assert band_for(M, likelihood, consequence)["key"] == band


def test_overall_consequence_is_the_highest_area_and_needs_every_area():
    assert overall_consequence(M, FULL) == 5
    assert overall_consequence(M, {"financial": 2}) is None
    assert overall_consequence(M, None) is None


@pytest.mark.parametrize(
    "links,expected",
    [
        ([], (4, 5)),
        ([("likelihood", "compliant")], (3, 5)),
        ([("likelihood", "compliant")] * 3, (2, 5)),
        ([("likelihood", "at_risk")], (4, 5)),
        ([("likelihood", "at_risk")] * 2, (3, 5)),
        ([("consequence", "compliant"), ("likelihood", "non_compliant")], (4, 4)),
    ],
)
def test_suggest_current(links, expected):
    assert suggest_current(M, 4, 5, links) == expected


def test_suggestion_never_goes_below_one():
    assert suggest_current(M, 1, 2, [("likelihood", "compliant")] * 2) == (1, 2)


def test_authority_order():
    assert authority_allows("executive", "executive") and authority_allows("executive", "risk_owner")
    assert authority_allows("isms_manager", "isms_manager") and not authority_allows("isms_manager", "executive")
    assert not authority_allows("risk_owner", "isms_manager") and not authority_allows(None, "risk_owner")


def test_acceptance_days():
    assert acceptance_days(M, "critical") == 90 and acceptance_days(M, "high") == 365


def test_rating_errors():
    assert rating_error(M, likelihood=6) == "Likelihood must be between 1 and 5."
    assert rating_error(M, consequence={"financial": 0}) == "Financial must be between 1 and 5."
    assert rating_error(M, consequence={"weather": 2}) == "Unknown consequence area: weather."
    assert rating_error(M, current=(3, 9)) == "The current level is outside the scale."
    assert rating_error(M, likelihood=3, consequence={"data": 5}, target=(1, 1)) is None
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_methodology.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'assayr.risk.methodology'`.

- [ ] **Step 3: Implement**

`backend/src/assayr/risk/methodology.py`:
```python
"""The risk methodology (vault: 03-Product/Risk Methodology.md). Every rating decision is a pure function of it."""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.risk.models import MethodologyVersion

AUTHORITY_ORDER = ("risk_owner", "isms_manager", "executive")
AUTHORITY_LABEL = {"risk_owner": "the risk owner", "isms_manager": "an ISMS manager", "executive": "top management"}
# How much one linked control reduces its axis, by the control's derived status.
CONTROL_EFFECT = {"compliant": 1.0, "at_risk": 0.5}

DEFAULT_METHODOLOGY: dict = {
    "name": "Assayr default (ISO/IEC 27005:2022)",
    "likelihood": [
        {"level": 1, "label": "Rare", "guidance": "Not expected in 5+ years"},
        {"level": 2, "label": "Unlikely", "guidance": "Could happen once in 2–5 years"},
        {"level": 3, "label": "Possible", "guidance": "Could happen once a year"},
        {"level": 4, "label": "Likely", "guidance": "Several times a year"},
        {"level": 5, "label": "Almost certain", "guidance": "Monthly or more"},
    ],
    "consequence": {
        "levels": [
            {"level": 1, "label": "Negligible"},
            {"level": 2, "label": "Minor"},
            {"level": 3, "label": "Moderate"},
            {"level": 4, "label": "Major"},
            {"level": 5, "label": "Severe"},
        ],
        "dimensions": [
            {
                "key": "financial",
                "label": "Financial",
                "guidance": [
                    "< 0.1% of revenue",
                    "0.1–0.5% of revenue",
                    "0.5–2% of revenue",
                    "2–5% of revenue",
                    "> 5% of revenue",
                ],
            },
            {
                "key": "operational",
                "label": "Operational",
                "guidance": ["< 1 hour of disruption", "< 1 day", "1–3 days", "3–7 days", "> 7 days"],
            },
            {
                "key": "legal",
                "label": "Legal / regulatory",
                "guidance": [
                    "None",
                    "Minor breach, no penalty",
                    "Reportable incident",
                    "Penalty or enforcement",
                    "Licence loss or prosecution",
                ],
            },
            {
                "key": "reputation",
                "label": "Reputation",
                "guidance": ["None", "Local, short-lived", "Regional media", "National media", "Lasting brand damage"],
            },
            {
                "key": "data",
                "label": "Data (C/I/A)",
                "guidance": [
                    "Internal data, no impact",
                    "Limited internal exposure",
                    "Confidential data, < 1k records",
                    "Confidential data, 1k–100k records",
                    "> 100k records or restricted data",
                ],
            },
        ],
    },
    "bands": [
        {
            "key": "very_low",
            "label": "Very low",
            "min": 1,
            "max": 3,
            "above_appetite": False,
            "treatment_required": False,
            "authority": "risk_owner",
            "review_days": 365,
            "rule": "Accept; the risk owner is aware.",
        },
        {
            "key": "low",
            "label": "Low",
            "min": 4,
            "max": 6,
            "above_appetite": False,
            "treatment_required": False,
            "authority": "risk_owner",
            "review_days": 365,
            "rule": "Accept by the risk owner.",
        },
        {
            "key": "medium",
            "label": "Medium",
            "min": 7,
            "max": 10,
            "above_appetite": True,
            "treatment_required": False,
            "authority": "risk_owner",
            "review_days": 182,
            "rule": "Treat, or accept with the risk owner's justification.",
        },
        {
            "key": "high",
            "label": "High",
            "min": 11,
            "max": 16,
            "above_appetite": True,
            "treatment_required": True,
            "authority": "isms_manager",
            "review_days": 90,
            "rule": "A treatment plan is required; the residual risk is accepted by an ISMS manager.",
        },
        {
            "key": "critical",
            "label": "Critical",
            "min": 17,
            "max": 25,
            "above_appetite": True,
            "treatment_required": True,
            "authority": "executive",
            "review_days": 31,
            "rule": "Treat immediately; only top management can accept the residual risk.",
        },
    ],
    "acceptance_days": {"default": 365, "critical": 90},
    "max_control_reduction": 2,
}


def active_methodology(db: Session) -> MethodologyVersion | None:
    return db.scalar(select(MethodologyVersion).order_by(MethodologyVersion.version_no.desc()).limit(1))


def dimension_keys(definition: dict) -> list[str]:
    return [d["key"] for d in definition["consequence"]["dimensions"]]


def overall_consequence(definition: dict, ratings: dict | None) -> int | None:
    """The highest consequence across all areas, or None until every area is rated."""
    keys = dimension_keys(definition)
    if not ratings or any(key not in ratings for key in keys):
        return None
    return max(int(ratings[key]) for key in keys)


def band_for(definition: dict, likelihood: int, consequence: int) -> dict:
    score = likelihood * consequence
    for band in definition["bands"]:
        if band["min"] <= score <= band["max"]:
            return band
    raise ValueError(f"No band covers score {score}.")


def suggest_current(
    definition: dict, likelihood: int, consequence: int, links: Iterable[tuple[str, str]]
) -> tuple[int, int]:
    """Lower each axis by the effect of the controls that reduce it (rounded down, capped, never below 1)."""
    reduction = {"likelihood": 0.0, "consequence": 0.0}
    for axis, control_status in links:
        reduction[axis] += CONTROL_EFFECT.get(control_status, 0.0)
    cap = definition["max_control_reduction"]
    return (
        max(1, likelihood - min(cap, int(reduction["likelihood"]))),
        max(1, consequence - min(cap, int(reduction["consequence"]))),
    )


def authority_allows(held: str | None, required: str) -> bool:
    if held is None:
        return False
    return AUTHORITY_ORDER.index(held) >= AUTHORITY_ORDER.index(required)


def acceptance_days(definition: dict, band_key: str) -> int:
    days = definition["acceptance_days"]
    return days.get(band_key, days["default"])


def rating_error(
    definition: dict,
    *,
    likelihood: int | None = None,
    consequence: dict | None = None,
    current: tuple[int | None, int | None] = (None, None),
    target: tuple[int | None, int | None] = (None, None),
) -> str | None:
    max_l = len(definition["likelihood"])
    max_c = len(definition["consequence"]["levels"])

    def outside(value: int | None, top: int) -> bool:
        return value is not None and not 1 <= value <= top

    if outside(likelihood, max_l):
        return f"Likelihood must be between 1 and {max_l}."
    labels = {d["key"]: d["label"] for d in definition["consequence"]["dimensions"]}
    for key, value in (consequence or {}).items():
        if key not in labels:
            return f"Unknown consequence area: {key}."
        if outside(value, max_c):
            return f"{labels[key]} must be between 1 and {max_c}."
    for name, (level_l, level_c) in (("current", current), ("target", target)):
        if outside(level_l, max_l) or outside(level_c, max_c):
            return f"The {name} level is outside the scale."
    return None
```

- [ ] **Step 4: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_methodology.py -W error`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(risk): default methodology with bands, suggestion and authority rules"
```

---

### Task 4: Risk libraries, seeding and the methodology/library API

**Files:**
- Create: `backend/src/assayr/risk/data/library.json`, `backend/src/assayr/risk/seed.py`, `backend/src/assayr/risk/library_router.py`
- Modify: `backend/src/assayr/cli.py` (`seed`), `backend/src/assayr/main.py`, `backend/tests/conftest.py` (`seeded`), `backend/tests/test_cli.py`
- Test: `backend/tests/test_risk_library.py`

**Interfaces:**
- Consumes: `DEFAULT_METHODOLOGY`, `active_methodology` (Task 3); models (Task 2).
- Produces: `ensure_methodology(db, now) -> MethodologyVersion`; `LibraryResult(threats, vulnerabilities, templates)`; `ensure_risk_library(db) -> LibraryResult`; `require_methodology(db) -> MethodologyVersion` (404 when missing); `GET /api/v1/risk-methodology` → `{version_no, name, likelihood, consequence, bands}`; `GET /api/v1/risk-library` → `{threats, vulnerabilities, templates}` (items `{code, name, category, description, is_custom}`, templates `{code, title, scenario, category, threat_codes, vulnerability_codes, control_codes, likelihood, consequence}`); `POST /api/v1/risk-library/threats` and `/vulnerabilities` (`{name, category, description?}` → 201 item with the next code); the `seeded` fixture now also loads the methodology and the library.

- [ ] **Step 1: Write the library data**

`backend/src/assayr/risk/data/library.json`:
```json
{
  "threats": [
    {"code": "T01", "name": "Ransomware", "category": "Malicious software"},
    {"code": "T02", "name": "Malware infection", "category": "Malicious software"},
    {"code": "T03", "name": "Phishing and social engineering", "category": "Human"},
    {"code": "T04", "name": "Business email compromise", "category": "Fraud"},
    {"code": "T05", "name": "Password attacks and credential stuffing", "category": "Unauthorised access"},
    {"code": "T06", "name": "Exploitation of an unpatched vulnerability", "category": "Technical attack"},
    {"code": "T07", "name": "Web application attack", "category": "Technical attack"},
    {"code": "T08", "name": "Denial of service", "category": "Technical attack"},
    {"code": "T09", "name": "Insider data theft", "category": "Insider"},
    {"code": "T10", "name": "Insider sabotage", "category": "Insider"},
    {"code": "T11", "name": "Accidental disclosure by staff", "category": "Human error"},
    {"code": "T12", "name": "Misconfiguration", "category": "Human error"},
    {"code": "T13", "name": "Loss or theft of a laptop or mobile device", "category": "Physical"},
    {"code": "T14", "name": "Unauthorised physical access", "category": "Physical"},
    {"code": "T15", "name": "Fire", "category": "Environmental"},
    {"code": "T16", "name": "Flood or water damage", "category": "Environmental"},
    {"code": "T17", "name": "Power failure", "category": "Infrastructure"},
    {"code": "T18", "name": "Hardware failure", "category": "Infrastructure"},
    {"code": "T19", "name": "Network or telecom outage", "category": "Infrastructure"},
    {"code": "T20", "name": "Cloud service provider outage", "category": "Supplier"},
    {"code": "T21", "name": "Supplier data breach", "category": "Supplier"},
    {"code": "T22", "name": "Software supply-chain compromise", "category": "Supplier"},
    {"code": "T23", "name": "Unauthorised change to systems", "category": "Change"},
    {"code": "T24", "name": "Data corruption", "category": "Technical"},
    {"code": "T25", "name": "Backup failure", "category": "Technical"},
    {"code": "T26", "name": "Privilege abuse by administrators", "category": "Insider"},
    {"code": "T27", "name": "Takeover of a privileged account", "category": "Unauthorised access"},
    {"code": "T28", "name": "Shadow IT and unapproved services", "category": "Governance"},
    {"code": "T29", "name": "Regulatory non-compliance", "category": "Legal"},
    {"code": "T30", "name": "Contractual breach", "category": "Legal"},
    {"code": "T31", "name": "Loss of key personnel", "category": "People"},
    {"code": "T32", "name": "Pandemic or mass absence", "category": "Environmental"},
    {"code": "T33", "name": "Interception of network traffic", "category": "Technical attack"},
    {"code": "T34", "name": "Compromise of cryptographic keys", "category": "Technical attack"},
    {"code": "T35", "name": "Misuse of removable media", "category": "Human"},
    {"code": "T36", "name": "Improper disposal of equipment or media", "category": "Physical"},
    {"code": "T37", "name": "Payment fraud", "category": "Fraud"},
    {"code": "T38", "name": "Targeted espionage (advanced persistent threat)", "category": "Technical attack"},
    {"code": "T39", "name": "Data leakage through AI or online tools", "category": "Human"},
    {"code": "T40", "name": "Civil unrest or terrorism", "category": "Environmental"}
  ],
  "vulnerabilities": [
    {"code": "V01", "name": "Missing security patches", "category": "Technical"},
    {"code": "V02", "name": "Unsupported (end-of-life) software", "category": "Technical"},
    {"code": "V03", "name": "Weak or default passwords", "category": "Technical"},
    {"code": "V04", "name": "No multi-factor authentication", "category": "Technical"},
    {"code": "V05", "name": "Excessive user privileges", "category": "Technical"},
    {"code": "V06", "name": "Shared or generic accounts", "category": "Technical"},
    {"code": "V07", "name": "Dormant accounts not removed", "category": "Technical"},
    {"code": "V08", "name": "Unencrypted data at rest", "category": "Technical"},
    {"code": "V09", "name": "Unencrypted data in transit", "category": "Technical"},
    {"code": "V10", "name": "Open or unnecessary network ports", "category": "Technical"},
    {"code": "V11", "name": "Flat network without segmentation", "category": "Technical"},
    {"code": "V12", "name": "Insecure remote access", "category": "Technical"},
    {"code": "V13", "name": "No endpoint protection", "category": "Technical"},
    {"code": "V14", "name": "No email filtering", "category": "Technical"},
    {"code": "V15", "name": "Insufficient logging", "category": "Technical"},
    {"code": "V16", "name": "Logs not monitored", "category": "Technical"},
    {"code": "V17", "name": "No backups, or backups never tested", "category": "Technical"},
    {"code": "V18", "name": "Backups reachable from the production network", "category": "Technical"},
    {"code": "V19", "name": "Single point of failure in infrastructure", "category": "Technical"},
    {"code": "V20", "name": "Insecure application code", "category": "Technical"},
    {"code": "V21", "name": "No web application firewall", "category": "Technical"},
    {"code": "V22", "name": "Insecure APIs", "category": "Technical"},
    {"code": "V23", "name": "Misconfigured cloud storage", "category": "Technical"},
    {"code": "V24", "name": "Unmanaged personal devices", "category": "Technical"},
    {"code": "V25", "name": "Unrestricted USB ports", "category": "Technical"},
    {"code": "V26", "name": "Weak cryptographic algorithms", "category": "Technical"},
    {"code": "V27", "name": "Poor key management", "category": "Technical"},
    {"code": "V28", "name": "No data loss prevention", "category": "Technical"},
    {"code": "V29", "name": "Inadequate capacity planning", "category": "Technical"},
    {"code": "V30", "name": "Unmonitored privileged access", "category": "Technical"},
    {"code": "V31", "name": "No asset inventory", "category": "Process"},
    {"code": "V32", "name": "No change management", "category": "Process"},
    {"code": "V33", "name": "No vulnerability management process", "category": "Process"},
    {"code": "V34", "name": "No incident response plan", "category": "Process"},
    {"code": "V35", "name": "Untested business continuity plan", "category": "Process"},
    {"code": "V36", "name": "No access review process", "category": "Process"},
    {"code": "V37", "name": "No joiner-mover-leaver process", "category": "Process"},
    {"code": "V38", "name": "No supplier security assessment", "category": "Process"},
    {"code": "V39", "name": "No security clauses in contracts", "category": "Process"},
    {"code": "V40", "name": "No information classification", "category": "Process"},
    {"code": "V41", "name": "No secure disposal procedure", "category": "Process"},
    {"code": "V42", "name": "No secure development lifecycle", "category": "Process"},
    {"code": "V43", "name": "Segregation of duties not enforced", "category": "Process"},
    {"code": "V44", "name": "No security requirements for projects", "category": "Process"},
    {"code": "V45", "name": "Outdated or missing policies", "category": "Process"},
    {"code": "V46", "name": "No register of legal and regulatory requirements", "category": "Process"},
    {"code": "V47", "name": "Low security awareness", "category": "People"},
    {"code": "V48", "name": "No phishing training", "category": "People"},
    {"code": "V49", "name": "Background checks not performed", "category": "People"},
    {"code": "V50", "name": "Dependence on a single key person", "category": "People"},
    {"code": "V51", "name": "Too few security staff", "category": "People"},
    {"code": "V52", "name": "Unclear security responsibilities", "category": "People"},
    {"code": "V53", "name": "Weak building access control", "category": "Physical"},
    {"code": "V54", "name": "No visitor management", "category": "Physical"},
    {"code": "V55", "name": "Unsecured server room", "category": "Physical"},
    {"code": "V56", "name": "No fire detection or suppression", "category": "Physical"},
    {"code": "V57", "name": "No UPS or generator", "category": "Physical"},
    {"code": "V58", "name": "Equipment and papers left unattended", "category": "Physical"},
    {"code": "V59", "name": "Dependence on a single supplier", "category": "Supplier"},
    {"code": "V60", "name": "No exit plan for cloud services", "category": "Supplier"}
  ],
  "templates": [
    {"code": "RT01", "title": "Ransomware encrypts file servers", "category": "Cyber attack",
     "scenario": "Ransomware enters through an unpatched system or a phishing email, spreads across the flat network and encrypts file servers and reachable backups, stopping operations.",
     "threats": ["T01"], "vulnerabilities": ["V01", "V11", "V17", "V18", "V47"],
     "controls": ["A.8.7", "A.8.8", "A.8.13", "A.8.22", "A.6.3"], "likelihood": 3,
     "consequence": {"financial": 4, "operational": 5, "legal": 3, "reputation": 4, "data": 4}},
    {"code": "RT02", "title": "Phishing leads to account compromise", "category": "Cyber attack",
     "scenario": "A member of staff enters their password on a phishing page; without multi-factor authentication the attacker signs in and reads mail and files.",
     "threats": ["T03", "T27"], "vulnerabilities": ["V04", "V14", "V48"],
     "controls": ["A.5.17", "A.8.5", "A.6.3", "A.8.23"], "likelihood": 4,
     "consequence": {"financial": 3, "operational": 2, "legal": 3, "reputation": 3, "data": 3}},
    {"code": "RT03", "title": "Business email compromise causes a fraudulent payment", "category": "Fraud",
     "scenario": "An attacker impersonates an executive or supplier by email and convinces finance to change bank details or approve an urgent transfer.",
     "threats": ["T04", "T37"], "vulnerabilities": ["V04", "V43", "V47"],
     "controls": ["A.5.17", "A.8.5", "A.6.3", "A.5.3"], "likelihood": 3,
     "consequence": {"financial": 4, "operational": 1, "legal": 2, "reputation": 3, "data": 1}},
    {"code": "RT04", "title": "Unpatched internet-facing system is exploited", "category": "Cyber attack",
     "scenario": "A known vulnerability in an internet-facing server or VPN appliance is exploited before the patch is applied, giving the attacker a foothold.",
     "threats": ["T06"], "vulnerabilities": ["V01", "V02", "V33"],
     "controls": ["A.8.8", "A.8.9", "A.8.20"], "likelihood": 3,
     "consequence": {"financial": 3, "operational": 4, "legal": 3, "reputation": 3, "data": 4}},
    {"code": "RT05", "title": "Customer data exposed through misconfigured cloud storage", "category": "Data protection",
     "scenario": "A cloud storage bucket or share holding customer data is left publicly readable and is found by an outsider.",
     "threats": ["T12"], "vulnerabilities": ["V23", "V40"],
     "controls": ["A.5.23", "A.8.9", "A.5.12"], "likelihood": 3,
     "consequence": {"financial": 3, "operational": 1, "legal": 4, "reputation": 4, "data": 5}},
    {"code": "RT06", "title": "Departing employee copies confidential data", "category": "Data protection",
     "scenario": "An employee who is leaving downloads customer lists or internal documents to personal storage before their last day.",
     "threats": ["T09"], "vulnerabilities": ["V05", "V28", "V37"],
     "controls": ["A.5.18", "A.8.12", "A.6.5", "A.5.15"], "likelihood": 2,
     "consequence": {"financial": 3, "operational": 1, "legal": 4, "reputation": 4, "data": 4}},
    {"code": "RT07", "title": "Laptop with unencrypted data is lost or stolen", "category": "Data protection",
     "scenario": "A laptop or phone holding work data is lost or stolen while travelling; the disk is not encrypted.",
     "threats": ["T13"], "vulnerabilities": ["V08", "V24"],
     "controls": ["A.8.1", "A.8.24", "A.7.9"], "likelihood": 4,
     "consequence": {"financial": 1, "operational": 1, "legal": 3, "reputation": 2, "data": 3}},
    {"code": "RT08", "title": "Data centre outage from power or cooling failure", "category": "Availability",
     "scenario": "A power cut or cooling failure takes down the server room and critical systems are unavailable for hours.",
     "threats": ["T17", "T18"], "vulnerabilities": ["V19", "V57"],
     "controls": ["A.7.11", "A.8.14", "A.5.30"], "likelihood": 2,
     "consequence": {"financial": 3, "operational": 4, "legal": 1, "reputation": 2, "data": 1}},
    {"code": "RT09", "title": "Key cloud provider outage halts services", "category": "Third party",
     "scenario": "The cloud platform that hosts customer-facing services has a regional outage and there is no fallback.",
     "threats": ["T20"], "vulnerabilities": ["V59", "V60"],
     "controls": ["A.5.23", "A.5.30", "A.8.14"], "likelihood": 2,
     "consequence": {"financial": 3, "operational": 4, "legal": 2, "reputation": 3, "data": 1}},
    {"code": "RT10", "title": "Supplier breach exposes our data", "category": "Third party",
     "scenario": "A supplier that processes our data is breached and our customers' records are leaked.",
     "threats": ["T21"], "vulnerabilities": ["V38", "V39"],
     "controls": ["A.5.19", "A.5.20", "A.5.21", "A.5.22"], "likelihood": 3,
     "consequence": {"financial": 3, "operational": 2, "legal": 4, "reputation": 4, "data": 4}},
    {"code": "RT11", "title": "Compromised software update introduces malware", "category": "Third party",
     "scenario": "A trusted vendor's update channel is compromised and a malicious update is installed across our systems.",
     "threats": ["T22"], "vulnerabilities": ["V38", "V42"],
     "controls": ["A.5.21", "A.8.19", "A.8.32"], "likelihood": 2,
     "consequence": {"financial": 3, "operational": 4, "legal": 2, "reputation": 3, "data": 3}},
    {"code": "RT12", "title": "Privileged administrator account is misused", "category": "Insider",
     "scenario": "An administrator, or an attacker using an administrator's account, makes unauthorised changes or reads restricted data without being noticed.",
     "threats": ["T26", "T27"], "vulnerabilities": ["V06", "V30", "V43"],
     "controls": ["A.8.2", "A.5.3", "A.8.15", "A.8.16"], "likelihood": 2,
     "consequence": {"financial": 3, "operational": 4, "legal": 3, "reputation": 3, "data": 4}},
    {"code": "RT13", "title": "Former employee keeps access after leaving", "category": "Insider",
     "scenario": "Accounts of people who have left are not disabled and are later used to access systems.",
     "threats": ["T05"], "vulnerabilities": ["V07", "V36", "V37"],
     "controls": ["A.5.16", "A.5.18", "A.6.5"], "likelihood": 3,
     "consequence": {"financial": 2, "operational": 2, "legal": 3, "reputation": 2, "data": 3}},
    {"code": "RT14", "title": "Backups fail when a restore is needed", "category": "Availability",
     "scenario": "After data loss the team tries to restore and finds backups incomplete, corrupted or never tested.",
     "threats": ["T25"], "vulnerabilities": ["V17"],
     "controls": ["A.8.13", "A.5.30"], "likelihood": 3,
     "consequence": {"financial": 3, "operational": 4, "legal": 2, "reputation": 2, "data": 3}},
    {"code": "RT15", "title": "Web application breached through an injection flaw", "category": "Cyber attack",
     "scenario": "An attacker exploits an injection or access-control flaw in a customer-facing web application and extracts records.",
     "threats": ["T07"], "vulnerabilities": ["V20", "V21", "V42"],
     "controls": ["A.8.25", "A.8.26", "A.8.28", "A.8.29"], "likelihood": 3,
     "consequence": {"financial": 3, "operational": 3, "legal": 4, "reputation": 4, "data": 4}},
    {"code": "RT16", "title": "Denial-of-service attack takes the customer portal offline", "category": "Availability",
     "scenario": "A flood of traffic makes the customer portal unavailable for several hours.",
     "threats": ["T08"], "vulnerabilities": ["V19", "V29"],
     "controls": ["A.8.6", "A.8.14", "A.8.20"], "likelihood": 3,
     "consequence": {"financial": 3, "operational": 3, "legal": 1, "reputation": 3, "data": 1}},
    {"code": "RT17", "title": "Unauthorised change breaks production", "category": "Operations",
     "scenario": "A change is made directly in production without review or testing and causes an outage or data error.",
     "threats": ["T23"], "vulnerabilities": ["V32"],
     "controls": ["A.8.32", "A.8.31", "A.8.9"], "likelihood": 3,
     "consequence": {"financial": 2, "operational": 4, "legal": 1, "reputation": 2, "data": 2}},
    {"code": "RT18", "title": "Fire or flood destroys office equipment", "category": "Physical",
     "scenario": "A fire or flood at the main office destroys equipment and paper records.",
     "threats": ["T15", "T16"], "vulnerabilities": ["V56"],
     "controls": ["A.7.5", "A.7.8", "A.5.30"], "likelihood": 1,
     "consequence": {"financial": 4, "operational": 4, "legal": 1, "reputation": 2, "data": 2}},
    {"code": "RT19", "title": "Intruder gains access to the server room", "category": "Physical",
     "scenario": "Someone without authorisation enters the building and the server room and tampers with or removes equipment.",
     "threats": ["T14"], "vulnerabilities": ["V53", "V54", "V55"],
     "controls": ["A.7.1", "A.7.2", "A.7.4"], "likelihood": 2,
     "consequence": {"financial": 2, "operational": 3, "legal": 2, "reputation": 2, "data": 3}},
    {"code": "RT20", "title": "Staff send confidential data to the wrong recipient", "category": "Data protection",
     "scenario": "Confidential documents are emailed to the wrong person or shared through an open link.",
     "threats": ["T11"], "vulnerabilities": ["V28", "V40", "V47"],
     "controls": ["A.5.12", "A.5.14", "A.6.3", "A.8.12"], "likelihood": 4,
     "consequence": {"financial": 2, "operational": 1, "legal": 3, "reputation": 3, "data": 3}},
    {"code": "RT21", "title": "Regulatory breach from unmanaged legal requirements", "category": "Compliance",
     "scenario": "A new or changed legal requirement (for example data protection or sector regulation) is missed and the organisation falls out of compliance.",
     "threats": ["T29"], "vulnerabilities": ["V45", "V46"],
     "controls": ["A.5.31", "A.5.34", "A.5.36"], "likelihood": 2,
     "consequence": {"financial": 4, "operational": 1, "legal": 5, "reputation": 3, "data": 1}},
    {"code": "RT22", "title": "Loss of a key IT person disrupts operations", "category": "People",
     "scenario": "The only person who knows how a critical system works leaves or is unavailable and nobody else can run it.",
     "threats": ["T31"], "vulnerabilities": ["V50", "V51"],
     "controls": ["A.5.2", "A.5.37"], "likelihood": 3,
     "consequence": {"financial": 2, "operational": 3, "legal": 1, "reputation": 1, "data": 1}},
    {"code": "RT23", "title": "Encryption keys are exposed or lost", "category": "Cyber attack",
     "scenario": "Private keys or certificates are stored insecurely and are copied, or are lost so that encrypted data cannot be recovered.",
     "threats": ["T34"], "vulnerabilities": ["V26", "V27"],
     "controls": ["A.8.24", "A.5.15"], "likelihood": 1,
     "consequence": {"financial": 3, "operational": 3, "legal": 3, "reputation": 3, "data": 4}},
    {"code": "RT24", "title": "Confidential data pasted into public AI tools", "category": "Data protection",
     "scenario": "Staff paste customer or internal data into public chatbots or online tools that store and reuse it.",
     "threats": ["T39"], "vulnerabilities": ["V28", "V45", "V47"],
     "controls": ["A.5.10", "A.5.14", "A.6.3", "A.8.12"], "likelihood": 4,
     "consequence": {"financial": 2, "operational": 1, "legal": 3, "reputation": 3, "data": 3}},
    {"code": "RT25", "title": "Security incident goes unnoticed for weeks", "category": "Operations",
     "scenario": "An intrusion or malware infection is not detected because logs are incomplete or nobody reviews them, so the attacker stays for weeks.",
     "threats": ["T02", "T38"], "vulnerabilities": ["V15", "V16", "V34"],
     "controls": ["A.8.15", "A.8.16", "A.5.24", "A.5.25"], "likelihood": 3,
     "consequence": {"financial": 3, "operational": 3, "legal": 3, "reputation": 3, "data": 4}}
  ]
}
```

- [ ] **Step 2: Write the failing tests**

Change the `seeded` fixture in `backend/tests/conftest.py` (add `from assayr.risk.seed import ensure_methodology, ensure_risk_library` to the imports):
```python
@pytest.fixture
def seeded(db, settings):
    scope = ensure_default_scope(db, settings.org_name)
    seed_iso27001(db, scope)
    ensure_methodology(db, utcnow())
    ensure_risk_library(db)
    db.commit()
    return scope
```

`backend/tests/test_risk_library.py`:
```python
from sqlalchemy import func, select

from assayr.audit.models import AuditLog
from assayr.catalogue.models import Control
from assayr.db import utcnow
from assayr.risk.models import RiskTemplate, Threat, Vulnerability
from assayr.risk.seed import LibraryResult, ensure_methodology, ensure_risk_library
from tests.conftest import create_user, sign_in

DIMENSIONS = {"financial", "operational", "legal", "reputation", "data"}


def test_seeded_library_is_complete_and_consistent(db, seeded):
    assert db.scalar(select(func.count()).select_from(Threat)) == 40
    assert db.scalar(select(func.count()).select_from(Vulnerability)) == 60
    assert db.scalar(select(func.count()).select_from(RiskTemplate)) == 25
    threats = set(db.scalars(select(Threat.code)))
    vulnerabilities = set(db.scalars(select(Vulnerability.code)))
    controls = set(db.scalars(select(Control.code)))
    for template in db.scalars(select(RiskTemplate)):
        assert set(template.threat_codes) <= threats, template.code
        assert set(template.vulnerability_codes) <= vulnerabilities, template.code
        assert set(template.control_codes) <= controls, template.code
        assert set(template.consequence) == DIMENSIONS, template.code
        assert 1 <= template.likelihood <= 5


def test_seeding_twice_adds_nothing(db, seeded):
    assert ensure_risk_library(db) == LibraryResult()
    assert ensure_methodology(db, utcnow()).version_no == 1


def test_methodology_api(client, db, seeded):
    create_user(db, "viewer@acme.com", roles=(("viewer", None),))
    sign_in(client, "viewer@acme.com")
    body = client.get("/api/v1/risk-methodology").json()
    assert body["version_no"] == 1
    assert [b["key"] for b in body["bands"]] == ["very_low", "low", "medium", "high", "critical"]
    assert body["likelihood"][3]["label"] == "Likely"
    assert len(body["consequence"]["dimensions"]) == 5


def test_library_api_and_custom_entries(client, db, seeded):
    create_user(db, "sana@acme.com")
    sign_in(client, "sana@acme.com")
    library = client.get("/api/v1/risk-library").json()
    assert library["threats"][0]["code"] == "T01" and len(library["templates"]) == 25
    created = client.post("/api/v1/risk-library/threats", json={"name": "Drone surveillance", "category": "Physical"})
    assert created.status_code == 201
    assert (created.json()["code"], created.json()["is_custom"]) == ("T41", True)
    vulnerability = client.post(
        "/api/v1/risk-library/vulnerabilities", json={"name": "No CCTV on the loading bay", "category": "Physical"}
    ).json()
    assert vulnerability["code"] == "V61"
    assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "risk_library.add")) == 2


def test_only_risk_managers_extend_the_library(client, db, seeded):
    create_user(db, "viewer@acme.com", roles=(("viewer", None),))
    sign_in(client, "viewer@acme.com")
    response = client.post("/api/v1/risk-library/threats", json={"name": "x", "category": "y"})
    assert response.status_code == 403
```

Append to `backend/tests/test_cli.py`:
```python
def test_seed_loads_the_risk_library(cli_db):
    run("migrate")
    first = run("seed")
    assert first.exit_code == 0
    assert "Risk library: 40 threats, 60 vulnerabilities and 25 templates added." in first.output
    assert "Risk library: 0 threats, 0 vulnerabilities and 0 templates added." in run("seed").output
```

- [ ] **Step 3: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_risk_library.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'assayr.risk.seed'`.

- [ ] **Step 4: Implement seeding**

`backend/src/assayr/risk/seed.py`:
```python
"""Load the default risk methodology and the threat, vulnerability and template libraries (only adds what is missing)."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.risk.methodology import DEFAULT_METHODOLOGY, active_methodology
from assayr.risk.models import MethodologyVersion, RiskTemplate, Threat, Vulnerability

LIBRARY_PATH = Path(__file__).resolve().parent / "data" / "library.json"


@dataclass
class LibraryResult:
    threats: int = 0
    vulnerabilities: int = 0
    templates: int = 0


def ensure_methodology(db: Session, now: datetime) -> MethodologyVersion:
    current = active_methodology(db)
    if current is not None:
        return current
    version = MethodologyVersion(
        version_no=1, name=DEFAULT_METHODOLOGY["name"], definition=DEFAULT_METHODOLOGY, effective_from=now
    )
    db.add(version)
    db.flush()
    return version


def ensure_risk_library(db: Session) -> LibraryResult:
    data = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    result = LibraryResult()
    for model, key, counter in ((Threat, "threats", "threats"), (Vulnerability, "vulnerabilities", "vulnerabilities")):
        have = set(db.scalars(select(model.code)))
        for item in data[key]:
            if item["code"] not in have:
                db.add(
                    model(
                        code=item["code"],
                        name=item["name"],
                        category=item["category"],
                        description=item.get("description"),
                        is_custom=False,
                    )
                )
                setattr(result, counter, getattr(result, counter) + 1)
    have = set(db.scalars(select(RiskTemplate.code)))
    for item in data["templates"]:
        if item["code"] in have:
            continue
        db.add(
            RiskTemplate(
                code=item["code"],
                title=item["title"],
                scenario=item["scenario"],
                category=item["category"],
                threat_codes=item["threats"],
                vulnerability_codes=item["vulnerabilities"],
                control_codes=item["controls"],
                likelihood=item["likelihood"],
                consequence=item["consequence"],
            )
        )
        result.templates += 1
    db.flush()
    return result
```

In `backend/src/assayr/cli.py` add `from assayr.risk.seed import ensure_methodology, ensure_risk_library` and replace the body of `seed()`:
```python
    with _database().sessionmaker() as session:
        scope = ensure_default_scope(session, get_settings().org_name)
        result = seed_iso27001(session, scope)
        ensure_methodology(session, utcnow())
        library = ensure_risk_library(session)
        session.commit()
    typer.echo(
        f"Seed complete: {result.requirements_created} requirements and {result.controls_created} controls created."
    )
    typer.echo(
        f"Risk library: {library.threats} threats, {library.vulnerabilities} vulnerabilities "
        f"and {library.templates} templates added."
    )
```

- [ ] **Step 5: Implement the API**

`backend/src/assayr/risk/library_router.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.db import get_session
from assayr.identity.deps import actor_for, current_user, require
from assayr.identity.models import User
from assayr.identity.rbac import Perm
from assayr.risk.methodology import active_methodology
from assayr.risk.models import MethodologyVersion, RiskTemplate, Threat, Vulnerability

router = APIRouter(tags=["risk library"])


class MethodologyOut(BaseModel):
    version_no: int
    name: str
    likelihood: list[dict]
    consequence: dict
    bands: list[dict]


class LibraryItemOut(BaseModel):
    code: str
    name: str
    category: str
    description: str | None
    is_custom: bool


class TemplateOut(BaseModel):
    code: str
    title: str
    scenario: str
    category: str
    threat_codes: list[str]
    vulnerability_codes: list[str]
    control_codes: list[str]
    likelihood: int
    consequence: dict[str, int]


class LibraryOut(BaseModel):
    threats: list[LibraryItemOut]
    vulnerabilities: list[LibraryItemOut]
    templates: list[TemplateOut]


class LibraryItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=60)
    description: str | None = Field(None, max_length=2000)


def require_methodology(db: Session) -> MethodologyVersion:
    version = active_methodology(db)
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No risk methodology exists yet. Run `assayr seed`.")
    return version


@router.get("/risk-methodology", response_model=MethodologyOut)
def get_methodology(_grant=Depends(require(Perm.RISKS_READ)), db: Session = Depends(get_session)) -> MethodologyOut:
    version = require_methodology(db)
    definition = version.definition
    return MethodologyOut(
        version_no=version.version_no,
        name=version.name,
        likelihood=definition["likelihood"],
        consequence=definition["consequence"],
        bands=definition["bands"],
    )


@router.get("/risk-library", response_model=LibraryOut)
def get_library(_grant=Depends(require(Perm.RISKS_READ)), db: Session = Depends(get_session)) -> LibraryOut:
    return LibraryOut(
        threats=[LibraryItemOut.model_validate(t, from_attributes=True) for t in db.scalars(select(Threat).order_by(Threat.code))],
        vulnerabilities=[
            LibraryItemOut.model_validate(v, from_attributes=True)
            for v in db.scalars(select(Vulnerability).order_by(Vulnerability.code))
        ],
        templates=[
            TemplateOut.model_validate(t, from_attributes=True)
            for t in db.scalars(select(RiskTemplate).order_by(RiskTemplate.code))
        ],
    )


def _next_code(db: Session, model, prefix: str) -> str:
    numbers = [
        int(code[len(prefix) :])
        for code in db.scalars(select(model.code))
        if code.startswith(prefix) and code[len(prefix) :].isdigit()
    ]
    return f"{prefix}{max(numbers, default=0) + 1:02d}"


def _add(db: Session, request: Request, user: User, model, prefix: str, body: LibraryItemIn) -> LibraryItemOut:
    item = model(
        code=_next_code(db, model, prefix),
        name=body.name.strip(),
        category=body.category.strip(),
        description=body.description,
        is_custom=True,
    )
    db.add(item)
    db.flush()
    record(db, actor_for(request, user), "risk_library.add", model.__tablename__, item.code, diff={"name": item.name})
    db.commit()
    return LibraryItemOut.model_validate(item, from_attributes=True)


@router.post("/risk-library/threats", response_model=LibraryItemOut, status_code=status.HTTP_201_CREATED)
def add_threat(
    body: LibraryItemIn,
    request: Request,
    user: User = Depends(current_user),
    _grant=Depends(require(Perm.RISKS_WRITE)),
    db: Session = Depends(get_session),
) -> LibraryItemOut:
    return _add(db, request, user, Threat, "T", body)


@router.post("/risk-library/vulnerabilities", response_model=LibraryItemOut, status_code=status.HTTP_201_CREATED)
def add_vulnerability(
    body: LibraryItemIn,
    request: Request,
    user: User = Depends(current_user),
    _grant=Depends(require(Perm.RISKS_WRITE)),
    db: Session = Depends(get_session),
) -> LibraryItemOut:
    return _add(db, request, user, Vulnerability, "V", body)
```

In `backend/src/assayr/main.py` add `from assayr.risk.library_router import router as risk_library_router` and `app.include_router(risk_library_router, prefix="/api/v1")`.

- [ ] **Step 6: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest -W error`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(risk): threat, vulnerability and template libraries with seeding and API"
```

---

### Task 5: Asset inventory API

**Files:**
- Create: `backend/src/assayr/assets/schemas.py`, `backend/src/assayr/assets/router.py`
- Modify: `backend/src/assayr/main.py`
- Test: `backend/tests/test_assets_api.py`

**Interfaces:**
- Consumes: `Asset`, `ASSET_TYPES` (Task 2); `rights_for`, `has_perm` (Task 1); `resolve_scope`, `_like`, `FORBIDDEN` (`assayr.catalogue.router`); `OwnerOut` (`assayr.catalogue.schemas`).
- Produces: `check_active_user(db, user_id, label="Owner")` in `assayr.catalogue.access` (422 "`<label>` must be an active user."); `AssetOut {id, code, name, type, owner, classification, confidentiality, integrity, availability, criticality, location, description, lifecycle}`; `asset_out(asset) -> AssetOut`; `GET /api/v1/assets?q=&type=&include_retired=` ; `POST /api/v1/assets` (201); `PATCH /api/v1/assets/{asset_id}`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_assets_api.py`:
```python
from sqlalchemy import select

from assayr.audit.models import AuditLog
from tests.conftest import create_user, sign_in


def manager(client, db):
    user = create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")
    return user


def test_create_and_list_assets(client, db, seeded):
    manager(client, db)
    created = client.post(
        "/api/v1/assets",
        json={
            "name": "Core banking database",
            "type": "information",
            "classification": "restricted",
            "confidentiality": 5,
            "integrity": 5,
            "availability": 4,
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert (body["code"], body["criticality"], body["lifecycle"]) == ("AST-001", 5, "in_use")
    client.post("/api/v1/assets", json={"name": "Email", "type": "cloud_service"})
    assert [a["code"] for a in client.get("/api/v1/assets").json()] == ["AST-001", "AST-002"]
    assert [a["name"] for a in client.get("/api/v1/assets?q=bank").json()] == ["Core banking database"]
    assert [a["name"] for a in client.get("/api/v1/assets?type=cloud_service").json()] == ["Email"]


def test_retired_assets_are_hidden_unless_asked(client, db, seeded):
    manager(client, db)
    asset = client.post("/api/v1/assets", json={"name": "Old file server", "type": "server"}).json()
    client.patch(f"/api/v1/assets/{asset['id']}", json={"lifecycle": "retired"})
    assert client.get("/api/v1/assets").json() == []
    assert len(client.get("/api/v1/assets?include_retired=true").json()) == 1


def test_control_owner_edits_only_their_own_assets(client, db, seeded):
    owner = create_user(db, "bilal@acme.com", roles=(("control_owner", None),), full_name="Bilal Khan")
    boss = manager(client, db)
    mine = client.post(
        "/api/v1/assets", json={"name": "Laptop fleet", "type": "endpoint", "owner_id": str(owner.id)}
    ).json()
    other = client.post("/api/v1/assets", json={"name": "Firewall", "type": "network_device"}).json()
    sign_in(client, "bilal@acme.com")
    assert client.patch(f"/api/v1/assets/{mine['id']}", json={"location": "Head office"}).json()["location"] == (
        "Head office"
    )
    assert client.patch(f"/api/v1/assets/{other['id']}", json={"location": "x"}).status_code == 403
    response = client.patch(f"/api/v1/assets/{mine['id']}", json={"owner_id": str(boss.id)})
    assert response.status_code == 403
    assert response.json() == {"detail": "Only an ISMS manager can change the owner."}
    assert client.post("/api/v1/assets", json={"name": "x", "type": "server"}).status_code == 403


def test_owner_must_be_active_and_values_valid(client, db, seeded):
    gone = create_user(db, "gone@acme.com", active=False)
    manager(client, db)
    response = client.post("/api/v1/assets", json={"name": "x", "type": "server", "owner_id": str(gone.id)})
    assert response.status_code == 422 and response.json() == {"detail": "Owner must be an active user."}
    assert client.post("/api/v1/assets", json={"name": "x", "type": "server", "confidentiality": 6}).status_code == 422
    assert client.post("/api/v1/assets", json={"name": "x", "type": "spaceship"}).status_code == 422
    asset = client.post("/api/v1/assets", json={"name": "x", "type": "server"}).json()
    response = client.patch(f"/api/v1/assets/{asset['id']}", json={"name": None})
    assert response.status_code == 422 and response.json() == {"detail": "Name can't be empty."}


def test_asset_changes_are_audited(client, db, seeded):
    manager(client, db)
    asset = client.post("/api/v1/assets", json={"name": "HR system", "type": "application"}).json()
    client.patch(f"/api/v1/assets/{asset['id']}", json={"classification": "confidential"})
    actions = [e.action for e in db.scalars(select(AuditLog).where(AuditLog.entity_type == "asset"))]
    assert actions == ["asset.create", "asset.update"]
    update = db.scalar(select(AuditLog).where(AuditLog.action == "asset.update"))
    assert update.diff == {"classification": ["internal", "confidential"]}
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_assets_api.py`
Expected: FAIL — 404/405 (routes don't exist).

- [ ] **Step 3: Implement**

Append to `backend/src/assayr/catalogue/access.py` (add imports `from fastapi import HTTPException, status` and `from sqlalchemy.orm import Session`):
```python
def check_active_user(db: Session, user_id: uuid.UUID | None, label: str = "Owner") -> None:
    """Owners and assignees must be people who can still sign in."""
    if user_id is None:
        return
    person = db.get(User, user_id)
    if person is None or not person.is_active:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{label} must be an active user.")
```

`backend/src/assayr/assets/schemas.py`:
```python
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from assayr.assets.models import Asset
from assayr.catalogue.schemas import OwnerOut

AssetType = Literal[
    "information",
    "application",
    "server",
    "endpoint",
    "network_device",
    "cloud_service",
    "facility",
    "people",
    "supplier_service",
]
Classification = Literal["public", "internal", "confidential", "restricted"]
Lifecycle = Literal["planned", "in_use", "retired"]
Rating = Annotated[int, Field(ge=1, le=5)]


class AssetIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: AssetType
    owner_id: uuid.UUID | None = None
    classification: Classification = "internal"
    confidentiality: Rating = 3
    integrity: Rating = 3
    availability: Rating = 3
    location: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=5000)
    lifecycle: Lifecycle = "in_use"


class AssetUpdateIn(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    type: AssetType | None = None
    owner_id: uuid.UUID | None = None
    classification: Classification | None = None
    confidentiality: Rating | None = None
    integrity: Rating | None = None
    availability: Rating | None = None
    location: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=5000)
    lifecycle: Lifecycle | None = None


class AssetOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    type: str
    owner: OwnerOut | None
    classification: str
    confidentiality: int
    integrity: int
    availability: int
    criticality: int
    location: str | None
    description: str | None
    lifecycle: str


def asset_out(asset: Asset) -> AssetOut:
    return AssetOut(
        id=asset.id,
        code=asset.code,
        name=asset.name,
        type=asset.type,
        owner=OwnerOut(id=asset.owner.id, full_name=asset.owner.full_name) if asset.owner else None,
        classification=asset.classification,
        confidentiality=asset.confidentiality,
        integrity=asset.integrity,
        availability=asset.availability,
        criticality=max(asset.confidentiality, asset.integrity, asset.availability),
        location=asset.location,
        description=asset.description,
        lifecycle=asset.lifecycle,
    )
```

`backend/src/assayr/assets/router.py`:
```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from assayr.assets.models import Asset
from assayr.assets.schemas import AssetIn, AssetOut, AssetUpdateIn, asset_out
from assayr.audit.service import record
from assayr.catalogue.access import check_active_user, has_perm, rights_for
from assayr.catalogue.router import FORBIDDEN, _like, resolve_scope
from assayr.db import get_session
from assayr.identity.deps import actor_for, current_user, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm

router = APIRouter(tags=["assets"])
EDITABLE = (
    "name",
    "type",
    "classification",
    "confidentiality",
    "integrity",
    "availability",
    "location",
    "description",
    "lifecycle",
)
REQUIRED = {"name", "type", "classification", "confidentiality", "integrity", "availability", "lifecycle"}


@router.get("/assets", response_model=list[AssetOut])
def list_assets(
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
    q: str | None = Query(None, max_length=100),
    type_: str | None = Query(None, alias="type", max_length=30),
    include_retired: bool = False,
) -> list[AssetOut]:
    scope = resolve_scope(db, scope_id, grant)
    stmt = select(Asset).where(Asset.scope_id == scope.id)
    if not include_retired:
        stmt = stmt.where(Asset.lifecycle != "retired")
    if type_:
        stmt = stmt.where(Asset.type == type_)
    if q and q.strip():
        like = _like(q.strip())
        stmt = stmt.where(
            or_(func.lower(Asset.name).like(like, escape="\\"), func.lower(Asset.code).like(like, escape="\\"))
        )
    return [asset_out(a) for a in db.scalars(stmt.order_by(Asset.seq)).unique()]


@router.post("/assets", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
def create_asset(
    body: AssetIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> AssetOut:
    scope = resolve_scope(db, scope_id, grant)
    if not has_perm(user, scope.id, Perm.ASSETS_WRITE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    check_active_user(db, body.owner_id)
    seq = (db.scalar(select(func.max(Asset.seq)).where(Asset.scope_id == scope.id)) or 0) + 1
    asset = Asset(scope_id=scope.id, code=f"AST-{seq:03d}", seq=seq, **body.model_dump())
    db.add(asset)
    db.flush()
    record(
        db, actor_for(request, user), "asset.create", "asset", asset.code, diff={"name": asset.name, "type": asset.type}
    )
    db.commit()
    db.refresh(asset)
    return asset_out(asset)


@router.patch("/assets/{asset_id}", response_model=AssetOut)
def update_asset(
    asset_id: uuid.UUID,
    body: AssetUpdateIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
) -> AssetOut:
    asset = db.get(Asset, asset_id)
    if asset is None or not grant.allows(asset.scope_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found.")
    rights = rights_for(user, asset.scope_id, asset.owner_id, Perm.ASSETS_WRITE, Perm.ASSETS_WRITE_OWN)
    if not rights.any:
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    fields = body.model_fields_set
    if "owner_id" in fields and not rights.all:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an ISMS manager can change the owner.")
    diff: dict[str, list] = {}
    if "owner_id" in fields and body.owner_id != asset.owner_id:
        check_active_user(db, body.owner_id)
        diff["owner_id"] = [
            str(asset.owner_id) if asset.owner_id else None,
            str(body.owner_id) if body.owner_id else None,
        ]
        asset.owner_id = body.owner_id
    for name in EDITABLE:
        if name not in fields:
            continue
        value = getattr(body, name)
        if value is None and name in REQUIRED:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{name.capitalize()} can't be empty.")
        if value != getattr(asset, name):
            diff[name] = [getattr(asset, name), value]
            setattr(asset, name, value)
    if diff:
        record(db, actor_for(request, user), "asset.update", "asset", asset.code, diff=diff)
        db.commit()
    db.refresh(asset)
    return asset_out(asset)
```

In `backend/src/assayr/main.py` add `from assayr.assets.router import router as assets_router` and `app.include_router(assets_router, prefix="/api/v1")`.

- [ ] **Step 4: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest -W error`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(assets): minimal asset inventory API"
```

---
### Task 6: Risk register — create, read, update and link controls

**Files:**
- Create: `backend/src/assayr/risk/schemas.py`, `backend/src/assayr/risk/service.py`, `backend/src/assayr/risk/router.py`, `backend/tests/risk_helpers.py`
- Modify: `backend/src/assayr/main.py`
- Test: `backend/tests/test_risk_api.py`

**Interfaces:**
- Consumes: models (Task 2); `band_for`, `overall_consequence`, `suggest_current`, `authority_allows` (Task 3); `require_methodology` (Task 4); `rights_for`, `has_perm`, `check_active_user` (Tasks 1, 5); `resolve_scope`, `_like`, `FORBIDDEN` (catalogue router); `OwnerOut`.
- Produces (schemas): `LevelOut {likelihood, consequence, score, band, band_label}`, `level_out(definition, likelihood, consequence) -> LevelOut | None`, `NamedRef`, `AssetRef`, `RiskControlOut {code, title, status, axis}`, `ProgressOut {done, total}`, `TaskOut {id, title, assignee, due, status, done_at}`, `task_out(task)`, `AssessmentOut {id, likelihood, consequence, inherent, suggested, current, current_reason, target, rationale, finalized_at, assessed_by, methodology_version}`, `AcceptanceOut {band, score, authority, statement, accepted_by, accepted_at, expires_at}`, `TreatmentOut {option, note, budget, due}`, `RiskRowOut {id, code, title, category, approach, owner, status, inherent, current, target, treatment_option, progress, review_due, acceptance_expires}`, `RiskDetailOut` (row + `description, template_code, threats, vulnerabilities, assets, controls, draft, latest, history, treatment, actions, acceptance, required_authority, can_accept, can_edit, closed_at, close_reason`); inputs `RiskCreateIn`, `RiskUpdateIn`, `ControlLinksIn`, `AssessmentIn`, `TreatmentIn`, `ActionIn`, `AcceptIn`, `CloseIn`, `SnapshotIn`.
- Produces (service): `next_risk_code(db, scope_id) -> (seq, code)`, `draft_assessment(db, risk)`, `latest_assessment(db, risk)`, `finalized_assessments(db, risk)`, `risk_actions(db, risk) -> list[Task]`, `current_acceptance(db, risk)`, `definition_of(db, assessment) -> dict`, `control_effects(risk)`, `inherent_of(definition, assessment)`, `suggested_of(definition, risk, assessment)`, `derive_status(*, closed, has_final, has_draft, review_overdue, accepted, option, actions) -> str`, `refresh_risk(db, risk, now) -> str`, `refresh_scope_risks(db, scope_id, now)`, `held_authority(user, scope_id, is_owner) -> str | None`, `open_actions(actions) -> bool`, `risk_row(db, risk)`, `risk_detail(db, risk, user)`.
- Produces (routes): `GET /api/v1/risks?status=&band=&owner=&q=&include_closed=`, `POST /api/v1/risks` (201), `GET /api/v1/risks/{code}`, `PATCH /api/v1/risks/{code}`, `PUT /api/v1/risks/{code}/controls`; router helpers `load_risk(db, grant, scope_id, code)`, `require_edit(user, risk) -> EditRights`, `require_open(risk)`. Test helper `new_risk(client, **body) -> dict`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/risk_helpers.py`:
```python
"""Build risks through the API in tests."""


def new_risk(client, **body) -> dict:
    payload = {"title": "Test risk", **body}
    response = client.post("/api/v1/risks", json=payload)
    assert response.status_code == 201, response.text
    return response.json()
```

`backend/tests/test_risk_api.py`:
```python
from sqlalchemy import select

from assayr.audit.models import AuditLog
from assayr.catalogue.models import Control
from tests.conftest import create_user, sign_in
from tests.risk_helpers import new_risk


def manager(client, db):
    user = create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")
    return user


def test_create_a_blank_risk(client, db, seeded):
    boss = manager(client, db)
    risk = new_risk(client, title="Ransomware encrypts file servers", owner_id=str(boss.id))
    assert (risk["code"], risk["status"], risk["owner"]["full_name"]) == ("R-001", "draft", "Sana Malik")
    assert risk["draft"]["likelihood"] is None and risk["latest"] is None and risk["can_edit"] is True
    assert [r["code"] for r in client.get("/api/v1/risks").json()] == ["R-001"]
    entry = db.scalar(select(AuditLog).where(AuditLog.action == "risk.create"))
    assert entry.diff == {"title": "Ransomware encrypts file servers", "template": None}


def test_create_from_a_template(client, db, seeded):
    manager(client, db)
    risk = client.post("/api/v1/risks", json={"template_code": "RT01"}).json()
    assert (risk["title"], risk["template_code"], risk["category"]) == (
        "Ransomware encrypts file servers",
        "RT01",
        "Cyber attack",
    )
    assert [t["code"] for t in risk["threats"]] == ["T01"]
    assert [c["code"] for c in risk["controls"]] == ["A.6.3", "A.8.7", "A.8.8", "A.8.13", "A.8.22"]
    assert risk["draft"]["likelihood"] == 3
    assert risk["draft"]["inherent"] == {
        "likelihood": 3,
        "consequence": 5,
        "score": 15,
        "band": "high",
        "band_label": "High",
    }
    assert risk["inherent"]["score"] == 15
    assert client.post("/api/v1/risks", json={"title": "Another"}).json()["code"] == "R-002"


def test_title_or_template_is_required_and_the_template_must_exist(client, db, seeded):
    manager(client, db)
    assert client.post("/api/v1/risks", json={}).status_code == 422
    response = client.post("/api/v1/risks", json={"template_code": "RT99"})
    assert response.status_code == 404 and response.json() == {"detail": "Risk template not found."}


def test_update_scenario_threats_and_assets(client, db, seeded):
    manager(client, db)
    asset = client.post("/api/v1/assets", json={"name": "File server", "type": "server"}).json()
    risk = new_risk(client)
    body = client.patch(
        f"/api/v1/risks/{risk['code']}",
        json={
            "title": "Ransomware",
            "approach": "asset",
            "threat_codes": ["T02", "T01"],
            "vulnerability_codes": ["V17"],
            "asset_ids": [asset["id"]],
        },
    ).json()
    assert (body["title"], body["approach"]) == ("Ransomware", "asset")
    assert [t["code"] for t in body["threats"]] == ["T01", "T02"]
    assert [v["code"] for v in body["vulnerabilities"]] == ["V17"]
    assert [a["code"] for a in body["assets"]] == ["AST-001"]
    response = client.patch(f"/api/v1/risks/{risk['code']}", json={"threat_codes": ["T99"]})
    assert response.status_code == 422 and response.json() == {"detail": "Unknown threat: T99."}


def test_linking_controls_replaces_the_set(client, db, seeded):
    manager(client, db)
    url = f"/api/v1/risks/{new_risk(client)['code']}/controls"
    body = client.put(url, json={"links": [{"code": "A.8.13"}, {"code": "A.8.7", "axis": "consequence"}]}).json()
    assert [(c["code"], c["axis"], c["status"]) for c in body["controls"]] == [
        ("A.8.7", "consequence", "not_started"),
        ("A.8.13", "likelihood", "not_started"),
    ]
    body = client.put(url, json={"links": [{"code": "A.8.7"}]}).json()
    assert [(c["code"], c["axis"]) for c in body["controls"]] == [("A.8.7", "likelihood")]
    response = client.put(url, json={"links": [{"code": "A.9.99"}]})
    assert response.status_code == 404 and response.json() == {"detail": "Control A.9.99 not found."}
    response = client.put(url, json={"links": [{"code": "A.8.7"}, {"code": "A.8.7"}]})
    assert response.status_code == 422 and response.json() == {"detail": "Each control can be linked once."}


def test_excluded_controls_cannot_be_linked(client, db, seeded):
    manager(client, db)
    control = db.scalar(select(Control).where(Control.code == "A.8.30"))
    control.applicable, control.exclusion_reason = False, "No outsourced development"
    db.commit()
    response = client.put(
        f"/api/v1/risks/{new_risk(client)['code']}/controls", json={"links": [{"code": "A.8.30"}]}
    )
    assert response.status_code == 409
    assert response.json() == {
        "detail": "A.8.30 is excluded in the Statement of Applicability. Include it before linking it to a risk."
    }


def test_risk_owner_edits_only_their_own_risks(client, db, seeded):
    owner = create_user(db, "bilal@acme.com", roles=(("risk_owner", None),), full_name="Bilal Khan")
    boss = manager(client, db)
    mine = new_risk(client, title="Mine", owner_id=str(owner.id))
    theirs = new_risk(client, title="Theirs")
    sign_in(client, "bilal@acme.com")
    assert client.patch(f"/api/v1/risks/{mine['code']}", json={"description": "Updated"}).status_code == 200
    assert client.patch(f"/api/v1/risks/{theirs['code']}", json={"description": "x"}).status_code == 403
    response = client.patch(f"/api/v1/risks/{mine['code']}", json={"owner_id": str(boss.id)})
    assert response.status_code == 403
    assert response.json() == {"detail": "Only an ISMS manager can change the owner."}
    assert client.post("/api/v1/risks", json={"title": "New"}).status_code == 403
    assert client.get(f"/api/v1/risks/{theirs['code']}").json()["can_edit"] is False


def test_list_filters_and_read_only_roles(client, db, seeded):
    boss = manager(client, db)
    new_risk(client, title="Ransomware", owner_id=str(boss.id))
    new_risk(client, title="Flood")
    assert [r["title"] for r in client.get("/api/v1/risks?owner=me").json()] == ["Ransomware"]
    assert [r["title"] for r in client.get("/api/v1/risks?q=flo").json()] == ["Flood"]
    assert len(client.get("/api/v1/risks?status=draft").json()) == 2
    create_user(db, "viewer@acme.com", roles=(("viewer", None),))
    sign_in(client, "viewer@acme.com")
    assert len(client.get("/api/v1/risks").json()) == 2
    assert client.post("/api/v1/risks", json={"title": "x"}).status_code == 403
    assert client.get("/api/v1/risks/R-404").status_code == 404
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_risk_api.py`
Expected: FAIL — 404/405 responses (routes don't exist).

- [ ] **Step 3: Implement the schemas**

`backend/src/assayr/risk/schemas.py`:
```python
import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from assayr.catalogue.schemas import OwnerOut
from assayr.risk.methodology import band_for

Approach = Literal["event", "asset"]
Axis = Literal["likelihood", "consequence"]
TreatmentOption = Literal["modify", "retain", "avoid", "share"]


class LevelOut(BaseModel):
    likelihood: int
    consequence: int
    score: int
    band: str
    band_label: str


def level_out(definition: dict | None, likelihood: int | None, consequence: int | None) -> LevelOut | None:
    if definition is None or likelihood is None or consequence is None:
        return None
    band = band_for(definition, likelihood, consequence)
    return LevelOut(
        likelihood=likelihood,
        consequence=consequence,
        score=likelihood * consequence,
        band=band["key"],
        band_label=band["label"],
    )


class NamedRef(BaseModel):
    code: str
    name: str


class AssetRef(BaseModel):
    id: uuid.UUID
    code: str
    name: str


class RiskControlOut(BaseModel):
    code: str
    title: str
    status: str
    axis: str


class ProgressOut(BaseModel):
    done: int
    total: int


class TaskOut(BaseModel):
    id: uuid.UUID
    title: str
    assignee: OwnerOut | None
    due: date | None
    status: str
    done_at: datetime | None


def task_out(task) -> TaskOut:
    return TaskOut(
        id=task.id,
        title=task.title,
        assignee=OwnerOut(id=task.assignee.id, full_name=task.assignee.full_name) if task.assignee else None,
        due=task.due,
        status=task.status,
        done_at=task.done_at,
    )


class AssessmentOut(BaseModel):
    id: uuid.UUID
    likelihood: int | None
    consequence: dict[str, int]
    inherent: LevelOut | None
    suggested: LevelOut | None
    current: LevelOut | None
    current_reason: str | None
    target: LevelOut | None
    rationale: str | None
    finalized_at: datetime | None
    assessed_by: str | None
    methodology_version: int


class AcceptanceOut(BaseModel):
    band: str
    score: int
    authority: str
    statement: str
    accepted_by: str | None
    accepted_at: datetime
    expires_at: datetime


class TreatmentOut(BaseModel):
    option: str | None
    note: str | None
    budget: str | None
    due: date | None


class RiskRowOut(BaseModel):
    id: uuid.UUID
    code: str
    title: str
    category: str | None
    approach: str
    owner: OwnerOut | None
    status: str
    inherent: LevelOut | None
    current: LevelOut | None
    target: LevelOut | None
    treatment_option: str | None
    progress: ProgressOut
    review_due: date | None
    acceptance_expires: datetime | None


class RiskDetailOut(RiskRowOut):
    description: str | None
    template_code: str | None
    threats: list[NamedRef]
    vulnerabilities: list[NamedRef]
    assets: list[AssetRef]
    controls: list[RiskControlOut]
    draft: AssessmentOut | None
    latest: AssessmentOut | None
    history: list[AssessmentOut]
    treatment: TreatmentOut
    actions: list[TaskOut]
    acceptance: AcceptanceOut | None
    required_authority: str | None
    can_accept: bool
    can_edit: bool
    closed_at: datetime | None
    close_reason: str | None


class RiskCreateIn(BaseModel):
    template_code: str | None = Field(None, max_length=20)
    title: str | None = Field(None, min_length=1, max_length=300)
    description: str | None = Field(None, max_length=10000)
    category: str | None = Field(None, max_length=60)
    approach: Approach = "event"
    owner_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _title_or_template(self):
        if not self.title and not self.template_code:
            raise ValueError("Give a title or choose a template.")
        return self


class RiskUpdateIn(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=300)
    description: str | None = Field(None, max_length=10000)
    category: str | None = Field(None, max_length=60)
    approach: Approach | None = None
    owner_id: uuid.UUID | None = None
    threat_codes: list[str] | None = Field(None, max_length=100)
    vulnerability_codes: list[str] | None = Field(None, max_length=100)
    asset_ids: list[uuid.UUID] | None = Field(None, max_length=200)


class ControlLinkIn(BaseModel):
    code: str = Field(max_length=20)
    axis: Axis = "likelihood"


class ControlLinksIn(BaseModel):
    links: list[ControlLinkIn] = Field(max_length=100)


class AssessmentIn(BaseModel):
    likelihood: int | None = None
    consequence: dict[str, int] | None = None
    current_l: int | None = None
    current_c: int | None = None
    current_reason: str | None = Field(None, max_length=2000)
    target_l: int | None = None
    target_c: int | None = None
    rationale: str | None = Field(None, max_length=5000)


class TreatmentIn(BaseModel):
    option: TreatmentOption
    note: str | None = Field(None, max_length=5000)
    budget: str | None = Field(None, max_length=100)
    due: date | None = None


class ActionIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    assignee_id: uuid.UUID | None = None
    due: date | None = None


class AcceptIn(BaseModel):
    statement: str = Field(min_length=1, max_length=2000)


class CloseIn(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class SnapshotIn(BaseModel):
    label: str = Field(min_length=1, max_length=200)
```

- [ ] **Step 4: Implement the service**

`backend/src/assayr/risk/service.py`:
```python
"""Risk register logic: codes, assessments, derived status and the API views (vault: FR-06, Risk Methodology)."""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from assayr.catalogue.access import has_perm, rights_for
from assayr.catalogue.schemas import OwnerOut
from assayr.identity.models import User
from assayr.identity.rbac import Perm
from assayr.risk.methodology import authority_allows, band_for, overall_consequence, suggest_current
from assayr.risk.models import MethodologyVersion, Risk, RiskAcceptance, RiskAssessment
from assayr.risk.schemas import (
    AcceptanceOut,
    AssessmentOut,
    AssetRef,
    NamedRef,
    ProgressOut,
    RiskControlOut,
    RiskDetailOut,
    RiskRowOut,
    TreatmentOut,
    level_out,
    task_out,
)
from assayr.tasks.models import Task


def next_risk_code(db: Session, scope_id: uuid.UUID) -> tuple[int, str]:
    seq = (db.scalar(select(func.max(Risk.seq)).where(Risk.scope_id == scope_id)) or 0) + 1
    return seq, f"R-{seq:03d}"


def draft_assessment(db: Session, risk: Risk) -> RiskAssessment | None:
    return db.scalar(
        select(RiskAssessment)
        .where(RiskAssessment.risk_id == risk.id, RiskAssessment.finalized_at.is_(None))
        .order_by(RiskAssessment.created_at.desc())
        .limit(1)
    )


def finalized_assessments(db: Session, risk: Risk) -> list[RiskAssessment]:
    return list(
        db.scalars(
            select(RiskAssessment)
            .where(RiskAssessment.risk_id == risk.id, RiskAssessment.finalized_at.is_not(None))
            .order_by(RiskAssessment.finalized_at.desc())
        )
    )


def latest_assessment(db: Session, risk: Risk) -> RiskAssessment | None:
    return db.scalar(
        select(RiskAssessment)
        .where(RiskAssessment.risk_id == risk.id, RiskAssessment.finalized_at.is_not(None))
        .order_by(RiskAssessment.finalized_at.desc())
        .limit(1)
    )


def risk_actions(db: Session, risk: Risk) -> list[Task]:
    return list(
        db.scalars(
            select(Task).where(Task.entity_type == "risk", Task.entity_id == str(risk.id)).order_by(Task.created_at)
        ).unique()
    )


def current_acceptance(db: Session, risk: Risk) -> RiskAcceptance | None:
    return db.scalar(
        select(RiskAcceptance)
        .where(RiskAcceptance.risk_id == risk.id)
        .order_by(RiskAcceptance.accepted_at.desc())
        .limit(1)
    )


def definition_of(db: Session, assessment: RiskAssessment) -> dict:
    return db.get(MethodologyVersion, assessment.methodology_version_id).definition


def control_effects(risk: Risk) -> list[tuple[str, str]]:
    return [(link.axis, link.control.status) for link in risk.control_links]


def inherent_of(definition: dict, assessment: RiskAssessment | None) -> tuple[int, int] | None:
    if assessment is None or assessment.likelihood is None:
        return None
    consequence = overall_consequence(definition, assessment.consequence)
    return None if consequence is None else (assessment.likelihood, consequence)


def suggested_of(definition: dict, risk: Risk, assessment: RiskAssessment | None) -> tuple[int, int] | None:
    """Frozen at finalization; worked out live from the linked controls while the assessment is open."""
    if assessment is None:
        return None
    if assessment.finalized_at is not None and assessment.suggested:
        return assessment.suggested["likelihood"], assessment.suggested["consequence"]
    inherent = inherent_of(definition, assessment)
    return None if inherent is None else suggest_current(definition, *inherent, control_effects(risk))


def derive_status(
    *,
    closed: bool,
    has_final: bool,
    has_draft: bool,
    review_overdue: bool,
    accepted: bool,
    option: str | None,
    actions: list[str],
) -> str:
    """Risk status from facts, first match wins (vault: State Machines, Risk)."""
    if closed:
        return "closed"
    if not has_final:
        return "draft"
    if has_draft:
        return "reassessing"
    if review_overdue:
        return "review_due"
    if accepted:
        return "accepted"
    if option in ("retain", "share"):
        return "treated"
    if option == "modify":
        live = [s for s in actions if s != "cancelled"]
        if live and all(s == "done" for s in live):
            return "treated"
        if any(s in ("in_progress", "blocked", "done") for s in live):
            return "in_treatment"
        return "treatment_planned"
    return "assessed"


def _acceptance_state(
    acceptance: RiskAcceptance | None, latest: RiskAssessment | None, now: datetime
) -> tuple[bool, bool]:
    """(accepted now, acceptance lapsed) — only an acceptance of the latest assessment counts."""
    if acceptance is None or latest is None or acceptance.assessment_id != latest.id:
        return False, False
    return acceptance.expires_at > now, acceptance.expires_at <= now


def refresh_risk(db: Session, risk: Risk, now: datetime) -> str:
    latest = latest_assessment(db, risk)
    accepted, lapsed = _acceptance_state(current_acceptance(db, risk), latest, now)
    overdue = lapsed or (risk.review_due is not None and now.date() > risk.review_due)
    risk.status = derive_status(
        closed=risk.closed_at is not None,
        has_final=latest is not None,
        has_draft=draft_assessment(db, risk) is not None,
        review_overdue=overdue,
        accepted=accepted,
        option=risk.treatment_option,
        actions=[t.status for t in risk_actions(db, risk)],
    )
    return risk.status


def refresh_scope_risks(db: Session, scope_id: uuid.UUID, now: datetime) -> None:
    for risk in db.scalars(select(Risk).where(Risk.scope_id == scope_id, Risk.closed_at.is_(None))).unique():
        refresh_risk(db, risk, now)


def held_authority(user: User, scope_id: uuid.UUID, is_owner: bool) -> str | None:
    if has_perm(user, scope_id, Perm.RISKS_ACCEPT_CRITICAL):
        return "executive"
    if has_perm(user, scope_id, Perm.RISKS_ACCEPT_HIGH):
        return "isms_manager"
    if is_owner and has_perm(user, scope_id, Perm.RISKS_ACCEPT_MEDIUM_OWN):
        return "risk_owner"
    return None


def open_actions(actions: list[Task]) -> bool:
    return any(t.status not in ("done", "cancelled") for t in actions)


def _owner(risk: Risk) -> OwnerOut | None:
    return OwnerOut(id=risk.owner.id, full_name=risk.owner.full_name) if risk.owner else None


def _name(db: Session, user_id: uuid.UUID | None) -> str | None:
    person = db.get(User, user_id) if user_id else None
    return person.full_name if person else None


def assessment_out(db: Session, risk: Risk, assessment: RiskAssessment) -> AssessmentOut:
    version = db.get(MethodologyVersion, assessment.methodology_version_id)
    definition = version.definition
    inherent = inherent_of(definition, assessment)
    suggested = suggested_of(definition, risk, assessment)
    return AssessmentOut(
        id=assessment.id,
        likelihood=assessment.likelihood,
        consequence=dict(assessment.consequence or {}),
        inherent=level_out(definition, *inherent) if inherent else None,
        suggested=level_out(definition, *suggested) if suggested else None,
        current=level_out(definition, assessment.current_l, assessment.current_c),
        current_reason=assessment.current_reason,
        target=level_out(definition, assessment.target_l, assessment.target_c),
        rationale=assessment.rationale,
        finalized_at=assessment.finalized_at,
        assessed_by=_name(db, assessment.assessed_by_id),
        methodology_version=version.version_no,
    )


def risk_row(db: Session, risk: Risk) -> RiskRowOut:
    latest = latest_assessment(db, risk)
    shown = latest or draft_assessment(db, risk)
    definition = definition_of(db, shown) if shown else None
    inherent = inherent_of(definition, shown) if shown else None
    actions = [t for t in risk_actions(db, risk) if t.status != "cancelled"]
    acceptance = current_acceptance(db, risk)
    accepted_latest = acceptance is not None and latest is not None and acceptance.assessment_id == latest.id
    return RiskRowOut(
        id=risk.id,
        code=risk.code,
        title=risk.title,
        category=risk.category,
        approach=risk.approach,
        owner=_owner(risk),
        status=risk.status,
        inherent=level_out(definition, *inherent) if inherent else None,
        current=level_out(definition, latest.current_l, latest.current_c) if latest else None,
        target=level_out(definition, latest.target_l, latest.target_c) if latest else None,
        treatment_option=risk.treatment_option,
        progress=ProgressOut(done=sum(t.status == "done" for t in actions), total=len(actions)),
        review_due=risk.review_due,
        acceptance_expires=acceptance.expires_at if accepted_latest else None,
    )


def _acceptance_out(db: Session, acceptance: RiskAcceptance) -> AcceptanceOut:
    return AcceptanceOut(
        band=acceptance.band,
        score=acceptance.score,
        authority=acceptance.authority,
        statement=acceptance.statement,
        accepted_by=_name(db, acceptance.accepted_by_id),
        accepted_at=acceptance.accepted_at,
        expires_at=acceptance.expires_at,
    )


def risk_detail(db: Session, risk: Risk, user: User) -> RiskDetailOut:
    row = risk_row(db, risk)
    latest = latest_assessment(db, risk)
    draft = draft_assessment(db, risk)
    actions = risk_actions(db, risk)
    acceptance = current_acceptance(db, risk)
    rights = rights_for(user, risk.scope_id, risk.owner_id, Perm.RISKS_WRITE, Perm.RISKS_WRITE_OWN)
    required = None
    can_accept = False
    if latest is not None and risk.closed_at is None:
        required = band_for(definition_of(db, latest), latest.current_l, latest.current_c)["authority"]
        held = held_authority(user, risk.scope_id, risk.owner_id == user.id)
        ready = (
            draft is None
            and risk.status != "accepted"
            and not (risk.treatment_option == "modify" and open_actions(actions))
        )
        can_accept = ready and authority_allows(held, required)
    links = sorted(risk.control_links, key=lambda link: link.control.sort_order)
    accepted_latest = acceptance is not None and latest is not None and acceptance.assessment_id == latest.id
    return RiskDetailOut(
        **row.model_dump(),
        description=risk.description,
        template_code=risk.template_code,
        threats=[NamedRef(code=t.code, name=t.name) for t in risk.threats],
        vulnerabilities=[NamedRef(code=v.code, name=v.name) for v in risk.vulnerabilities],
        assets=[AssetRef(id=a.id, code=a.code, name=a.name) for a in risk.assets],
        controls=[
            RiskControlOut(code=link.control.code, title=link.control.title, status=link.control.status, axis=link.axis)
            for link in links
        ],
        draft=assessment_out(db, risk, draft) if draft else None,
        latest=assessment_out(db, risk, latest) if latest else None,
        history=[assessment_out(db, risk, a) for a in finalized_assessments(db, risk)],
        treatment=TreatmentOut(
            option=risk.treatment_option, note=risk.treatment_note, budget=risk.treatment_budget, due=risk.treatment_due
        ),
        actions=[task_out(t) for t in actions],
        acceptance=_acceptance_out(db, acceptance) if accepted_latest else None,
        required_authority=required,
        can_accept=can_accept,
        can_edit=rights.any and risk.closed_at is None,
        closed_at=risk.closed_at,
        close_reason=risk.close_reason,
    )
```

- [ ] **Step 5: Implement the routes**

`backend/src/assayr/risk/router.py`:
```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from assayr.assets.models import Asset
from assayr.audit.service import record
from assayr.catalogue.access import EditRights, check_active_user, has_perm, rights_for
from assayr.catalogue.models import Control
from assayr.catalogue.router import FORBIDDEN, _like, resolve_scope
from assayr.db import get_session
from assayr.identity.deps import actor_for, current_user, get_clock, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm
from assayr.risk.library_router import require_methodology
from assayr.risk.models import Risk, RiskAssessment, RiskControl, RiskTemplate, Threat, Vulnerability
from assayr.risk.schemas import ControlLinksIn, RiskCreateIn, RiskDetailOut, RiskRowOut, RiskUpdateIn
from assayr.risk.service import next_risk_code, refresh_risk, risk_detail, risk_row

router = APIRouter(tags=["risks"])
NOT_FOUND = "Risk not found."
OWNER_ONLY = "Only an ISMS manager can change the owner."


def load_risk(db: Session, grant: Grant, scope_id: uuid.UUID | None, code: str) -> Risk:
    scope = resolve_scope(db, scope_id, grant)
    risk = db.scalar(select(Risk).where(Risk.scope_id == scope.id, Risk.code == code))
    if risk is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return risk


def require_edit(user: User, risk: Risk) -> EditRights:
    rights = rights_for(user, risk.scope_id, risk.owner_id, Perm.RISKS_WRITE, Perm.RISKS_WRITE_OWN)
    if not rights.any:
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    return rights


def require_open(risk: Risk) -> None:
    if risk.closed_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This risk is closed.")


@router.get("/risks", response_model=list[RiskRowOut])
def list_risks(
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
    status_: str | None = Query(None, alias="status", max_length=30),
    band: str | None = Query(None, max_length=20),
    owner: str | None = Query(None, max_length=40),
    q: str | None = Query(None, max_length=100),
    include_closed: bool = False,
) -> list[RiskRowOut]:
    scope = resolve_scope(db, scope_id, grant)
    stmt = select(Risk).where(Risk.scope_id == scope.id)
    if not include_closed and status_ != "closed":
        stmt = stmt.where(Risk.closed_at.is_(None))
    if status_:
        stmt = stmt.where(Risk.status == status_)
    if owner == "me":
        stmt = stmt.where(Risk.owner_id == user.id)
    elif owner:
        try:
            stmt = stmt.where(Risk.owner_id == uuid.UUID(owner))
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "owner must be 'me' or a user id.") from exc
    if q and q.strip():
        like = _like(q.strip())
        stmt = stmt.where(
            or_(func.lower(Risk.title).like(like, escape="\\"), func.lower(Risk.code).like(like, escape="\\"))
        )
    rows = [risk_row(db, r) for r in db.scalars(stmt.order_by(Risk.seq)).unique()]
    if band:
        rows = [r for r in rows if (r.current or r.inherent) is not None and (r.current or r.inherent).band == band]
    return rows


@router.post("/risks", response_model=RiskDetailOut, status_code=status.HTTP_201_CREATED)
def create_risk(
    body: RiskCreateIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> RiskDetailOut:
    scope = resolve_scope(db, scope_id, grant)
    if not has_perm(user, scope.id, Perm.RISKS_WRITE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    check_active_user(db, body.owner_id)
    version = require_methodology(db)
    template = None
    if body.template_code:
        template = db.scalar(select(RiskTemplate).where(RiskTemplate.code == body.template_code))
        if template is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Risk template not found.")
    now = get_clock(request)()
    seq, code = next_risk_code(db, scope.id)
    risk = Risk(
        scope_id=scope.id,
        code=code,
        seq=seq,
        title=(body.title or template.title).strip(),
        description=body.description if body.description is not None else (template.scenario if template else None),
        category=body.category or (template.category if template else None),
        approach=body.approach,
        owner_id=body.owner_id,
        template_code=template.code if template else None,
    )
    if template is not None:
        risk.threats = list(db.scalars(select(Threat).where(Threat.code.in_(template.threat_codes))))
        risk.vulnerabilities = list(
            db.scalars(select(Vulnerability).where(Vulnerability.code.in_(template.vulnerability_codes)))
        )
        controls = db.scalars(
            select(Control).where(
                Control.scope_id == scope.id,
                Control.code.in_(template.control_codes),
                Control.applicable.is_(True),
            )
        ).unique()
        risk.control_links = [RiskControl(control=c, axis="likelihood") for c in controls]
    db.add(risk)
    db.flush()
    db.add(
        RiskAssessment(
            risk_id=risk.id,
            methodology_version_id=version.id,
            likelihood=template.likelihood if template else None,
            consequence=dict(template.consequence) if template else None,
            assessed_by_id=user.id,
            created_at=now,
        )
    )
    db.flush()
    refresh_risk(db, risk, now)
    record(
        db,
        actor_for(request, user),
        "risk.create",
        "risk",
        risk.code,
        diff={"title": risk.title, "template": risk.template_code},
    )
    db.commit()
    return risk_detail(db, risk, user)


@router.get("/risks/{code}", response_model=RiskDetailOut)
def get_risk(
    code: str,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> RiskDetailOut:
    return risk_detail(db, load_risk(db, grant, scope_id, code), user)


def _resolve_codes(db: Session, model, codes: list[str], label: str) -> list:
    found = list(db.scalars(select(model).where(model.code.in_(codes)).order_by(model.code)))
    missing = sorted(set(codes) - {item.code for item in found})
    if missing:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown {label}: {missing[0]}.")
    return found


@router.patch("/risks/{code}", response_model=RiskDetailOut)
def update_risk(
    code: str,
    body: RiskUpdateIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> RiskDetailOut:
    risk = load_risk(db, grant, scope_id, code)
    rights = require_edit(user, risk)
    require_open(risk)
    fields = body.model_fields_set
    diff: dict[str, list] = {}
    if "owner_id" in fields and body.owner_id != risk.owner_id:
        if not rights.all:
            raise HTTPException(status.HTTP_403_FORBIDDEN, OWNER_ONLY)
        check_active_user(db, body.owner_id)
        diff["owner_id"] = [str(risk.owner_id) if risk.owner_id else None, str(body.owner_id) if body.owner_id else None]
        risk.owner_id = body.owner_id
    for name in ("title", "description", "category", "approach"):
        if name not in fields:
            continue
        value = getattr(body, name)
        if value is None and name in ("title", "approach"):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{name.capitalize()} can't be empty.")
        if value != getattr(risk, name):
            diff[name] = [getattr(risk, name), value]
            setattr(risk, name, value)
    for attr, model, label in (
        ("threat_codes", Threat, "threat"),
        ("vulnerability_codes", Vulnerability, "vulnerability"),
    ):
        codes = getattr(body, attr)
        if codes is None:
            continue
        items = _resolve_codes(db, model, codes, label)
        relation = "threats" if model is Threat else "vulnerabilities"
        before = [item.code for item in getattr(risk, relation)]
        if before != [item.code for item in items]:
            diff[relation] = [before, [item.code for item in items]]
            setattr(risk, relation, items)
    if body.asset_ids is not None:
        assets = list(
            db.scalars(
                select(Asset).where(Asset.id.in_(body.asset_ids), Asset.scope_id == risk.scope_id).order_by(Asset.seq)
            ).unique()
        )
        if len(assets) != len(set(body.asset_ids)):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown asset.")
        before = [a.code for a in risk.assets]
        if before != [a.code for a in assets]:
            diff["assets"] = [before, [a.code for a in assets]]
            risk.assets = assets
    if diff:
        record(db, actor_for(request, user), "risk.update", "risk", risk.code, diff=diff)
        db.commit()
    return risk_detail(db, risk, user)


@router.put("/risks/{code}/controls", response_model=RiskDetailOut)
def set_risk_controls(
    code: str,
    body: ControlLinksIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> RiskDetailOut:
    risk = load_risk(db, grant, scope_id, code)
    require_edit(user, risk)
    require_open(risk)
    codes = [link.code for link in body.links]
    if len(codes) != len(set(codes)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Each control can be linked once.")
    controls = {
        c.code: c
        for c in db.scalars(select(Control).where(Control.scope_id == risk.scope_id, Control.code.in_(codes))).unique()
    }
    for link in body.links:
        control = controls.get(link.code)
        if control is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Control {link.code} not found.")
        if not control.applicable:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{control.code} is excluded in the Statement of Applicability. "
                "Include it before linking it to a risk.",
            )
    before = sorted(f"{link.control.code}:{link.axis}" for link in risk.control_links)
    wanted = {controls[link.code].id: (controls[link.code], link.axis) for link in body.links}
    for link in list(risk.control_links):
        if link.control_id in wanted:
            link.axis = wanted.pop(link.control_id)[1]
        else:
            risk.control_links.remove(link)
    for control, axis in wanted.values():
        risk.control_links.append(RiskControl(control=control, axis=axis))
    db.flush()
    after = sorted(f"{link.control.code}:{link.axis}" for link in risk.control_links)
    if before != after:
        record(db, actor_for(request, user), "risk.controls", "risk", risk.code, diff={"controls": [before, after]})
    refresh_risk(db, risk, get_clock(request)())
    db.commit()
    return risk_detail(db, risk, user)
```

In `backend/src/assayr/main.py` add `from assayr.risk.router import router as risk_router` and `app.include_router(risk_router, prefix="/api/v1")`.

- [ ] **Step 6: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest -W error`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(risk): risk register with templates, threats, assets and mitigating controls"
```

---

### Task 7: Risk assessment — rating, suggested current level and finalizing

**Files:**
- Modify: `backend/src/assayr/risk/router.py`, `backend/tests/risk_helpers.py`
- Test: `backend/tests/test_risk_assessment.py`

**Interfaces:**
- Consumes: Task 6 service and helpers; `rating_error`, `band_for`, `suggest_current` (Task 3).
- Produces: `PATCH /api/v1/risks/{code}/assessment` (`AssessmentIn`; opens a new assessment when none is open, copying likelihood, consequence and rationale from the latest one) → `RiskDetailOut`; `POST /api/v1/risks/{code}/assessment/finalize` → `RiskDetailOut` (sets `review_due` = today + the current band's `review_days`); test helpers `DIMENSIONS`, `ratings(level, **overrides)`, `assessed_risk(client, *, likelihood, consequence, title="Test risk", owner_id=None) -> dict`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/risk_helpers.py`:
```python
DIMENSIONS = ("financial", "operational", "legal", "reputation", "data")


def ratings(level: int, **overrides: int) -> dict:
    values = {key: level for key in DIMENSIONS}
    values.update(overrides)
    return values


def assessed_risk(client, *, likelihood: int, consequence: int, title: str = "Test risk", owner_id=None) -> dict:
    """A risk with one finalized assessment and no controls, so current = target = inherent."""
    body = {"title": title}
    if owner_id is not None:
        body["owner_id"] = str(owner_id)
    code = new_risk(client, **body)["code"]
    response = client.patch(
        f"/api/v1/risks/{code}/assessment", json={"likelihood": likelihood, "consequence": ratings(consequence)}
    )
    assert response.status_code == 200, response.text
    response = client.post(f"/api/v1/risks/{code}/assessment/finalize")
    assert response.status_code == 200, response.text
    return response.json()
```

`backend/tests/test_risk_assessment.py`:
```python
from datetime import timedelta

import pytest
from sqlalchemy import select

from assayr.audit.models import AuditLog
from assayr.catalogue.models import Control
from assayr.risk.service import derive_status
from tests.conftest import create_user, sign_in
from tests.risk_helpers import assessed_risk, new_risk, ratings


def manager(client, db):
    create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")


def test_linked_controls_suggest_the_current_level(client, db, seeded, clock):
    manager(client, db)
    code = new_risk(client)["code"]
    client.put(f"/api/v1/risks/{code}/controls", json={"links": [{"code": "A.8.13"}, {"code": "A.8.7"}]})
    for control in db.scalars(select(Control).where(Control.code.in_(["A.8.13", "A.8.7"]))):
        control.status = "compliant"
    db.commit()
    body = client.patch(
        f"/api/v1/risks/{code}/assessment", json={"likelihood": 4, "consequence": ratings(3, operational=5)}
    ).json()
    assert body["draft"]["inherent"] == {
        "likelihood": 4,
        "consequence": 5,
        "score": 20,
        "band": "critical",
        "band_label": "Critical",
    }
    # Two compliant controls on likelihood: 4 → 2, so 2 × 5 = 10 (Medium).
    assert (body["draft"]["suggested"]["score"], body["draft"]["suggested"]["band"]) == (10, "medium")
    done = client.post(f"/api/v1/risks/{code}/assessment/finalize").json()
    assert (done["status"], done["draft"]) == ("assessed", None)
    assert (done["current"]["score"], done["target"]["score"]) == (10, 10)
    assert done["review_due"] == (clock().date() + timedelta(days=182)).isoformat()
    assert len(done["history"]) == 1 and done["latest"]["suggested"]["score"] == 10
    entry = db.scalar(select(AuditLog).where(AuditLog.action == "risk.assess"))
    assert entry.diff == {"inherent": 20, "current": 10, "target": 10, "band": "medium"}


def test_owner_needs_a_reason_to_override_the_suggestion(client, db, seeded, clock):
    manager(client, db)
    code = new_risk(client)["code"]
    url = f"/api/v1/risks/{code}/assessment"
    client.patch(url, json={"likelihood": 3, "consequence": ratings(3), "current_l": 2, "current_c": 3})
    response = client.post(f"{url}/finalize")
    assert response.status_code == 422
    assert response.json() == {"detail": "Explain why the current level differs from the suggested one."}
    client.patch(url, json={"current_reason": "Firewall rules were reviewed last month."})
    done = client.post(f"{url}/finalize").json()
    assert done["current"]["score"] == 6 and done["latest"]["current_reason"] == "Firewall rules were reviewed last month."


@pytest.mark.parametrize(
    "body,message",
    [
        ({"likelihood": 3, "consequence": {"financial": 3}}, "Rate the likelihood and every consequence area before finishing."),
        (
            {"likelihood": 2, "consequence": ratings(2), "current_l": 3, "current_c": 3, "current_reason": "x"},
            "The current level can't be higher than the inherent level.",
        ),
        (
            {"likelihood": 3, "consequence": ratings(3), "target_l": 4, "target_c": 4},
            "The target can't be worse than the current level.",
        ),
        (
            {"likelihood": 3, "consequence": ratings(3), "target_l": 2},
            "Give both the likelihood and the consequence for the target level.",
        ),
        (
            {"likelihood": 3, "consequence": ratings(3), "current_l": 2, "current_reason": "x"},
            "Give both the likelihood and the consequence for the current level.",
        ),
    ],
)
def test_finalize_validation(client, db, seeded, clock, body, message):
    manager(client, db)
    code = new_risk(client)["code"]
    assert client.patch(f"/api/v1/risks/{code}/assessment", json=body).status_code == 200
    response = client.post(f"/api/v1/risks/{code}/assessment/finalize")
    assert response.status_code == 422 and response.json() == {"detail": message}


def test_ratings_outside_the_scale_are_refused(client, db, seeded):
    manager(client, db)
    url = f"/api/v1/risks/{new_risk(client)['code']}/assessment"
    response = client.patch(url, json={"likelihood": 6})
    assert response.status_code == 422 and response.json() == {"detail": "Likelihood must be between 1 and 5."}
    response = client.patch(url, json={"consequence": {"weather": 2}})
    assert response.status_code == 422 and response.json() == {"detail": "Unknown consequence area: weather."}


def test_finalize_needs_an_open_assessment(client, db, seeded, clock):
    manager(client, db)
    risk = assessed_risk(client, likelihood=2, consequence=2)
    response = client.post(f"/api/v1/risks/{risk['code']}/assessment/finalize")
    assert response.status_code == 409 and response.json() == {"detail": "There's no assessment in progress."}


def test_reassessment_keeps_history(client, db, seeded, clock):
    manager(client, db)
    code = assessed_risk(client, likelihood=3, consequence=3)["code"]
    reopened = client.patch(f"/api/v1/risks/{code}/assessment", json={}).json()
    assert (reopened["status"], reopened["draft"]["likelihood"]) == ("reassessing", 3)
    clock.advance(days=1)
    client.patch(f"/api/v1/risks/{code}/assessment", json={"likelihood": 2})
    done = client.post(f"/api/v1/risks/{code}/assessment/finalize").json()
    assert (done["status"], done["current"]["score"], len(done["history"])) == ("assessed", 6, 2)
    assert done["history"][0]["current"]["score"] == 6 and done["history"][1]["current"]["score"] == 9


def test_only_editors_assess(client, db, seeded):
    manager(client, db)
    code = new_risk(client)["code"]
    create_user(db, "viewer@acme.com", roles=(("viewer", None),))
    sign_in(client, "viewer@acme.com")
    assert client.patch(f"/api/v1/risks/{code}/assessment", json={"likelihood": 2}).status_code == 403


BASE = dict(
    closed=False, has_final=True, has_draft=False, review_overdue=False, accepted=False, option=None, actions=[]
)


@pytest.mark.parametrize(
    "facts,expected",
    [
        ({"closed": True}, "closed"),
        ({"has_final": False, "has_draft": True}, "draft"),
        ({"has_draft": True}, "reassessing"),
        ({"review_overdue": True, "accepted": True}, "review_due"),
        ({"accepted": True, "option": "modify", "actions": ["todo"]}, "accepted"),
        ({"option": "retain"}, "treated"),
        ({"option": "share"}, "treated"),
        ({"option": "modify"}, "treatment_planned"),
        ({"option": "modify", "actions": ["todo", "in_progress"]}, "in_treatment"),
        ({"option": "modify", "actions": ["done", "cancelled"]}, "treated"),
        ({"option": "modify", "actions": ["cancelled"]}, "treatment_planned"),
        ({}, "assessed"),
    ],
)
def test_derive_status(facts, expected):
    assert derive_status(**{**BASE, **facts}) == expected
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_risk_assessment.py`
Expected: FAIL — the assessment routes return 404/405 (`test_derive_status` already passes; it pins Task 6's function).

- [ ] **Step 3: Implement**

Add to the imports of `backend/src/assayr/risk/router.py`: `from datetime import timedelta`, `from assayr.risk.methodology import band_for, rating_error, suggest_current`, extend the schema import with `AssessmentIn`, and extend the service import with `control_effects, definition_of, draft_assessment, inherent_of, latest_assessment`. Then append:
```python
@router.patch("/risks/{code}/assessment", response_model=RiskDetailOut)
def save_assessment(
    code: str,
    body: AssessmentIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> RiskDetailOut:
    risk = load_risk(db, grant, scope_id, code)
    require_edit(user, risk)
    require_open(risk)
    version = require_methodology(db)
    error = rating_error(
        version.definition,
        likelihood=body.likelihood,
        consequence=body.consequence,
        current=(body.current_l, body.current_c),
        target=(body.target_l, body.target_c),
    )
    if error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, error)
    now = get_clock(request)()
    draft = draft_assessment(db, risk)
    if draft is None:
        draft = RiskAssessment(risk_id=risk.id, methodology_version_id=version.id, created_at=now)
        latest = latest_assessment(db, risk)
        if latest is not None:  # a reassessment starts from the last ratings
            draft.likelihood = latest.likelihood
            draft.consequence = dict(latest.consequence or {})
            draft.rationale = latest.rationale
        db.add(draft)
    fields = body.model_fields_set
    for name in ("likelihood", "current_l", "current_c", "current_reason", "target_l", "target_c", "rationale"):
        if name in fields:
            setattr(draft, name, getattr(body, name))
    if "consequence" in fields:
        draft.consequence = {**(draft.consequence or {}), **(body.consequence or {})}
    draft.assessed_by_id = user.id
    db.flush()
    refresh_risk(db, risk, now)
    db.commit()
    return risk_detail(db, risk, user)


def _pair(values: tuple[int | None, int | None], default: tuple[int, int], name: str) -> tuple[int, int]:
    if values == (None, None):
        return default
    if None in values:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Give both the likelihood and the consequence for the {name} level."
        )
    return values  # type: ignore[return-value]


@router.post("/risks/{code}/assessment/finalize", response_model=RiskDetailOut)
def finalize_assessment(
    code: str,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> RiskDetailOut:
    risk = load_risk(db, grant, scope_id, code)
    require_edit(user, risk)
    require_open(risk)
    draft = draft_assessment(db, risk)
    if draft is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "There's no assessment in progress.")
    definition = definition_of(db, draft)
    inherent = inherent_of(definition, draft)
    if inherent is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Rate the likelihood and every consequence area before finishing."
        )
    suggested = suggest_current(definition, *inherent, control_effects(risk))
    current = _pair((draft.current_l, draft.current_c), suggested, "current")
    if current != suggested and not (draft.current_reason or "").strip():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Explain why the current level differs from the suggested one."
        )
    if current[0] * current[1] > inherent[0] * inherent[1]:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "The current level can't be higher than the inherent level."
        )
    target = _pair((draft.target_l, draft.target_c), current, "target")
    if target[0] * target[1] > current[0] * current[1]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The target can't be worse than the current level.")
    now = get_clock(request)()
    draft.suggested = {"likelihood": suggested[0], "consequence": suggested[1]}
    draft.current_l, draft.current_c = current
    draft.target_l, draft.target_c = target
    draft.finalized_at = now
    draft.assessed_by_id = user.id
    band = band_for(definition, *current)
    risk.review_due = now.date() + timedelta(days=band["review_days"])
    db.flush()
    refresh_risk(db, risk, now)
    record(
        db,
        actor_for(request, user),
        "risk.assess",
        "risk",
        risk.code,
        diff={
            "inherent": inherent[0] * inherent[1],
            "current": current[0] * current[1],
            "target": target[0] * target[1],
            "band": band["key"],
        },
    )
    db.commit()
    return risk_detail(db, risk, user)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest -W error`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(risk): assessment with control-based suggested level and finalization"
```

---

### Task 8: Treatment, actions, acceptance with authority levels, closing and scheduled review

**Files:**
- Create: `backend/src/assayr/tasks/router.py`
- Modify: `backend/src/assayr/risk/router.py`, `backend/src/assayr/scoring/jobs.py`, `backend/src/assayr/main.py`
- Test: `backend/tests/test_risk_treatment.py`

**Interfaces:**
- Consumes: Task 6/7 service and router helpers; `acceptance_days`, `authority_allows`, `AUTHORITY_LABEL` (Task 3); `Task` (Task 2).
- Produces: `POST /api/v1/risks/{code}/treatment` (`TreatmentIn`); `POST /api/v1/risks/{code}/actions` (`ActionIn`, 201 → `RiskDetailOut`); `PATCH /api/v1/tasks/{task_id}` (`{title?, status?, due?, assignee_id?}` → `TaskOut`); `POST /api/v1/risks/{code}/accept` (`AcceptIn`); `POST /api/v1/risks/{code}/close` (`CloseIn`); the scheduled `recompute_scope` job also runs `refresh_scope_risks`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_risk_treatment.py`:
```python
from datetime import timedelta

from sqlalchemy import select

from assayr.audit.models import AuditLog
from assayr.scoring.jobs import enqueue_recompute_all
from tests.conftest import create_user, sign_in
from tests.evidence_helpers import run_jobs
from tests.risk_helpers import assessed_risk, new_risk

STATEMENT = {"statement": "The residual risk is accepted until the next review."}


def manager(client, db):
    user = create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")
    return user


def test_modify_treatment_moves_through_the_states(client, db, seeded, clock):
    manager(client, db)
    code = assessed_risk(client, likelihood=4, consequence=4)["code"]
    planned = client.post(
        f"/api/v1/risks/{code}/treatment", json={"option": "modify", "budget": "PKR 2m", "due": "2026-12-31"}
    ).json()
    assert planned["status"] == "treatment_planned" and planned["treatment"]["budget"] == "PKR 2m"
    response = client.post(f"/api/v1/risks/{code}/actions", json={"title": "Enable MFA for remote access"})
    assert response.status_code == 201
    action = response.json()["actions"][0]
    assert action["status"] == "todo" and response.json()["progress"] == {"done": 0, "total": 1}
    client.patch(f"/api/v1/tasks/{action['id']}", json={"status": "in_progress"})
    assert client.get(f"/api/v1/risks/{code}").json()["status"] == "in_treatment"
    assert client.patch(f"/api/v1/tasks/{action['id']}", json={"status": "done"}).json()["done_at"] is not None
    treated = client.get(f"/api/v1/risks/{code}").json()
    assert (treated["status"], treated["required_authority"], treated["can_accept"]) == (
        "treated",
        "isms_manager",
        True,
    )
    accepted = client.post(f"/api/v1/risks/{code}/accept", json=STATEMENT).json()
    assert accepted["status"] == "accepted" and accepted["can_accept"] is False
    assert accepted["acceptance"]["expires_at"][:10] == (clock().date() + timedelta(days=365)).isoformat()
    assert db.scalar(select(AuditLog).where(AuditLog.action == "risk.accept")).diff["band"] == "high"


def test_acceptance_needs_the_right_authority(client, db, seeded, clock):
    owner = create_user(db, "bilal@acme.com", roles=(("risk_owner", None),), full_name="Bilal Khan")
    create_user(db, "tariq@acme.com", roles=(("executive", None),), full_name="Tariq Qureshi")
    manager(client, db)
    high = assessed_risk(client, likelihood=4, consequence=4, owner_id=owner.id)["code"]
    critical = assessed_risk(client, likelihood=5, consequence=5, owner_id=owner.id)["code"]
    medium = assessed_risk(client, likelihood=3, consequence=3, owner_id=owner.id)["code"]
    response = client.post(f"/api/v1/risks/{critical}/accept", json=STATEMENT)
    assert response.status_code == 403
    assert response.json() == {"detail": "A critical risk must be accepted by top management."}
    sign_in(client, "bilal@acme.com")
    response = client.post(f"/api/v1/risks/{high}/accept", json=STATEMENT)
    assert response.status_code == 403
    assert response.json() == {"detail": "A high risk must be accepted by an ISMS manager."}
    assert client.get(f"/api/v1/risks/{high}").json()["can_accept"] is False
    assert client.post(f"/api/v1/risks/{medium}/accept", json=STATEMENT).json()["status"] == "accepted"
    sign_in(client, "tariq@acme.com")
    accepted = client.post(f"/api/v1/risks/{critical}/accept", json=STATEMENT).json()
    assert (accepted["acceptance"]["authority"], accepted["treatment"]["option"]) == ("executive", "retain")
    assert accepted["acceptance"]["expires_at"][:10] == (clock().date() + timedelta(days=90)).isoformat()


def test_risk_owner_cannot_accept_someone_elses_risk(client, db, seeded, clock):
    create_user(db, "bilal@acme.com", roles=(("risk_owner", None),))
    manager(client, db)
    code = assessed_risk(client, likelihood=2, consequence=2)["code"]
    sign_in(client, "bilal@acme.com")
    response = client.post(f"/api/v1/risks/{code}/accept", json=STATEMENT)
    assert response.status_code == 403
    assert response.json() == {"detail": "A low risk must be accepted by the risk owner."}


def test_acceptance_waits_for_open_actions(client, db, seeded, clock):
    manager(client, db)
    code = assessed_risk(client, likelihood=4, consequence=4)["code"]
    client.post(f"/api/v1/risks/{code}/treatment", json={"option": "modify"})
    client.post(f"/api/v1/risks/{code}/actions", json={"title": "Segment the network"})
    response = client.post(f"/api/v1/risks/{code}/accept", json=STATEMENT)
    assert response.status_code == 409
    assert response.json() == {"detail": "Finish the treatment actions before accepting the residual risk."}


def test_actions_need_the_modify_option(client, db, seeded, clock):
    manager(client, db)
    code = assessed_risk(client, likelihood=3, consequence=3)["code"]
    response = client.post(f"/api/v1/risks/{code}/actions", json={"title": "x"})
    assert response.status_code == 409
    assert response.json() == {"detail": "Treatment actions belong to the 'modify' option. Choose it first."}


def test_avoid_and_share_need_a_record(client, db, seeded, clock):
    manager(client, db)
    code = assessed_risk(client, likelihood=3, consequence=3)["code"]
    response = client.post(f"/api/v1/risks/{code}/treatment", json={"option": "avoid"})
    assert response.status_code == 422 and response.json() == {"detail": "Record the decision to avoid the risk."}
    closed = client.post(
        f"/api/v1/risks/{code}/treatment", json={"option": "avoid", "note": "We stopped offering the service."}
    ).json()
    assert (closed["status"], closed["close_reason"]) == ("closed", "Avoided: We stopped offering the service.")
    assert client.get("/api/v1/risks").json() == []
    assert [r["code"] for r in client.get("/api/v1/risks?include_closed=true").json()] == [code]
    other = assessed_risk(client, likelihood=3, consequence=3)["code"]
    response = client.post(f"/api/v1/risks/{other}/treatment", json={"option": "share"})
    assert response.status_code == 422
    assert response.json() == {"detail": "Record the contract or insurance that shares the risk."}


def test_treatment_needs_a_finished_assessment(client, db, seeded):
    manager(client, db)
    response = client.post(f"/api/v1/risks/{new_risk(client)['code']}/treatment", json={"option": "retain"})
    assert response.status_code == 409
    assert response.json() == {"detail": "Finish the assessment before choosing a treatment."}


def test_closing_a_risk(client, db, seeded, clock):
    manager(client, db)
    code = assessed_risk(client, likelihood=2, consequence=2)["code"]
    closed = client.post(f"/api/v1/risks/{code}/close", json={"reason": "The office was sold."}).json()
    assert (closed["status"], closed["can_edit"]) == ("closed", False)
    response = client.patch(f"/api/v1/risks/{code}", json={"title": "x"})
    assert response.status_code == 409 and response.json() == {"detail": "This risk is closed."}


def test_scheduled_check_flags_lapsed_acceptance(app, client, db, seeded, clock):
    manager(client, db)
    code = assessed_risk(client, likelihood=2, consequence=2)["code"]
    client.post(f"/api/v1/risks/{code}/accept", json=STATEMENT)
    clock.advance(days=366)
    enqueue_recompute_all(db, clock())
    db.commit()
    run_jobs(app)
    assert client.get(f"/api/v1/risks/{code}").json()["status"] == "review_due"


def test_tasks_are_updated_by_assignees_and_risk_editors_only(client, db, seeded, clock):
    helper = create_user(db, "ali@acme.com", roles=(("contributor", None),), full_name="Ali Raza")
    create_user(db, "zara@acme.com", roles=(("contributor", None),))
    manager(client, db)
    code = assessed_risk(client, likelihood=4, consequence=4)["code"]
    client.post(f"/api/v1/risks/{code}/treatment", json={"option": "modify"})
    detail = client.post(
        f"/api/v1/risks/{code}/actions", json={"title": "Patch VPN", "assignee_id": str(helper.id)}
    ).json()
    task_id = detail["actions"][0]["id"]
    assert detail["actions"][0]["assignee"]["full_name"] == "Ali Raza"
    sign_in(client, "ali@acme.com")
    assert client.patch(f"/api/v1/tasks/{task_id}", json={"status": "in_progress"}).status_code == 200
    sign_in(client, "zara@acme.com")
    assert client.patch(f"/api/v1/tasks/{task_id}", json={"status": "done"}).status_code == 403
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_risk_treatment.py`
Expected: FAIL — 404/405 on the new routes.

- [ ] **Step 3: Implement the risk routes**

In `backend/src/assayr/risk/router.py`: extend the imports with `from assayr.risk.methodology import AUTHORITY_LABEL, acceptance_days, authority_allows`, `from assayr.risk.models import RiskAcceptance`, `from assayr.tasks.models import Task`, schemas `AcceptIn, ActionIn, CloseIn, TreatmentIn`, and service `held_authority, open_actions, risk_actions`. Append:
```python
@router.post("/risks/{code}/treatment", response_model=RiskDetailOut)
def set_treatment(
    code: str,
    body: TreatmentIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> RiskDetailOut:
    risk = load_risk(db, grant, scope_id, code)
    require_edit(user, risk)
    require_open(risk)
    if latest_assessment(db, risk) is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Finish the assessment before choosing a treatment.")
    note = (body.note or "").strip()
    if body.option == "avoid" and not note:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Record the decision to avoid the risk.")
    if body.option == "share" and not note:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Record the contract or insurance that shares the risk."
        )
    now = get_clock(request)()
    before = risk.treatment_option
    risk.treatment_option = body.option
    risk.treatment_note = note or None
    risk.treatment_budget = body.budget
    risk.treatment_due = body.due
    if body.option == "avoid":
        risk.closed_at = now
        risk.close_reason = f"Avoided: {note}"
    refresh_risk(db, risk, now)
    record(db, actor_for(request, user), "risk.treatment", "risk", risk.code, diff={"option": [before, body.option]})
    db.commit()
    return risk_detail(db, risk, user)


@router.post("/risks/{code}/actions", response_model=RiskDetailOut, status_code=status.HTTP_201_CREATED)
def add_action(
    code: str,
    body: ActionIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> RiskDetailOut:
    risk = load_risk(db, grant, scope_id, code)
    require_edit(user, risk)
    require_open(risk)
    if risk.treatment_option != "modify":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Treatment actions belong to the 'modify' option. Choose it first."
        )
    check_active_user(db, body.assignee_id, "Assignee")
    task = Task(
        scope_id=risk.scope_id,
        entity_type="risk",
        entity_id=str(risk.id),
        title=body.title.strip(),
        assignee_id=body.assignee_id,
        due=body.due,
        created_by_id=user.id,
    )
    db.add(task)
    db.flush()
    refresh_risk(db, risk, get_clock(request)())
    record(
        db, actor_for(request, user), "task.create", "task", str(task.id), diff={"risk": risk.code, "title": task.title}
    )
    db.commit()
    return risk_detail(db, risk, user)


@router.post("/risks/{code}/accept", response_model=RiskDetailOut)
def accept_risk(
    code: str,
    body: AcceptIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> RiskDetailOut:
    risk = load_risk(db, grant, scope_id, code)
    require_open(risk)
    latest = latest_assessment(db, risk)
    if latest is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Finish the assessment before accepting the risk.")
    if draft_assessment(db, risk) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Finish the reassessment before accepting the risk.")
    if risk.treatment_option == "modify" and open_actions(risk_actions(db, risk)):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Finish the treatment actions before accepting the residual risk."
        )
    definition = definition_of(db, latest)
    band = band_for(definition, latest.current_l, latest.current_c)
    held = held_authority(user, risk.scope_id, risk.owner_id == user.id)
    if not authority_allows(held, band["authority"]):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"A {band['label'].lower()} risk must be accepted by {AUTHORITY_LABEL[band['authority']]}.",
        )
    now = get_clock(request)()
    if risk.treatment_option is None:
        risk.treatment_option = "retain"
    acceptance = RiskAcceptance(
        risk_id=risk.id,
        assessment_id=latest.id,
        band=band["key"],
        score=latest.current_l * latest.current_c,
        authority=held,
        statement=body.statement.strip(),
        accepted_by_id=user.id,
        accepted_at=now,
        expires_at=now + timedelta(days=acceptance_days(definition, band["key"])),
    )
    db.add(acceptance)
    db.flush()
    refresh_risk(db, risk, now)
    record(
        db,
        actor_for(request, user),
        "risk.accept",
        "risk",
        risk.code,
        diff={"band": band["key"], "score": acceptance.score, "expires_at": acceptance.expires_at.isoformat()},
    )
    db.commit()
    return risk_detail(db, risk, user)


@router.post("/risks/{code}/close", response_model=RiskDetailOut)
def close_risk(
    code: str,
    body: CloseIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> RiskDetailOut:
    risk = load_risk(db, grant, scope_id, code)
    require_edit(user, risk)
    if risk.closed_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This risk is already closed.")
    now = get_clock(request)()
    risk.closed_at = now
    risk.close_reason = body.reason.strip()
    refresh_risk(db, risk, now)
    record(db, actor_for(request, user), "risk.close", "risk", risk.code, reason=risk.close_reason)
    db.commit()
    return risk_detail(db, risk, user)
```

- [ ] **Step 4: Implement task updates and the scheduled refresh**

`backend/src/assayr/tasks/router.py`:
```python
import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.catalogue.access import check_active_user, rights_for
from assayr.catalogue.router import FORBIDDEN
from assayr.db import get_session
from assayr.identity.deps import actor_for, current_user, get_clock, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm
from assayr.risk.models import Risk
from assayr.risk.schemas import TaskOut, task_out
from assayr.risk.service import refresh_risk
from assayr.tasks.models import Task

router = APIRouter(tags=["tasks"])


class TaskUpdateIn(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=300)
    status: Literal["todo", "in_progress", "blocked", "done", "cancelled"] | None = None
    due: date | None = None
    assignee_id: uuid.UUID | None = None


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(
    task_id: uuid.UUID,
    body: TaskUpdateIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
) -> TaskOut:
    task = db.get(Task, task_id)
    if task is None or not grant.allows(task.scope_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found.")
    risk = db.get(Risk, uuid.UUID(task.entity_id)) if task.entity_type == "risk" else None
    editor = risk is not None and rights_for(
        user, risk.scope_id, risk.owner_id, Perm.RISKS_WRITE, Perm.RISKS_WRITE_OWN
    ).any
    if not (editor or task.assignee_id == user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    now = get_clock(request)()
    fields = body.model_fields_set
    diff: dict[str, list] = {}
    if "assignee_id" in fields and body.assignee_id != task.assignee_id:
        check_active_user(db, body.assignee_id, "Assignee")
        diff["assignee_id"] = [str(task.assignee_id) if task.assignee_id else None, str(body.assignee_id) if body.assignee_id else None]
        task.assignee_id = body.assignee_id
    for name in ("title", "status", "due"):
        if name not in fields:
            continue
        value = getattr(body, name)
        if value is None and name in ("title", "status"):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{name.capitalize()} can't be empty.")
        if value != getattr(task, name):
            diff[name] = [str(getattr(task, name)) if getattr(task, name) is not None else None, str(value) if value is not None else None]
            setattr(task, name, value)
    if "status" in diff:
        task.done_at = now if task.status == "done" else None
    if diff:
        db.flush()
        if risk is not None:
            refresh_risk(db, risk, now)
        record(db, actor_for(request, user), "task.update", "task", str(task.id), diff=diff)
        db.commit()
    db.refresh(task)
    return task_out(task)
```

In `backend/src/assayr/main.py` add `from assayr.tasks.router import router as tasks_router` and `app.include_router(tasks_router, prefix="/api/v1")`.

In `backend/src/assayr/scoring/jobs.py` add `from assayr.risk.service import refresh_scope_risks` and change `recompute_scope_job` to:
```python
@handler("recompute_scope")
def recompute_scope_job(db: Session, payload: dict, env: JobEnv) -> None:
    scope_id = uuid.UUID(payload["scope_id"])
    now = env.now()
    recompute_scope(db, scope_id, now, env.settings)
    refresh_scope_risks(db, scope_id, now)
    db.commit()
```

- [ ] **Step 5: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest -W error`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(risk): treatment actions, residual acceptance by authority level and scheduled review"
```

---

### Task 9: Snapshots, snapshot comparison and the risk register export

**Files:**
- Create: `backend/src/assayr/exports.py`, `backend/src/assayr/risk/snapshots.py`
- Modify: `backend/src/assayr/risk/router.py`
- Test: `backend/tests/test_exports.py`, `backend/tests/test_risk_snapshots.py`

**Interfaces:**
- Consumes: Task 6–8 service; `RiskSnapshot` (Task 2); `SnapshotIn` (Task 6).
- Produces: `XLSX_MIME`; `safe_cell(value)`; `add_sheet(workbook, title, header, rows)`; `xlsx_response(workbook, filename) -> Response`; `snapshot_rows(db, scope_id) -> list[dict]` (rows `{code, title, owner, status, treatment, inherent, current, target}`; levels are `LevelOut` dicts); `level_text(level) -> str | None` ("High (16)"); `compare_rows(base, head) -> {added, removed, changed: [{code, title, changes: [{field, before, after}]}]}`; `POST /api/v1/risk-snapshots` (201), `GET /api/v1/risk-snapshots`, `GET /api/v1/risk-snapshots/compare?base=&head=`, `GET /api/v1/risk-snapshots/{snapshot_id}`, `GET /api/v1/risk-register/export.xlsx`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_exports.py`:
```python
import pytest

from assayr.exports import safe_cell


@pytest.mark.parametrize(
    "value,expected",
    [
        ('=HYPERLINK("http://evil","click")', '\'=HYPERLINK("http://evil","click")'),
        ("+1+1", "'+1+1"),
        ("-2+3", "'-2+3"),
        ("@SUM(A1)", "'@SUM(A1)"),
        ("\tcmd", "'\tcmd"),
        ("Ransomware", "Ransomware"),
        (12, 12),
        (None, None),
    ],
)
def test_safe_cell(value, expected):
    assert safe_cell(value) == expected
```

`backend/tests/test_risk_snapshots.py`:
```python
import io

import openpyxl
from sqlalchemy import select

from assayr.audit.models import AuditLog
from assayr.exports import XLSX_MIME
from tests.conftest import create_user, sign_in
from tests.risk_helpers import assessed_risk


def manager(client, db):
    create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")


def test_snapshot_freezes_the_register_and_compare_shows_changes(client, db, seeded, clock):
    manager(client, db)
    code = assessed_risk(client, likelihood=4, consequence=4, title="Ransomware")["code"]
    first = client.post("/api/v1/risk-snapshots", json={"label": "Q3 2026 assessment"})
    assert first.status_code == 201
    first = first.json()
    assert (first["risk_count"], first["rows"][0]["current"]["score"]) == (1, 16)
    clock.advance(minutes=5)
    client.patch(f"/api/v1/risks/{code}/assessment", json={"likelihood": 2})
    client.post(f"/api/v1/risks/{code}/assessment/finalize")
    second = client.post("/api/v1/risk-snapshots", json={"label": "Q4 2026 assessment"}).json()
    assert client.get(f"/api/v1/risk-snapshots/{first['id']}").json()["rows"][0]["current"]["score"] == 16
    diff = client.get(f"/api/v1/risk-snapshots/compare?base={first['id']}&head={second['id']}").json()
    assert (diff["added"], diff["removed"]) == ([], [])
    assert diff["changed"] == [
        {
            "code": code,
            "title": "Ransomware",
            "changes": [
                {"field": "current", "before": "High (16)", "after": "Medium (8)"},
                {"field": "target", "before": "High (16)", "after": "Medium (8)"},
            ],
        }
    ]
    assert [s["label"] for s in client.get("/api/v1/risk-snapshots").json()] == [
        "Q4 2026 assessment",
        "Q3 2026 assessment",
    ]


def test_snapshots_need_write_permission_to_create(client, db, seeded):
    create_user(db, "viewer@acme.com", roles=(("viewer", None),))
    sign_in(client, "viewer@acme.com")
    assert client.post("/api/v1/risk-snapshots", json={"label": "x"}).status_code == 403
    assert client.get("/api/v1/risk-snapshots").json() == []


def test_export_neutralises_formulas(client, db, seeded, clock):
    manager(client, db)
    code = assessed_risk(client, likelihood=4, consequence=4, title='=HYPERLINK("http://evil","click")')["code"]
    client.post(f"/api/v1/risks/{code}/treatment", json={"option": "modify"})
    client.post(f"/api/v1/risks/{code}/actions", json={"title": "Enable MFA"})
    response = client.get("/api/v1/risk-register/export.xlsx")
    assert response.status_code == 200 and response.headers["content-type"] == XLSX_MIME
    assert response.headers["content-disposition"].startswith("attachment")
    book = openpyxl.load_workbook(io.BytesIO(response.content))
    register = book["Register"]
    assert [c.value for c in register[1]][:3] == ["Code", "Risk", "Category"]
    assert register["B2"].value == '\'=HYPERLINK("http://evil","click")'
    assert register["G2"].value == "High (16)"
    assert book["Treatment plan"]["F2"].value == "Enable MFA"
    assert db.scalar(select(AuditLog).where(AuditLog.action == "risk.export")) is not None
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_exports.py tests/test_risk_snapshots.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'assayr.exports'`.

- [ ] **Step 3: Implement the helpers**

`backend/src/assayr/exports.py`:
```python
"""Spreadsheet exports. User text never becomes a live formula."""

import io

from fastapi.responses import Response
from openpyxl import Workbook
from openpyxl.styles import Font

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value):
    if isinstance(value, str) and value.startswith(_FORMULA_START):
        return "'" + value
    return value


def add_sheet(workbook: Workbook, title: str, header: list[str], rows: list[list]) -> None:
    sheet = workbook.create_sheet(title)
    sheet.append(header)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in rows:
        sheet.append([safe_cell(value) for value in row])
    sheet.freeze_panes = "A2"


def xlsx_response(workbook: Workbook, filename: str) -> Response:
    if "Sheet" in workbook.sheetnames and len(workbook.sheetnames) > 1:
        del workbook["Sheet"]
    buffer = io.BytesIO()
    workbook.save(buffer)
    return Response(
        buffer.getvalue(),
        media_type=XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "X-Content-Type-Options": "nosniff"},
    )
```

`backend/src/assayr/risk/snapshots.py`:
```python
"""Frozen copies of the risk register and what changed between two of them (clause 8.2 records)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.risk.models import Risk
from assayr.risk.service import risk_row

COMPARED_LEVELS = ("current", "target")
COMPARED_FIELDS = ("status", "treatment")


def snapshot_rows(db: Session, scope_id: uuid.UUID) -> list[dict]:
    rows = []
    for risk in db.scalars(
        select(Risk).where(Risk.scope_id == scope_id, Risk.closed_at.is_(None)).order_by(Risk.seq)
    ).unique():
        row = risk_row(db, risk)
        if row.current is None:
            continue
        rows.append(
            {
                "code": row.code,
                "title": row.title,
                "owner": row.owner.full_name if row.owner else None,
                "status": row.status,
                "treatment": row.treatment_option,
                "inherent": row.inherent.model_dump() if row.inherent else None,
                "current": row.current.model_dump(),
                "target": row.target.model_dump() if row.target else None,
            }
        )
    return rows


def level_text(level: dict | None) -> str | None:
    return f"{level['band_label']} ({level['score']})" if level else None


def compare_rows(base: list[dict], head: list[dict]) -> dict:
    before = {row["code"]: row for row in base}
    after = {row["code"]: row for row in head}
    changed = []
    for code, row in after.items():
        old = before.get(code)
        if old is None:
            continue
        changes = []
        for field in COMPARED_LEVELS:
            was, now = level_text(old[field]), level_text(row[field])
            if was != now:
                changes.append({"field": field, "before": was, "after": now})
        for field in COMPARED_FIELDS:
            if old[field] != row[field]:
                changes.append({"field": field, "before": old[field], "after": row[field]})
        if changes:
            changed.append({"code": code, "title": row["title"], "changes": changes})
    return {
        "added": [code for code in after if code not in before],
        "removed": [code for code in before if code not in after],
        "changed": changed,
    }
```

- [ ] **Step 4: Implement the routes**

In `backend/src/assayr/risk/router.py` extend the imports with `from datetime import datetime`, `from openpyxl import Workbook`, `from pydantic import BaseModel`, `from fastapi.responses import Response`, `from assayr.exports import add_sheet, xlsx_response`, `from assayr.risk.models import MethodologyVersion, RiskSnapshot`, `from assayr.risk.schemas import SnapshotIn`, `from assayr.risk.snapshots import compare_rows, level_text, snapshot_rows`, and append:
```python
class SnapshotSummaryOut(BaseModel):
    id: uuid.UUID
    label: str
    taken_at: datetime
    taken_by: str | None
    methodology_version: int
    risk_count: int


class SnapshotOut(SnapshotSummaryOut):
    rows: list[dict]


class SnapshotChangeOut(BaseModel):
    field: str
    before: str | None
    after: str | None


class SnapshotChangedRiskOut(BaseModel):
    code: str
    title: str
    changes: list[SnapshotChangeOut]


class SnapshotCompareOut(BaseModel):
    base: SnapshotSummaryOut
    head: SnapshotSummaryOut
    added: list[str]
    removed: list[str]
    changed: list[SnapshotChangedRiskOut]


def _summary(db: Session, snapshot: RiskSnapshot) -> SnapshotSummaryOut:
    taker = db.get(User, snapshot.taken_by_id) if snapshot.taken_by_id else None
    return SnapshotSummaryOut(
        id=snapshot.id,
        label=snapshot.label,
        taken_at=snapshot.taken_at,
        taken_by=taker.full_name if taker else None,
        methodology_version=db.get(MethodologyVersion, snapshot.methodology_version_id).version_no,
        risk_count=len(snapshot.rows),
    )


def _snapshot(db: Session, grant: Grant, snapshot_id: uuid.UUID) -> RiskSnapshot:
    snapshot = db.get(RiskSnapshot, snapshot_id)
    if snapshot is None or not grant.allows(snapshot.scope_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Snapshot not found.")
    return snapshot


@router.post("/risk-snapshots", response_model=SnapshotOut, status_code=status.HTTP_201_CREATED)
def create_snapshot(
    body: SnapshotIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> SnapshotOut:
    scope = resolve_scope(db, scope_id, grant)
    if not has_perm(user, scope.id, Perm.RISKS_WRITE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    snapshot = RiskSnapshot(
        scope_id=scope.id,
        label=body.label.strip(),
        taken_at=get_clock(request)(),
        taken_by_id=user.id,
        methodology_version_id=require_methodology(db).id,
        rows=snapshot_rows(db, scope.id),
    )
    db.add(snapshot)
    db.flush()
    record(
        db,
        actor_for(request, user),
        "risk.snapshot",
        "risk_snapshot",
        str(snapshot.id),
        diff={"label": snapshot.label, "risks": len(snapshot.rows)},
    )
    db.commit()
    return SnapshotOut(**_summary(db, snapshot).model_dump(), rows=snapshot.rows)


@router.get("/risk-snapshots", response_model=list[SnapshotSummaryOut])
def list_snapshots(
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> list[SnapshotSummaryOut]:
    scope = resolve_scope(db, scope_id, grant)
    snapshots = db.scalars(
        select(RiskSnapshot).where(RiskSnapshot.scope_id == scope.id).order_by(RiskSnapshot.taken_at.desc())
    )
    return [_summary(db, s) for s in snapshots]


@router.get("/risk-snapshots/compare", response_model=SnapshotCompareOut)
def compare_snapshots(
    base: uuid.UUID,
    head: uuid.UUID,
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
) -> SnapshotCompareOut:
    before, after = _snapshot(db, grant, base), _snapshot(db, grant, head)
    return SnapshotCompareOut(
        base=_summary(db, before), head=_summary(db, after), **compare_rows(before.rows, after.rows)
    )


@router.get("/risk-snapshots/{snapshot_id}", response_model=SnapshotOut)
def get_snapshot(
    snapshot_id: uuid.UUID,
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
) -> SnapshotOut:
    snapshot = _snapshot(db, grant, snapshot_id)
    return SnapshotOut(**_summary(db, snapshot).model_dump(), rows=snapshot.rows)


TREATMENT_LABEL = {"modify": "Modify", "retain": "Retain", "avoid": "Avoid", "share": "Share"}


@router.get("/risk-register/export.xlsx")
def export_register(
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.RISKS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> Response:
    scope = resolve_scope(db, scope_id, grant)
    risks = list(db.scalars(select(Risk).where(Risk.scope_id == scope.id).order_by(Risk.seq)).unique())
    register, plan = [], []
    for risk in risks:
        row = risk_row(db, risk)
        register.append(
            [
                row.code,
                row.title,
                row.category,
                row.owner.full_name if row.owner else None,
                row.status.replace("_", " "),
                level_text(row.inherent.model_dump()) if row.inherent else None,
                level_text(row.current.model_dump()) if row.current else None,
                level_text(row.target.model_dump()) if row.target else None,
                TREATMENT_LABEL.get(row.treatment_option or "", None),
                row.review_due.isoformat() if row.review_due else None,
                row.acceptance_expires.date().isoformat() if row.acceptance_expires else None,
            ]
        )
        for task in risk_actions(db, risk) or [None]:
            if task is None and risk.treatment_option is None:
                continue
            plan.append(
                [
                    risk.code,
                    TREATMENT_LABEL.get(risk.treatment_option or "", None),
                    risk.treatment_note,
                    risk.treatment_budget,
                    risk.treatment_due.isoformat() if risk.treatment_due else None,
                    task.title if task else None,
                    task.assignee.full_name if task and task.assignee else None,
                    task.due.isoformat() if task and task.due else None,
                    task.status.replace("_", " ") if task else None,
                ]
            )
    workbook = Workbook()
    add_sheet(
        workbook,
        "Register",
        [
            "Code",
            "Risk",
            "Category",
            "Owner",
            "Status",
            "Inherent",
            "Current",
            "Target",
            "Treatment",
            "Next review",
            "Acceptance expires",
        ],
        register,
    )
    add_sheet(
        workbook,
        "Treatment plan",
        ["Risk", "Treatment", "Decision or note", "Budget", "Due", "Action", "Assignee", "Action due", "Action status"],
        plan,
    )
    record(db, actor_for(request, user), "risk.export", "risk", None, diff={"risks": len(risks)})
    db.commit()
    return xlsx_response(workbook, "risk-register.xlsx")
```

- [ ] **Step 5: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest -W error`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(risk): register snapshots, comparison and spreadsheet export"
```

---
### Task 10: Statement of Applicability — applicability, justification sources and traceability checks

**Files:**
- Create: `backend/src/assayr/soa/schemas.py`, `backend/src/assayr/soa/service.py`, `backend/src/assayr/soa/router.py`
- Modify: `backend/src/assayr/scoring/service.py` (`recompute_control`), `backend/src/assayr/main.py`
- Test: `backend/tests/test_soa_api.py`, `backend/tests/test_scoring.py` (append)

**Interfaces:**
- Consumes: `Control.applicable/soa_sources/soa_justification/exclusion_reason` (Task 2); `Risk`, `RiskControl`; `latest_assessment`, `definition_of` (Task 6); `band_for` (Task 3); `slot_views`, `recompute_control` (Phase 1a); `has_perm`.
- Produces: `MANUAL_SOURCES` (`legal`, `contractual`, `business`, `best_practice` → labels); `SourceOut {kind, label, ref}`; `SoaItemOut {code, title, theme, applicable, sources, justification, exclusion_reason, implementation_status, status, evidence_verified, evidence_required, owner}`; `SoaChecksOut {orphans, excluded_mitigating: [{code, risks}], untreated_risks, ok}`; `SoaOut {items, checks}`; `SoaItemsIn {codes, applicable?, sources?, justification?, exclusion_reason?}`; `active_risk_links(db, scope_id) -> dict[control_id, [risk codes]]`; `untreated_risks(db, scope_id) -> list[str]`; `soa_view(db, scope_id, settings, today) -> SoaOut`; `GET /api/v1/soa`; `PATCH /api/v1/soa/items`. `recompute_control` gives a non-applicable control status `excluded` and score `None`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_scoring.py`:
```python
def test_excluded_controls_drop_out_of_readiness(db, seeded, settings):
    control = control_with_slots(db)
    control.applicable = False
    result = recompute_control(db, control, utcnow(), settings, trigger="Excluded in the Statement of Applicability")
    assert (result.status, control.status, control.score) == ("excluded", "excluded", None)
    controls = list(db.scalars(select(Control)))
    assert weighted_readiness(controls) == weighted_readiness([c for c in controls if c.code != control.code])
```

`backend/tests/test_soa_api.py`:
```python
from sqlalchemy import select

from assayr.audit.models import AuditLog
from assayr.catalogue.models import Control
from tests.conftest import create_user, sign_in
from tests.risk_helpers import assessed_risk, new_risk


def manager(client, db):
    create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")


def item(body, code):
    return next(i for i in body["items"] if i["code"] == code)


def test_soa_lists_every_control_with_risk_justifications(client, db, seeded):
    manager(client, db)
    client.put(f"/api/v1/risks/{new_risk(client)['code']}/controls", json={"links": [{"code": "A.8.13"}]})
    body = client.get("/api/v1/soa").json()
    assert len(body["items"]) == 93
    backup = item(body, "A.8.13")
    assert backup["sources"] == [{"kind": "risk", "label": "Risk R-001", "ref": "R-001"}]
    assert (backup["evidence_verified"], backup["evidence_required"]) == (0, 3)
    assert "A.8.13" not in body["checks"]["orphans"] and len(body["checks"]["orphans"]) == 92
    assert body["checks"]["ok"] is False


def test_bulk_sources_clear_orphans(client, db, seeded):
    manager(client, db)
    codes = [i["code"] for i in client.get("/api/v1/soa").json()["items"]]
    body = client.patch(
        "/api/v1/soa/items",
        json={"codes": codes, "sources": ["legal", "best_practice"], "justification": "Baseline for a regulated bank."},
    ).json()
    assert body["checks"] == {"orphans": [], "excluded_mitigating": [], "untreated_risks": [], "ok": True}
    assert body["items"][0]["sources"] == [
        {"kind": "best_practice", "label": "Best practice", "ref": None},
        {"kind": "legal", "label": "Legal or regulatory", "ref": None},
    ]
    assert body["items"][0]["justification"] == "Baseline for a regulated bank."


def test_excluding_needs_a_reason_and_drops_the_control(client, db, seeded):
    manager(client, db)
    response = client.patch("/api/v1/soa/items", json={"codes": ["A.8.30"], "applicable": False})
    assert response.status_code == 422 and response.json() == {"detail": "Give a reason for excluding a control."}
    body = client.patch(
        "/api/v1/soa/items",
        json={"codes": ["A.8.30"], "applicable": False, "exclusion_reason": "All development is done in-house."},
    ).json()
    excluded = item(body, "A.8.30")
    assert (excluded["applicable"], excluded["status"]) == (False, "excluded")
    assert "A.8.30" not in body["checks"]["orphans"]
    assert client.get("/api/v1/controls/A.8.30").json()["status"] == "excluded"
    assert db.scalar(select(AuditLog).where(AuditLog.action == "soa.update")).diff["applicable"] == [True, False]
    back = client.patch("/api/v1/soa/items", json={"codes": ["A.8.30"], "applicable": True}).json()
    assert item(back, "A.8.30")["status"] == "not_started"


def test_excluding_a_control_that_mitigates_a_risk_is_refused(client, db, seeded):
    manager(client, db)
    for _ in range(2):
        client.put(f"/api/v1/risks/{new_risk(client)['code']}/controls", json={"links": [{"code": "A.8.13"}]})
    response = client.patch(
        "/api/v1/soa/items", json={"codes": ["A.8.13"], "applicable": False, "exclusion_reason": "x"}
    )
    assert response.status_code == 409
    assert response.json() == {
        "detail": "A.8.13 mitigates R-001, R-002. Unlink it from those risks or change their treatment first."
    }


def test_excluded_control_that_mitigates_a_risk_is_reported(client, db, seeded):
    manager(client, db)
    client.put(f"/api/v1/risks/{new_risk(client)['code']}/controls", json={"links": [{"code": "A.8.13"}]})
    control = db.scalar(select(Control).where(Control.code == "A.8.13"))
    control.applicable, control.exclusion_reason = False, "x"
    db.commit()
    checks = client.get("/api/v1/soa").json()["checks"]
    assert checks["excluded_mitigating"] == [{"code": "A.8.13", "risks": ["R-001"]}]


def test_untreated_risks_above_appetite_are_reported(client, db, seeded, clock):
    manager(client, db)
    high = assessed_risk(client, likelihood=4, consequence=4)["code"]
    assessed_risk(client, likelihood=1, consequence=2)
    assert client.get("/api/v1/soa").json()["checks"]["untreated_risks"] == [high]
    client.post(f"/api/v1/risks/{high}/treatment", json={"option": "modify"})
    assert client.get("/api/v1/soa").json()["checks"]["untreated_risks"] == []


def test_soa_permissions(client, db, seeded):
    manager(client, db)
    response = client.patch("/api/v1/soa/items", json={"codes": ["A.9.99"], "sources": ["legal"]})
    assert response.status_code == 404 and response.json() == {"detail": "Control A.9.99 not found."}
    for email, role in (("viewer@acme.com", "viewer"), ("tariq@acme.com", "executive")):
        create_user(db, email, roles=((role, None),))
        sign_in(client, email)
        assert client.get("/api/v1/soa").status_code == 200
        assert client.patch("/api/v1/soa/items", json={"codes": ["A.5.1"], "sources": ["legal"]}).status_code == 403
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_soa_api.py tests/test_scoring.py`
Expected: FAIL — `test_excluded_controls_drop_out_of_readiness` asserts `"excluded"` but gets `"in_progress"`/`"not_started"`, and the SoA routes return 404.

- [ ] **Step 3: Make scoring respect the SoA**

In `backend/src/assayr/scoring/service.py`, inside `recompute_control`, replace the line that calls `evaluate(...)` with:
```python
    if not control.applicable:
        result = ControlScore(status="excluded", score=0.0, views=views, attested=attested)
    else:
        result = evaluate(control.implementation_status, views, attested, has_any_link)
```
and replace `control.score = result.score` with:
```python
    control.score = None if result.status == "excluded" else result.score
```

- [ ] **Step 4: Implement the SoA working view**

`backend/src/assayr/soa/schemas.py`:
```python
from typing import Literal

from pydantic import BaseModel, Field

SourceKind = Literal["legal", "contractual", "business", "best_practice"]
MANUAL_SOURCES = {
    "legal": "Legal or regulatory",
    "contractual": "Contractual",
    "business": "Business requirement",
    "best_practice": "Best practice",
}


class SourceOut(BaseModel):
    kind: str
    label: str
    ref: str | None = None


class SoaItemOut(BaseModel):
    code: str
    title: str
    theme: str | None
    applicable: bool
    sources: list[SourceOut]
    justification: str | None
    exclusion_reason: str | None
    implementation_status: str
    status: str
    evidence_verified: int
    evidence_required: int
    owner: str | None


class ExcludedMitigatingOut(BaseModel):
    code: str
    risks: list[str]


class SoaChecksOut(BaseModel):
    orphans: list[str]
    excluded_mitigating: list[ExcludedMitigatingOut]
    untreated_risks: list[str]
    ok: bool


class SoaOut(BaseModel):
    items: list[SoaItemOut]
    checks: SoaChecksOut


class SoaItemsIn(BaseModel):
    codes: list[str] = Field(min_length=1, max_length=200)
    applicable: bool | None = None
    sources: list[SourceKind] | None = Field(None, max_length=4)
    justification: str | None = Field(None, max_length=5000)
    exclusion_reason: str | None = Field(None, max_length=2000)
```

`backend/src/assayr/soa/service.py`:
```python
"""The working Statement of Applicability: applicability, justification sources and traceability checks."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.catalogue.models import Control
from assayr.config import Settings
from assayr.risk.methodology import band_for
from assayr.risk.models import Risk, RiskControl
from assayr.risk.service import definition_of, latest_assessment
from assayr.scoring.service import slot_views
from assayr.soa.schemas import MANUAL_SOURCES, ExcludedMitigatingOut, SoaChecksOut, SoaItemOut, SoaOut, SourceOut


def active_risk_links(db: Session, scope_id: uuid.UUID) -> dict[uuid.UUID, list[str]]:
    """Control id → codes of the open risks that list it as a mitigating control."""
    rows = db.execute(
        select(RiskControl.control_id, Risk.code)
        .join(Risk, RiskControl.risk_id == Risk.id)
        .where(Risk.scope_id == scope_id, Risk.closed_at.is_(None))
        .order_by(Risk.seq)
    )
    links: dict[uuid.UUID, list[str]] = {}
    for control_id, code in rows:
        links.setdefault(control_id, []).append(code)
    return links


def untreated_risks(db: Session, scope_id: uuid.UUID) -> list[str]:
    """Open risks whose current level is above appetite and that have no treatment decision."""
    codes = []
    for risk in db.scalars(
        select(Risk).where(Risk.scope_id == scope_id, Risk.closed_at.is_(None)).order_by(Risk.seq)
    ).unique():
        latest = latest_assessment(db, risk)
        if latest is None or risk.treatment_option is not None:
            continue
        if band_for(definition_of(db, latest), latest.current_l, latest.current_c)["above_appetite"]:
            codes.append(risk.code)
    return codes


def soa_items(db: Session, scope_id: uuid.UUID, settings: Settings, today: date) -> list[SoaItemOut]:
    links = active_risk_links(db, scope_id)
    items = []
    for control in db.scalars(
        select(Control).where(Control.scope_id == scope_id).order_by(Control.sort_order)
    ).unique():
        sources = [SourceOut(kind="risk", label=f"Risk {code}", ref=code) for code in links.get(control.id, [])]
        sources += [
            SourceOut(kind=kind, label=MANUAL_SOURCES[kind])
            for kind in (control.soa_sources or [])
            if kind in MANUAL_SOURCES
        ]
        required = [v for v in slot_views(db, control, today, settings) if v.required]
        items.append(
            SoaItemOut(
                code=control.code,
                title=control.title,
                theme=control.theme,
                applicable=control.applicable,
                sources=sources,
                justification=control.soa_justification,
                exclusion_reason=control.exclusion_reason,
                implementation_status=control.implementation_status,
                status=control.status,
                evidence_verified=sum(v.state in ("verified", "expiring") for v in required),
                evidence_required=len(required),
                owner=control.owner.full_name if control.owner else None,
            )
        )
    return items


def soa_checks(items: list[SoaItemOut], untreated: list[str]) -> SoaChecksOut:
    orphans = [i.code for i in items if i.applicable and not i.sources]
    excluded = [
        ExcludedMitigatingOut(code=i.code, risks=[s.ref for s in i.sources if s.kind == "risk"])
        for i in items
        if not i.applicable and any(s.kind == "risk" for s in i.sources)
    ]
    return SoaChecksOut(
        orphans=orphans,
        excluded_mitigating=excluded,
        untreated_risks=untreated,
        ok=not orphans and not excluded and not untreated,
    )


def soa_view(db: Session, scope_id: uuid.UUID, settings: Settings, today: date) -> SoaOut:
    items = soa_items(db, scope_id, settings, today)
    return SoaOut(items=items, checks=soa_checks(items, untreated_risks(db, scope_id)))
```

`backend/src/assayr/soa/router.py`:
```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.catalogue.access import has_perm
from assayr.catalogue.models import Control
from assayr.catalogue.router import FORBIDDEN, resolve_scope
from assayr.db import get_session
from assayr.identity.deps import actor_for, current_user, get_clock, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm
from assayr.scoring.service import recompute_control
from assayr.soa.schemas import SoaItemsIn, SoaOut
from assayr.soa.service import active_risk_links, soa_view

router = APIRouter(tags=["statement of applicability"])


@router.get("/soa", response_model=SoaOut)
def get_soa(
    request: Request,
    grant: Grant = Depends(require(Perm.SOA_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> SoaOut:
    scope = resolve_scope(db, scope_id, grant)
    return soa_view(db, scope.id, request.app.state.settings, get_clock(request)().date())


@router.patch("/soa/items", response_model=SoaOut)
def update_soa_items(
    body: SoaItemsIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.SOA_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> SoaOut:
    scope = resolve_scope(db, scope_id, grant)
    if not has_perm(user, scope.id, Perm.SOA_WRITE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    codes = list(dict.fromkeys(body.codes))
    controls = {
        c.code: c for c in db.scalars(select(Control).where(Control.scope_id == scope.id, Control.code.in_(codes))).unique()
    }
    for code in codes:
        if code not in controls:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Control {code} not found.")
    fields = body.model_fields_set
    if "applicable" in fields and body.applicable is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Applicable can't be empty.")
    if body.applicable is False:
        links = active_risk_links(db, scope.id)
        for code in codes:
            reason = body.exclusion_reason if "exclusion_reason" in fields else controls[code].exclusion_reason
            if not (reason or "").strip():
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Give a reason for excluding a control.")
            risks = links.get(controls[code].id)
            if risks:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"{code} mitigates {', '.join(risks)}. Unlink it from those risks or change their treatment first.",
                )
    settings = request.app.state.settings
    now = get_clock(request)()
    for code in codes:
        control = controls[code]
        diff: dict[str, list] = {}
        if "applicable" in fields and body.applicable != control.applicable:
            diff["applicable"] = [control.applicable, body.applicable]
            control.applicable = body.applicable
        if "sources" in fields:
            new_sources = sorted(set(body.sources or []))
            if new_sources != sorted(control.soa_sources or []):
                diff["sources"] = [sorted(control.soa_sources or []), new_sources]
                control.soa_sources = new_sources
        for name, attr in (("justification", "soa_justification"), ("exclusion_reason", "exclusion_reason")):
            if name in fields:
                value = (getattr(body, name) or "").strip() or None
                if value != getattr(control, attr):
                    diff[name] = [getattr(control, attr), value]
                    setattr(control, attr, value)
        if not diff:
            continue
        record(db, actor_for(request, user), "soa.update", "control", code, diff=diff)
        if "applicable" in diff:
            trigger = (
                "Included in the Statement of Applicability"
                if control.applicable
                else "Excluded in the Statement of Applicability"
            )
            recompute_control(db, control, now, settings, trigger=trigger)
    db.commit()
    return soa_view(db, scope.id, settings, now.date())
```

In `backend/src/assayr/main.py` add `from assayr.soa.router import router as soa_router` and `app.include_router(soa_router, prefix="/api/v1")`.

- [ ] **Step 5: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest -W error`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(soa): applicability, justification sources and traceability checks"
```

---

### Task 11: SoA versions — submit, approve or return, and export

**Files:**
- Modify: `backend/src/assayr/soa/router.py`
- Test: `backend/tests/test_soa_versions.py`

**Interfaces:**
- Consumes: `SoaVersion` (Task 2); `soa_view`, `SoaItemOut` (Task 10); `add_sheet`, `xlsx_response` (Task 9).
- Produces: `SoaVersionSummaryOut {version_no, status, prepared_by, prepared_at, decided_by, decided_at, decision_note, applicable, excluded}`; `SoaVersionOut` (+ `entries: list[SoaItemOut]`); `GET /api/v1/soa/versions`; `POST /api/v1/soa/versions` (201; needs clean checks and no pending version); `GET /api/v1/soa/versions/{version_no}`; `POST /api/v1/soa/versions/{version_no}/approve`; `POST /api/v1/soa/versions/{version_no}/return` (`{reason}`); `GET /api/v1/soa/versions/{version_no}/export.xlsx`; `GET /api/v1/soa/export.xlsx` (working copy).

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_soa_versions.py`:
```python
import io

import openpyxl
from sqlalchemy import select

from assayr.audit.models import AuditLog
from tests.conftest import create_user, sign_in


def manager(client, db):
    create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")


def executive(client, db):
    create_user(db, "tariq@acme.com", roles=(("executive", None),), full_name="Tariq Qureshi")


def justify_everything(client):
    codes = [i["code"] for i in client.get("/api/v1/soa").json()["items"]]
    client.patch("/api/v1/soa/items", json={"codes": codes, "sources": ["best_practice"]})


def test_submission_needs_clean_checks(client, db, seeded):
    manager(client, db)
    response = client.post("/api/v1/soa/versions")
    assert response.status_code == 409
    assert response.json() == {
        "detail": "Fix the traceability issues before submitting: 93 applicable controls without a justification."
    }


def test_approved_version_is_frozen(client, db, seeded):
    executive(client, db)
    manager(client, db)
    justify_everything(client)
    created = client.post("/api/v1/soa/versions")
    assert created.status_code == 201
    first = created.json()
    assert (first["version_no"], first["status"], first["applicable"], first["excluded"]) == (1, "pending", 93, 0)
    response = client.post("/api/v1/soa/versions")
    assert response.status_code == 409
    assert response.json() == {"detail": "Version 1 is already waiting for approval."}
    sign_in(client, "tariq@acme.com")
    approved = client.post("/api/v1/soa/versions/1/approve").json()
    assert (approved["status"], approved["decided_by"]) == ("approved", "Tariq Qureshi")
    response = client.post("/api/v1/soa/versions/1/approve")
    assert response.status_code == 409
    assert response.json() == {"detail": "Only a version waiting for approval can be approved."}
    assert client.post("/api/v1/soa/versions/1/return", json={"reason": "x"}).status_code == 409
    sign_in(client, "sana@acme.com")
    client.patch(
        "/api/v1/soa/items",
        json={"codes": ["A.8.30"], "applicable": False, "exclusion_reason": "All development is in-house."},
    )
    frozen = client.get("/api/v1/soa/versions/1").json()
    assert next(e for e in frozen["entries"] if e["code"] == "A.8.30")["applicable"] is True
    second = client.post("/api/v1/soa/versions").json()
    assert (second["version_no"], second["excluded"]) == (2, 1)
    assert [v["version_no"] for v in client.get("/api/v1/soa/versions").json()] == [2, 1]
    actions = [e.action for e in db.scalars(select(AuditLog).where(AuditLog.action.like("soa.%")))]
    assert actions.count("soa.submit") == 2 and actions.count("soa.approve") == 1


def test_preparer_cannot_approve_their_own_version(client, db, seeded):
    create_user(db, "sana@acme.com", roles=(("isms_manager", None), ("executive", None)), full_name="Sana Malik")
    sign_in(client, "sana@acme.com")
    justify_everything(client)
    client.post("/api/v1/soa/versions")
    response = client.post("/api/v1/soa/versions/1/approve")
    assert response.status_code == 403
    assert response.json() == {"detail": "You prepared this version, so someone else must approve it."}


def test_executive_returns_a_version_with_a_reason(client, db, seeded):
    executive(client, db)
    manager(client, db)
    justify_everything(client)
    client.post("/api/v1/soa/versions")
    sign_in(client, "tariq@acme.com")
    returned = client.post("/api/v1/soa/versions/1/return", json={"reason": "Explain why A.5.7 applies."}).json()
    assert (returned["status"], returned["decision_note"]) == ("returned", "Explain why A.5.7 applies.")
    sign_in(client, "sana@acme.com")
    assert client.post("/api/v1/soa/versions").json()["version_no"] == 2


def test_only_executives_decide(client, db, seeded):
    manager(client, db)
    justify_everything(client)
    client.post("/api/v1/soa/versions")
    assert client.post("/api/v1/soa/versions/1/approve").status_code == 403
    assert client.get("/api/v1/soa/versions/9").status_code == 404


def test_soa_export_lists_every_control(client, db, seeded):
    manager(client, db)
    justify_everything(client)
    client.patch("/api/v1/soa/items", json={"codes": ["A.5.1"], "justification": '=cmd|" /C calc"!A0'})
    client.post("/api/v1/soa/versions")
    response = client.get("/api/v1/soa/versions/1/export.xlsx")
    assert response.status_code == 200 and response.headers["content-disposition"].startswith("attachment")
    book = openpyxl.load_workbook(io.BytesIO(response.content))
    sheet = book["SoA v1"]
    assert sheet.max_row == 94
    assert [c.value for c in sheet[1]][:4] == ["Control", "Title", "Theme", "Applicable"]
    assert (sheet["A2"].value, sheet["D2"].value) == ("A.5.1", "Yes")
    assert sheet["F2"].value == '\'=cmd|" /C calc"!A0'
    approval = {row[0].value: row[1].value for row in book["Approval"].iter_rows(min_row=2)}
    assert (approval["Version"], approval["Status"], approval["Prepared by"]) == (1, "Pending", "Sana Malik")
    working = client.get("/api/v1/soa/export.xlsx")
    assert openpyxl.load_workbook(io.BytesIO(working.content))["SoA (working)"].max_row == 94
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_soa_versions.py`
Expected: FAIL — 404/405 on the version routes.

- [ ] **Step 3: Implement**

In `backend/src/assayr/soa/router.py` extend the imports with `from datetime import datetime`, `from fastapi.responses import Response`, `from openpyxl import Workbook`, `from pydantic import BaseModel, Field`, `from sqlalchemy import func`, `from assayr.exports import add_sheet, xlsx_response`, `from assayr.soa.models import SoaVersion`, `from assayr.soa.schemas import SoaItemOut`, and append:
```python
class SoaVersionSummaryOut(BaseModel):
    version_no: int
    status: str
    prepared_by: str | None
    prepared_at: datetime
    decided_by: str | None
    decided_at: datetime | None
    decision_note: str | None
    applicable: int
    excluded: int


class SoaVersionOut(SoaVersionSummaryOut):
    entries: list[SoaItemOut]


class ReturnIn(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


def _name(db: Session, user_id: uuid.UUID | None) -> str | None:
    person = db.get(User, user_id) if user_id else None
    return person.full_name if person else None


def _summary(db: Session, version: SoaVersion) -> SoaVersionSummaryOut:
    applicable = sum(1 for e in version.entries if e["applicable"])
    return SoaVersionSummaryOut(
        version_no=version.version_no,
        status=version.status,
        prepared_by=_name(db, version.prepared_by_id),
        prepared_at=version.prepared_at,
        decided_by=_name(db, version.decided_by_id),
        decided_at=version.decided_at,
        decision_note=version.decision_note,
        applicable=applicable,
        excluded=len(version.entries) - applicable,
    )


def _full(db: Session, version: SoaVersion) -> SoaVersionOut:
    return SoaVersionOut(**_summary(db, version).model_dump(), entries=version.entries)


def _load_version(db: Session, scope_id: uuid.UUID, version_no: int) -> SoaVersion:
    version = db.scalar(
        select(SoaVersion).where(SoaVersion.scope_id == scope_id, SoaVersion.version_no == version_no)
    )
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SoA version not found.")
    return version


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


@router.get("/soa/versions", response_model=list[SoaVersionSummaryOut])
def list_versions(
    grant: Grant = Depends(require(Perm.SOA_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> list[SoaVersionSummaryOut]:
    scope = resolve_scope(db, scope_id, grant)
    versions = db.scalars(
        select(SoaVersion).where(SoaVersion.scope_id == scope.id).order_by(SoaVersion.version_no.desc())
    )
    return [_summary(db, v) for v in versions]


@router.post("/soa/versions", response_model=SoaVersionOut, status_code=status.HTTP_201_CREATED)
def submit_version(
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.SOA_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> SoaVersionOut:
    scope = resolve_scope(db, scope_id, grant)
    if not has_perm(user, scope.id, Perm.SOA_WRITE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    pending = db.scalar(select(SoaVersion).where(SoaVersion.scope_id == scope.id, SoaVersion.status == "pending"))
    if pending is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Version {pending.version_no} is already waiting for approval.")
    now = get_clock(request)()
    view = soa_view(db, scope.id, request.app.state.settings, now.date())
    if not view.checks.ok:
        problems = []
        if view.checks.orphans:
            problems.append(f"{_plural(len(view.checks.orphans), 'applicable control')} without a justification")
        if view.checks.excluded_mitigating:
            problems.append(f"{_plural(len(view.checks.excluded_mitigating), 'excluded control')} that mitigate a risk")
        if view.checks.untreated_risks:
            problems.append(f"{_plural(len(view.checks.untreated_risks), 'risk')} above appetite without a treatment")
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Fix the traceability issues before submitting: {'; '.join(problems)}."
        )
    number = (db.scalar(select(func.max(SoaVersion.version_no)).where(SoaVersion.scope_id == scope.id)) or 0) + 1
    version = SoaVersion(
        scope_id=scope.id,
        version_no=number,
        status="pending",
        entries=[item.model_dump(mode="json") for item in view.items],
        prepared_by_id=user.id,
        prepared_at=now,
    )
    db.add(version)
    db.flush()
    record(db, actor_for(request, user), "soa.submit", "soa_version", str(number), diff={"controls": len(view.items)})
    db.commit()
    return _full(db, version)


@router.get("/soa/versions/{version_no}", response_model=SoaVersionOut)
def get_version(
    version_no: int,
    grant: Grant = Depends(require(Perm.SOA_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> SoaVersionOut:
    scope = resolve_scope(db, scope_id, grant)
    return _full(db, _load_version(db, scope.id, version_no))


def _decide(db: Session, request: Request, user: User, version: SoaVersion, outcome: str, note: str | None) -> None:
    verb = "approved" if outcome == "approved" else "returned"
    if version.status != "pending":
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Only a version waiting for approval can be {verb}."
        )
    if outcome == "approved" and version.prepared_by_id == user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You prepared this version, so someone else must approve it.")
    version.status = outcome
    version.decided_by_id = user.id
    version.decided_at = get_clock(request)()
    version.decision_note = note
    action = "soa.approve" if outcome == "approved" else "soa.return"
    record(db, actor_for(request, user), action, "soa_version", str(version.version_no), reason=note)
    db.commit()


@router.post("/soa/versions/{version_no}/approve", response_model=SoaVersionOut)
def approve_version(
    version_no: int,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.SOA_APPROVE)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> SoaVersionOut:
    scope = resolve_scope(db, scope_id, grant)
    version = _load_version(db, scope.id, version_no)
    _decide(db, request, user, version, "approved", None)
    return _full(db, version)


@router.post("/soa/versions/{version_no}/return", response_model=SoaVersionOut)
def return_version(
    version_no: int,
    body: ReturnIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.SOA_APPROVE)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> SoaVersionOut:
    scope = resolve_scope(db, scope_id, grant)
    version = _load_version(db, scope.id, version_no)
    _decide(db, request, user, version, "returned", body.reason.strip())
    return _full(db, version)


SOA_HEADER = [
    "Control",
    "Title",
    "Theme",
    "Applicable",
    "Justification sources",
    "Justification",
    "Exclusion reason",
    "Implementation",
    "Status",
    "Evidence verified",
    "Owner",
]


def _soa_rows(entries: list[dict]) -> list[list]:
    return [
        [
            e["code"],
            e["title"],
            e["theme"],
            "Yes" if e["applicable"] else "No",
            "; ".join(s["label"] for s in e["sources"]),
            e["justification"],
            e["exclusion_reason"],
            e["implementation_status"].replace("_", " "),
            e["status"].replace("_", " "),
            f"{e['evidence_verified']} of {e['evidence_required']}",
            e["owner"],
        ]
        for e in entries
    ]


@router.get("/soa/versions/{version_no}/export.xlsx")
def export_version(
    version_no: int,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.SOA_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> Response:
    scope = resolve_scope(db, scope_id, grant)
    version = _load_version(db, scope.id, version_no)
    summary = _summary(db, version)
    workbook = Workbook()
    add_sheet(workbook, f"SoA v{version.version_no}", SOA_HEADER, _soa_rows(version.entries))
    add_sheet(
        workbook,
        "Approval",
        ["Field", "Value"],
        [
            ["Version", summary.version_no],
            ["Status", summary.status.capitalize()],
            ["Prepared by", summary.prepared_by],
            ["Prepared at", summary.prepared_at.isoformat()],
            ["Decided by", summary.decided_by],
            ["Decided at", summary.decided_at.isoformat() if summary.decided_at else None],
            ["Decision note", summary.decision_note],
        ],
    )
    record(db, actor_for(request, user), "soa.export", "soa_version", str(version.version_no))
    db.commit()
    return xlsx_response(workbook, f"statement-of-applicability-v{version.version_no}.xlsx")


@router.get("/soa/export.xlsx")
def export_working(
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.SOA_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> Response:
    scope = resolve_scope(db, scope_id, grant)
    view = soa_view(db, scope.id, request.app.state.settings, get_clock(request)().date())
    workbook = Workbook()
    add_sheet(workbook, "SoA (working)", SOA_HEADER, _soa_rows([i.model_dump() for i in view.items]))
    record(db, actor_for(request, user), "soa.export", "soa_version", "working")
    db.commit()
    return xlsx_response(workbook, "statement-of-applicability-working.xlsx")
```

- [ ] **Step 4: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest -W error`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(soa): versioned approval with separation of duties and spreadsheet export"
```

---
### Task 12: Frontend — risk register, risk detail and snapshots

**Files:**
- Modify: `frontend/src/styles/tokens.css`, `frontend/src/styles/global.css`, `frontend/src/api/types.ts`, `frontend/src/test/render.tsx`, `frontend/src/components/AppShell.tsx`, `frontend/src/router.tsx`
- Create: `frontend/src/api/risks.ts`, `frontend/src/api/assets.ts`, `frontend/src/api/people.ts`, `frontend/src/components/LevelPill.tsx`, `frontend/src/components/Heatmap.tsx`, `frontend/src/components/Segmented.tsx`, `frontend/src/test/fixtures.ts`, `frontend/src/pages/Risks.tsx`, `frontend/src/pages/RiskDetail.tsx`, `frontend/src/pages/RiskSnapshots.tsx`
- Test: `frontend/src/components/Heatmap.test.tsx`, `frontend/src/pages/Risks.test.tsx`, `frontend/src/pages/RiskDetail.test.tsx`, `frontend/src/pages/RiskSnapshots.test.tsx`

**Interfaces:**
- Consumes: backend Tasks 4–9 and the people/asset APIs.
- Produces: types `Level`, `Band`, `Methodology`, `LibraryItem`, `RiskTemplate`, `RiskLibrary`, `RiskRow`, `Assessment`, `RiskTask`, `RiskAcceptance`, `RiskDetail`, `SnapshotSummary`, `SnapshotCompare`, `Asset`, `Person`; hooks `useMethodology`, `useRiskLibrary`, `useRisks({q, mine})`, `useRisk(code)`, `useAllControls()`, `useCreateRisk()`, `useUpdateRisk(code)`, `useSetRiskControls(code)`, `useSaveAssessment(code)`, `useFinalizeAssessment(code)`, `useSetTreatment(code)`, `useAddAction(code)`, `useUpdateTask(code)`, `useAcceptRisk(code)`, `useCloseRisk(code)`, `useSnapshots()`, `useCreateSnapshot()`, `useSnapshotCompare(base, head)`, `usePeople()`, `useAssets(includeRetired)`, `useCreateAsset()`, `useUpdateAsset()`; labels `RISK_STATUS_LABEL`, `TREATMENT_LABEL`, `AUTHORITY_LABEL`, `TASK_STATUS_LABEL`, `ASSET_TYPE_LABEL`, `CLASSIFICATION_LABEL`, `LIFECYCLE_LABEL`; components `LevelPill({level})`, `RiskStatusPill({status})`, `HEAT`, `Heatmap({points, bands, selected?, onSelect?, marker?, size?})`, `Segmented({label, options, value, onChange})`; test fixtures `METHODOLOGY`, `level(l, c)`, `riskRow(overrides)`, `riskDetail(overrides)`; routes `/risks`, `/risks/snapshots`, `/risks/$code`; Risks nav item enabled.

- [ ] **Step 1: Write the failing tests**

`frontend/src/test/fixtures.ts`:
```ts
import type { Band, Level, Methodology, RiskDetail, RiskRow } from "../api/types"

const BANDS: Band[] = [
  { key: "very_low", label: "Very low", min: 1, max: 3, above_appetite: false, treatment_required: false,
    authority: "risk_owner", review_days: 365, rule: "Accept; the risk owner is aware." },
  { key: "low", label: "Low", min: 4, max: 6, above_appetite: false, treatment_required: false,
    authority: "risk_owner", review_days: 365, rule: "Accept by the risk owner." },
  { key: "medium", label: "Medium", min: 7, max: 10, above_appetite: true, treatment_required: false,
    authority: "risk_owner", review_days: 182, rule: "Treat, or accept with the risk owner's justification." },
  { key: "high", label: "High", min: 11, max: 16, above_appetite: true, treatment_required: true,
    authority: "isms_manager", review_days: 90,
    rule: "A treatment plan is required; the residual risk is accepted by an ISMS manager." },
  { key: "critical", label: "Critical", min: 17, max: 25, above_appetite: true, treatment_required: true,
    authority: "executive", review_days: 31, rule: "Treat immediately; only top management can accept the residual risk." },
]
const DIMENSIONS: [string, string][] = [
  ["financial", "Financial"], ["operational", "Operational"], ["legal", "Legal / regulatory"],
  ["reputation", "Reputation"], ["data", "Data (C/I/A)"],
]

export const METHODOLOGY: Methodology = {
  version_no: 1,
  name: "Assayr default (ISO/IEC 27005:2022)",
  likelihood: ["Rare", "Unlikely", "Possible", "Likely", "Almost certain"].map((label, i) => ({
    level: i + 1, label, guidance: `Likelihood guidance ${i + 1}`,
  })),
  consequence: {
    levels: ["Negligible", "Minor", "Moderate", "Major", "Severe"].map((label, i) => ({ level: i + 1, label })),
    dimensions: DIMENSIONS.map(([key, label]) => ({
      key, label, guidance: [1, 2, 3, 4, 5].map((n) => `${label} guidance ${n}`),
    })),
  },
  bands: BANDS,
}

export function level(likelihood: number, consequence: number): Level {
  const score = likelihood * consequence
  const band = BANDS.find((b) => score >= b.min && score <= b.max)!
  return { likelihood, consequence, score, band: band.key, band_label: band.label }
}

export function riskRow(overrides: Partial<RiskRow> = {}): RiskRow {
  return {
    id: "r1", code: "R-001", title: "Ransomware encrypts file servers", category: "Cyber attack",
    approach: "event", owner: { id: "u1", full_name: "Sana Malik" }, status: "assessed",
    inherent: level(4, 5), current: level(4, 4), target: level(2, 4), treatment_option: null,
    progress: { done: 0, total: 0 }, review_due: "2027-01-06", acceptance_expires: null,
    ...overrides,
  }
}

export function riskDetail(overrides: Partial<RiskDetail> = {}): RiskDetail {
  return {
    ...riskRow(),
    description: "Ransomware enters through an unpatched system and encrypts file servers.",
    template_code: "RT01",
    threats: [{ code: "T01", name: "Ransomware" }],
    vulnerabilities: [{ code: "V17", name: "No backups, or backups never tested" }],
    assets: [],
    controls: [{ code: "A.8.13", title: "Information backup", status: "compliant", axis: "likelihood" }],
    draft: null, latest: null, history: [],
    treatment: { option: null, note: null, budget: null, due: null },
    actions: [], acceptance: null, required_authority: "isms_manager", can_accept: true, can_edit: true,
    closed_at: null, close_reason: null,
    ...overrides,
  }
}
```

In `frontend/src/test/render.tsx` change `ME.permissions` to:
```ts
  permissions: [
    "assets:read", "assets:write", "audit_log:read", "controls:read", "controls:write", "evidence:review",
    "risks:accept_high", "risks:read", "risks:write", "soa:read", "soa:write",
  ],
```

`frontend/src/components/Heatmap.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { METHODOLOGY } from "../test/fixtures"
import { Heatmap } from "./Heatmap"

test("cells show how many risks sit at each position and can be selected", async () => {
  const onSelect = vi.fn()
  const points = [
    { code: "R-001", title: "a", likelihood: 4, consequence: 4 },
    { code: "R-002", title: "b", likelihood: 4, consequence: 4 },
  ]
  render(<Heatmap points={points} bands={METHODOLOGY.bands} onSelect={onSelect} />)
  const cell = screen.getByRole("button", { name: "Likelihood 4, consequence 4: 2 risks" })
  expect(cell).toHaveTextContent("2")
  expect(screen.getByRole("button", { name: "Likelihood 1, consequence 1: 0 risks" })).toHaveTextContent("")
  await userEvent.click(cell)
  expect(onSelect).toHaveBeenCalledWith([4, 4])
})
```

`frontend/src/pages/Risks.test.tsx`:
```tsx
import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { level, METHODOLOGY, riskRow } from "../test/fixtures"
import { json, ME, mockApi, renderApp } from "../test/render"

const ROWS = [
  riskRow(),
  riskRow({ id: "r2", code: "R-002", title: "Laptop theft", status: "accepted", inherent: level(4, 3),
    current: level(2, 3), target: level(2, 3) }),
  riskRow({ id: "r3", code: "R-003", title: "New supplier", status: "draft", inherent: null, current: null,
    target: null }),
]

function mockRisks() {
  return mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /risks": () => json(200, ROWS),
    "GET /risk-methodology": () => json(200, METHODOLOGY),
  })
}

test("the table lists risks with their levels", async () => {
  mockRisks()
  renderApp("/risks")
  const row = (await screen.findByRole("link", { name: "Ransomware encrypts file servers" })).closest("tr")!
  expect(row).toHaveTextContent("Critical 20")
  expect(row).toHaveTextContent("High 16")
  expect(row).toHaveTextContent("Medium 8")
  expect(screen.getByRole("link", { name: "New supplier" }).closest("tr")).toHaveTextContent("Draft")
})

test("the heatmap counts risks per cell and lists the risks of a selected cell", async () => {
  mockRisks()
  renderApp("/risks")
  await userEvent.click(await screen.findByRole("button", { name: "Heatmap" }))
  await userEvent.click(screen.getByRole("button", { name: "Likelihood 4, consequence 4: 1 risk" }))
  const selected = screen.getByRole("region", { name: "Selected cell" })
  expect(within(selected).getByRole("link", { name: "Ransomware encrypts file servers" })).toBeInTheDocument()
  await userEvent.click(screen.getByRole("button", { name: "Inherent" }))
  expect(screen.getByRole("button", { name: "Likelihood 4, consequence 5: 1 risk" })).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Likelihood 4, consequence 3: 1 risk" })).toBeInTheDocument()
})

test("the board groups risks by status", async () => {
  mockRisks()
  renderApp("/risks")
  await userEvent.click(await screen.findByRole("button", { name: "Board" }))
  expect(within(screen.getByRole("region", { name: "Accepted" })).getByText("Laptop theft")).toBeInTheDocument()
  expect(within(screen.getByRole("region", { name: "Draft" })).getByText("New supplier")).toBeInTheDocument()
})
```

`frontend/src/pages/RiskDetail.test.tsx`:
```tsx
import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { level, riskDetail } from "../test/fixtures"
import { json, ME, mockApi, renderApp } from "../test/render"

const base = { "GET /auth/me": () => json(200, ME), "GET /people": () => json(200, []) }

test("shows the levels and controls, and the owner accepts the residual risk", async () => {
  const calls = mockApi({
    ...base,
    "GET /risks/R-001": () => json(200, riskDetail()),
    "POST /risks/R-001/accept": () => json(200, riskDetail({
      status: "accepted", can_accept: false,
      acceptance: { band: "high", score: 16, authority: "isms_manager", statement: "Accepted for now.",
        accepted_by: "Sana Malik", accepted_at: "2026-10-08T09:00:00Z", expires_at: "2027-10-08T09:00:00Z" },
    })),
  })
  renderApp("/risks/R-001")
  expect(await screen.findByRole("heading", { name: "Ransomware encrypts file servers" })).toBeInTheDocument()
  const levels = screen.getByRole("region", { name: "Risk levels" })
  expect(levels).toHaveTextContent("Critical 20")
  expect(levels).toHaveTextContent("High 16")
  expect(levels).toHaveTextContent("Medium 8")
  expect(screen.getByRole("link", { name: "Information backup" })).toBeInTheDocument()
  await userEvent.type(screen.getByLabelText("Acceptance statement"), "Accepted for now.")
  await userEvent.click(screen.getByRole("button", { name: "Accept residual risk" }))
  expect(await screen.findByText(/Accepted by Sana Malik on 8 Oct 2026, valid until 8 Oct 2027/)).toBeInTheDocument()
  const post = calls.find((c) => c.method === "POST")!
  expect(JSON.parse(String(post.init.body))).toEqual({ statement: "Accepted for now." })
})

test("explains who has to accept when the user can't", async () => {
  mockApi({
    ...base,
    "GET /risks/R-001": () => json(200, riskDetail({ current: level(5, 5), can_accept: false, required_authority: "executive" })),
  })
  renderApp("/risks/R-001")
  expect(await screen.findByText("Waiting for acceptance by top management.")).toBeInTheDocument()
  expect(screen.queryByRole("button", { name: "Accept residual risk" })).not.toBeInTheDocument()
})

test("chooses a treatment and adds an action", async () => {
  const planned = riskDetail({
    can_accept: false, status: "treatment_planned", treatment_option: "modify",
    treatment: { option: "modify", note: null, budget: "PKR 2m", due: null },
  })
  const calls = mockApi({
    ...base,
    "GET /risks/R-001": () => json(200, riskDetail({ can_accept: false })),
    "POST /risks/R-001/treatment": () => json(200, planned),
    "POST /risks/R-001/actions": () => json(201, {
      ...planned, progress: { done: 0, total: 1 },
      actions: [{ id: "t1", title: "Enable MFA", assignee: null, due: null, status: "todo", done_at: null }],
    }),
  })
  renderApp("/risks/R-001")
  await userEvent.click(await screen.findByRole("radio", { name: "Modify" }))
  await userEvent.type(screen.getByLabelText("Budget"), "PKR 2m")
  await userEvent.click(screen.getByRole("button", { name: "Save treatment" }))
  await userEvent.type(await screen.findByLabelText("New action"), "Enable MFA")
  await userEvent.click(screen.getByRole("button", { name: "Add action" }))
  expect(await screen.findByText("Enable MFA")).toBeInTheDocument()
  const posts = calls.filter((c) => c.method === "POST").map((c) => JSON.parse(String(c.init.body)))
  expect(posts).toEqual([
    { option: "modify", note: null, budget: "PKR 2m", due: null },
    { title: "Enable MFA", assignee_id: null, due: null },
  ])
})
```

`frontend/src/pages/RiskSnapshots.test.tsx`:
```tsx
import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { json, ME, mockApi, renderApp } from "../test/render"

const snapshot = (id: string, label: string) => ({
  id, label, taken_at: "2026-10-08T09:00:00Z", taken_by: "Sana Malik", methodology_version: 1, risk_count: 3,
})

test("saves a snapshot and compares two", async () => {
  const calls = mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /risk-snapshots": () => json(200, [snapshot("s2", "Q4 2026"), snapshot("s1", "Q3 2026")]),
    "POST /risk-snapshots": () => json(201, { ...snapshot("s3", "Q1 2027"), rows: [] }),
    "GET /risk-snapshots/compare": () => json(200, {
      base: snapshot("s1", "Q3 2026"), head: snapshot("s2", "Q4 2026"), added: ["R-004"], removed: [],
      changed: [{ code: "R-001", title: "Ransomware", changes: [{ field: "current", before: "High (16)", after: "Medium (8)" }] }],
    }),
  })
  renderApp("/risks/snapshots")
  await userEvent.type(await screen.findByLabelText("Snapshot label"), "Q1 2027")
  await userEvent.click(screen.getByRole("button", { name: "Save snapshot" }))
  await userEvent.selectOptions(screen.getByLabelText("Compare"), "s1")
  await userEvent.selectOptions(screen.getByLabelText("With"), "s2")
  expect(await screen.findByText("High (16) → Medium (8)")).toBeInTheDocument()
  expect(screen.getByText(/Added: R-004/)).toBeInTheDocument()
  const post = calls.find((c) => c.method === "POST")!
  expect(JSON.parse(String(post.init.body))).toEqual({ label: "Q1 2027" })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd frontend && npx vitest run --testTimeout=10000`
Expected: FAIL — `Failed to resolve import "./Heatmap"` and the `/risks` pages render "Not Found".

- [ ] **Step 3: Implement tokens, types and API hooks**

Append to `frontend/src/styles/tokens.css` (the heat scale is the same in both themes; text on it is always dark):
```css
:root {
  --heat-1: #cdebd8; --heat-2: #e4efb0; --heat-3: #fce38a; --heat-4: #f8a35b; --heat-5: #e2483d; --on-heat: #1b2233;
}
```
Add to the `@theme inline` block in `frontend/src/styles/global.css`:
```css
  --color-heat-1: var(--heat-1);
  --color-heat-2: var(--heat-2);
  --color-heat-3: var(--heat-3);
  --color-heat-4: var(--heat-4);
  --color-heat-5: var(--heat-5);
  --color-on-heat: var(--on-heat);
```

Append to `frontend/src/api/types.ts`:
```ts
export interface Level { likelihood: number; consequence: number; score: number; band: string; band_label: string }
export interface Band {
  key: string
  label: string
  min: number
  max: number
  above_appetite: boolean
  treatment_required: boolean
  authority: string
  review_days: number
  rule: string
}
export interface Methodology {
  version_no: number
  name: string
  likelihood: { level: number; label: string; guidance: string }[]
  consequence: {
    levels: { level: number; label: string }[]
    dimensions: { key: string; label: string; guidance: string[] }[]
  }
  bands: Band[]
}
export interface LibraryItem { code: string; name: string; category: string; description: string | null; is_custom: boolean }
export interface RiskTemplate {
  code: string
  title: string
  scenario: string
  category: string
  threat_codes: string[]
  vulnerability_codes: string[]
  control_codes: string[]
  likelihood: number
  consequence: Record<string, number>
}
export interface RiskLibrary { threats: LibraryItem[]; vulnerabilities: LibraryItem[]; templates: RiskTemplate[] }
export interface RiskRow {
  id: string
  code: string
  title: string
  category: string | null
  approach: string
  owner: Owner | null
  status: string
  inherent: Level | null
  current: Level | null
  target: Level | null
  treatment_option: string | null
  progress: { done: number; total: number }
  review_due: string | null
  acceptance_expires: string | null
}
export interface Assessment {
  id: string
  likelihood: number | null
  consequence: Record<string, number>
  inherent: Level | null
  suggested: Level | null
  current: Level | null
  current_reason: string | null
  target: Level | null
  rationale: string | null
  finalized_at: string | null
  assessed_by: string | null
  methodology_version: number
}
export interface RiskTask {
  id: string
  title: string
  assignee: Owner | null
  due: string | null
  status: string
  done_at: string | null
}
export interface RiskAcceptance {
  band: string
  score: number
  authority: string
  statement: string
  accepted_by: string | null
  accepted_at: string
  expires_at: string
}
export interface RiskDetail extends RiskRow {
  description: string | null
  template_code: string | null
  threats: { code: string; name: string }[]
  vulnerabilities: { code: string; name: string }[]
  assets: { id: string; code: string; name: string }[]
  controls: { code: string; title: string; status: string; axis: string }[]
  draft: Assessment | null
  latest: Assessment | null
  history: Assessment[]
  treatment: { option: string | null; note: string | null; budget: string | null; due: string | null }
  actions: RiskTask[]
  acceptance: RiskAcceptance | null
  required_authority: string | null
  can_accept: boolean
  can_edit: boolean
  closed_at: string | null
  close_reason: string | null
}
export interface SnapshotSummary {
  id: string
  label: string
  taken_at: string
  taken_by: string | null
  methodology_version: number
  risk_count: number
}
export interface SnapshotCompare {
  base: SnapshotSummary
  head: SnapshotSummary
  added: string[]
  removed: string[]
  changed: { code: string; title: string; changes: { field: string; before: string | null; after: string | null }[] }[]
}
export interface Asset {
  id: string
  code: string
  name: string
  type: string
  owner: Owner | null
  classification: string
  confidentiality: number
  integrity: number
  availability: number
  criticality: number
  location: string | null
  description: string | null
  lifecycle: string
}
export interface Person { id: string; full_name: string; email: string; roles: string[] }
```

`frontend/src/api/risks.ts`:
```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"
import type {
  ControlPage, Methodology, RiskDetail, RiskLibrary, RiskRow, RiskTask, SnapshotCompare, SnapshotSummary,
} from "./types"

export const RISK_STATUS_LABEL: Record<string, string> = {
  draft: "Draft",
  assessed: "Assessed",
  reassessing: "Reassessing",
  treatment_planned: "Treatment planned",
  in_treatment: "In treatment",
  treated: "Treated",
  accepted: "Accepted",
  review_due: "Review due",
  closed: "Closed",
}
export const TREATMENT_LABEL: Record<string, string> = { modify: "Modify", retain: "Retain", avoid: "Avoid", share: "Share" }
export const AUTHORITY_LABEL: Record<string, string> = {
  risk_owner: "the risk owner",
  isms_manager: "an ISMS manager",
  executive: "top management",
}
export const TASK_STATUS_LABEL: Record<string, string> = {
  todo: "To do", in_progress: "In progress", blocked: "Blocked", done: "Done", cancelled: "Cancelled",
}

const path = (code: string) => `/risks/${encodeURIComponent(code)}`
const send = <T,>(url: string, method: string, body?: unknown) =>
  api<T>(url, { method, body: body === undefined ? undefined : JSON.stringify(body) })

export function useMethodology() {
  return useQuery({ queryKey: ["risk-methodology"], queryFn: () => api<Methodology>("/risk-methodology"), staleTime: Infinity })
}

export function useRiskLibrary() {
  return useQuery({ queryKey: ["risk-library"], queryFn: () => api<RiskLibrary>("/risk-library"), staleTime: 300_000 })
}

export function useRisks(filters: { q?: string; mine?: boolean }) {
  return useQuery({
    queryKey: ["risks", filters],
    queryFn: () => {
      const params = new URLSearchParams()
      if (filters.q) params.set("q", filters.q)
      if (filters.mine) params.set("owner", "me")
      const query = params.toString()
      return api<RiskRow[]>(`/risks${query ? `?${query}` : ""}`)
    },
  })
}

export function useRisk(code: string) {
  return useQuery({ queryKey: ["risk", code], queryFn: () => api<RiskDetail>(path(code)) })
}

export function useAllControls() {
  return useQuery({
    queryKey: ["controls", "all"],
    queryFn: async () => (await api<ControlPage>("/controls?limit=200")).items,
    staleTime: 60_000,
  })
}

function useRiskMutation<T>(request: (body: T) => Promise<RiskDetail>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: request,
    onSuccess: (detail) => {
      queryClient.setQueryData(["risk", detail.code], detail)
      queryClient.invalidateQueries({ queryKey: ["risks"] })
      queryClient.invalidateQueries({ queryKey: ["soa"] })
    },
  })
}

export function useCreateRisk() {
  return useRiskMutation((body: { template_code?: string; title?: string }) => send<RiskDetail>("/risks", "POST", body))
}

export type RiskChanges = Partial<{
  title: string
  description: string | null
  category: string | null
  approach: string
  owner_id: string | null
  threat_codes: string[]
  vulnerability_codes: string[]
  asset_ids: string[]
}>

export function useUpdateRisk(code: string) {
  return useRiskMutation((changes: RiskChanges) => send<RiskDetail>(path(code), "PATCH", changes))
}

export function useSetRiskControls(code: string) {
  return useRiskMutation((body: { links: { code: string; axis: string }[] }) =>
    send<RiskDetail>(`${path(code)}/controls`, "PUT", body))
}

export type AssessmentChanges = Partial<{
  likelihood: number | null
  consequence: Record<string, number>
  current_l: number | null
  current_c: number | null
  current_reason: string | null
  target_l: number | null
  target_c: number | null
  rationale: string | null
}>

export function useSaveAssessment(code: string) {
  return useRiskMutation((changes: AssessmentChanges) =>
    send<RiskDetail>(`${path(code)}/assessment`, "PATCH", changes))
}

export function useFinalizeAssessment(code: string) {
  return useRiskMutation(() => send<RiskDetail>(`${path(code)}/assessment/finalize`, "POST"))
}

export function useSetTreatment(code: string) {
  return useRiskMutation((body: { option: string; note: string | null; budget: string | null; due: string | null }) =>
    send<RiskDetail>(`${path(code)}/treatment`, "POST", body))
}

export function useAddAction(code: string) {
  return useRiskMutation((body: { title: string; assignee_id: string | null; due: string | null }) =>
    send<RiskDetail>(`${path(code)}/actions`, "POST", body))
}

export function useAcceptRisk(code: string) {
  return useRiskMutation((statement: string) => send<RiskDetail>(`${path(code)}/accept`, "POST", { statement }))
}

export function useCloseRisk(code: string) {
  return useRiskMutation((reason: string) => send<RiskDetail>(`${path(code)}/close`, "POST", { reason }))
}

export function useUpdateTask(code: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...changes }: { id: string; status?: string; title?: string }) =>
      send<RiskTask>(`/tasks/${id}`, "PATCH", changes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["risk", code] })
      queryClient.invalidateQueries({ queryKey: ["risks"] })
    },
  })
}

export function useSnapshots() {
  return useQuery({ queryKey: ["risk-snapshots"], queryFn: () => api<SnapshotSummary[]>("/risk-snapshots") })
}

export function useCreateSnapshot() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (label: string) => send<SnapshotSummary>("/risk-snapshots", "POST", { label }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["risk-snapshots"] }),
  })
}

export function useSnapshotCompare(base: string, head: string) {
  return useQuery({
    queryKey: ["risk-snapshots", "compare", base, head],
    queryFn: () => api<SnapshotCompare>(`/risk-snapshots/compare?base=${base}&head=${head}`),
    enabled: Boolean(base && head && base !== head),
  })
}
```

`frontend/src/api/people.ts`:
```ts
import { useQuery } from "@tanstack/react-query"
import { api } from "./client"
import type { Person } from "./types"

export function usePeople() {
  return useQuery({ queryKey: ["people"], queryFn: () => api<Person[]>("/people"), staleTime: 60_000 })
}
```

`frontend/src/api/assets.ts`:
```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"
import type { Asset } from "./types"

export const ASSET_TYPE_LABEL: Record<string, string> = {
  information: "Information",
  application: "Application",
  server: "Server",
  endpoint: "Endpoint",
  network_device: "Network device",
  cloud_service: "Cloud service",
  facility: "Facility",
  people: "People / role",
  supplier_service: "Supplier service",
}
export const CLASSIFICATION_LABEL: Record<string, string> = {
  public: "Public", internal: "Internal", confidential: "Confidential", restricted: "Restricted",
}
export const LIFECYCLE_LABEL: Record<string, string> = { planned: "Planned", in_use: "In use", retired: "Retired" }

export interface AssetInput {
  name: string
  type: string
  owner_id?: string | null
  classification: string
  confidentiality: number
  integrity: number
  availability: number
  location: string | null
  description: string | null
  lifecycle: string
}

export function useAssets(includeRetired = false) {
  return useQuery({
    queryKey: ["assets", includeRetired],
    queryFn: () => api<Asset[]>(`/assets${includeRetired ? "?include_retired=true" : ""}`),
  })
}

export function useCreateAsset() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: AssetInput) => api<Asset>("/assets", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assets"] }),
  })
}

export function useUpdateAsset() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...changes }: Partial<AssetInput> & { id: string }) =>
      api<Asset>(`/assets/${id}`, { method: "PATCH", body: JSON.stringify(changes) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assets"] }),
  })
}
```

- [ ] **Step 4: Implement the shared components**

`frontend/src/components/LevelPill.tsx`:
```tsx
import { RISK_STATUS_LABEL } from "../api/risks"
import type { Level } from "../api/types"
import { StatusPill } from "./StatusPill"

export const HEAT: Record<string, string> = {
  very_low: "bg-heat-1",
  low: "bg-heat-2",
  medium: "bg-heat-3",
  high: "bg-heat-4",
  critical: "bg-heat-5",
}

export function LevelPill({ level }: { level: Level | null }) {
  if (!level) return <span className="text-fg-3">—</span>
  return (
    <span
      className={`inline-flex h-6 items-center whitespace-nowrap rounded-full px-2.5 text-xs font-semibold tabular-nums text-on-heat ${HEAT[level.band] ?? "bg-subtle"}`}
      title={`Likelihood ${level.likelihood} × consequence ${level.consequence}`}
    >
      {`${level.band_label} ${level.score}`}
    </span>
  )
}

const RISK_STYLE: Record<string, string> = {
  draft: "not_started",
  reassessing: "in_review",
  assessed: "in_progress",
  treatment_planned: "in_progress",
  in_treatment: "in_progress",
  treated: "in_review",
  accepted: "compliant",
  review_due: "at_risk",
  closed: "excluded",
}

export function RiskStatusPill({ status }: { status: string }) {
  return <StatusPill status={RISK_STYLE[status] ?? "not_started"} label={RISK_STATUS_LABEL[status] ?? status} />
}
```

`frontend/src/components/Segmented.tsx`:
```tsx
export function Segmented<T extends string>({ label, options, value, onChange }: {
  label: string
  options: { key: T; label: string }[]
  value: T
  onChange: (value: T) => void
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex rounded-lg border border-line-2 bg-surface p-0.5">
      {options.map((option) => (
        <button
          key={option.key}
          type="button"
          aria-pressed={value === option.key}
          onClick={() => onChange(option.key)}
          className="rounded-md px-2.5 py-1 text-[13px] font-medium text-fg-2 aria-pressed:bg-primary-soft aria-pressed:text-primary"
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
```

`frontend/src/components/Heatmap.tsx`:
```tsx
import { Fragment } from "react"
import type { Band } from "../api/types"
import { HEAT } from "./LevelPill"

export interface HeatPoint { code: string; title: string; likelihood: number; consequence: number }
const SCALE = [1, 2, 3, 4, 5]

export function Heatmap({ points, bands, selected, onSelect, marker, size = "md" }: {
  points: HeatPoint[]
  bands: Band[]
  selected?: [number, number] | null
  onSelect?: (cell: [number, number] | null) => void
  marker?: { likelihood: number; consequence: number } | null
  size?: "sm" | "md"
}) {
  const bandOf = (score: number) => bands.find((b) => score >= b.min && score <= b.max)
  return (
    <div className="grid gap-1.5">
      <div className="grid grid-cols-[1.25rem_repeat(5,minmax(0,1fr))] gap-1" role="group" aria-label="Risk heatmap">
        {[...SCALE].reverse().map((consequence) => (
          <Fragment key={consequence}>
            <span className="flex items-center justify-end pr-1 text-[11px] text-fg-3" aria-hidden="true">{consequence}</span>
            {SCALE.map((likelihood) => {
              const count = points.filter((p) => p.likelihood === likelihood && p.consequence === consequence).length
              const band = bandOf(likelihood * consequence)
              const isSelected = selected?.[0] === likelihood && selected?.[1] === consequence
              const isMarker = marker?.likelihood === likelihood && marker?.consequence === consequence
              const label = `Likelihood ${likelihood}, consequence ${consequence}: ${count} ${count === 1 ? "risk" : "risks"}`
              const className = `relative flex aspect-square items-center justify-center rounded-md text-on-heat tabular-nums ${HEAT[band?.key ?? ""] ?? "bg-subtle"} ${isSelected ? "ring-2 ring-fg ring-offset-1 ring-offset-surface" : ""} ${size === "sm" ? "text-[11px]" : "text-sm font-semibold"}`
              const content = (
                <>
                  {count > 0 ? count : ""}
                  {isMarker && (
                    <span className="absolute size-3 rounded-full border-2 border-surface bg-ink" title="This risk" aria-hidden="true" />
                  )}
                </>
              )
              return onSelect ? (
                <button key={likelihood} type="button" aria-label={label} aria-pressed={isSelected} className={className}
                  onClick={() => onSelect(isSelected ? null : [likelihood, consequence])}>
                  {content}
                </button>
              ) : (
                <div key={likelihood} aria-label={label} className={className}>{content}</div>
              )
            })}
          </Fragment>
        ))}
        <span aria-hidden="true" />
        {SCALE.map((likelihood) => (
          <span key={likelihood} className="text-center text-[11px] text-fg-3" aria-hidden="true">{likelihood}</span>
        ))}
      </div>
      <p className="flex justify-between text-[11px] text-fg-3" aria-hidden="true">
        <span>↑ Consequence</span>
        <span>Likelihood →</span>
      </p>
    </div>
  )
}
```

- [ ] **Step 5: Implement the pages**

`frontend/src/pages/Risks.tsx`:
```tsx
import { Link } from "@tanstack/react-router"
import { type FormEvent, useState } from "react"
import { RISK_STATUS_LABEL, TREATMENT_LABEL, useMethodology, useRisks } from "../api/risks"
import type { RiskRow } from "../api/types"
import { Button } from "../components/Button"
import { Heatmap } from "../components/Heatmap"
import { LevelPill, RiskStatusPill } from "../components/LevelPill"
import { Segmented } from "../components/Segmented"
import { formatDate } from "../lib/format"

type View = "table" | "board" | "heatmap"
type Matrix = "inherent" | "current" | "target"
const VIEWS: { key: View; label: string }[] = [
  { key: "table", label: "Table" }, { key: "board", label: "Board" }, { key: "heatmap", label: "Heatmap" },
]
const MATRICES: { key: Matrix; label: string }[] = [
  { key: "inherent", label: "Inherent" }, { key: "current", label: "Current" }, { key: "target", label: "Target" },
]
const BOARD = ["draft", "assessed", "reassessing", "treatment_planned", "in_treatment", "treated", "accepted", "review_due"]
const linkClass = "rounded-lg border border-line-2 bg-surface px-2.5 py-1 text-[13px] font-medium hover:border-fg-3"

function RiskLink({ risk }: { risk: RiskRow }) {
  return (
    <Link to="/risks/$code" params={{ code: risk.code }} className="text-fg hover:text-primary">{risk.title}</Link>
  )
}

export function RisksPage() {
  const [view, setView] = useState<View>("table")
  const [matrix, setMatrix] = useState<Matrix>("current")
  const [typed, setTyped] = useState("")
  const [query, setQuery] = useState("")
  const [mine, setMine] = useState(false)
  const [cell, setCell] = useState<[number, number] | null>(null)
  const risks = useRisks({ q: query || undefined, mine })
  const methodology = useMethodology()
  const rows = risks.data ?? []

  function onSearch(event: FormEvent) {
    event.preventDefault()
    setQuery(typed.trim())
  }

  return (
    <div className="mx-auto grid max-w-6xl gap-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Risk</p>
          <h1 className="font-display text-[26px] font-extrabold tracking-tight">Risks</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Segmented label="View" options={VIEWS} value={view} onChange={setView} />
          <Link to="/risks/snapshots" className={linkClass}>Snapshots</Link>
          <a href="/api/v1/risk-register/export.xlsx" className={linkClass}>Export XLSX</a>
        </div>
      </header>
      <section className="rounded-xl border border-line bg-surface">
        <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
          <label className="flex items-center gap-2 text-[13px]">
            <input type="checkbox" checked={mine} onChange={(e) => setMine(e.target.checked)} />
            Only my risks
          </label>
          {view === "heatmap" && <Segmented label="Matrix" options={MATRICES} value={matrix} onChange={(m) => { setMatrix(m); setCell(null) }} />}
          <form onSubmit={onSearch} className="ml-auto flex min-w-0 flex-1 justify-end gap-2" role="search">
            <label htmlFor="risk-search" className="sr-only">Search risks</label>
            <input id="risk-search" value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="Filter by ID or title"
              className="w-full min-w-0 max-w-72 rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13px]" />
            <Button type="submit" variant="secondary" size="sm">Search</Button>
          </form>
        </div>
        {risks.isError && <p role="alert" className="p-4">{risks.error.message}</p>}
        {risks.isSuccess && rows.length === 0 && (
          <p className="px-4 py-8 text-center text-fg-3">{query || mine ? "No risks match these filters." : "No risks yet."}</p>
        )}
        {rows.length > 0 && view === "table" && <RiskTable rows={rows} />}
        {rows.length > 0 && view === "board" && <RiskBoard rows={rows} />}
        {rows.length > 0 && view === "heatmap" && methodology.data && (
          <div className="grid gap-4 p-4 md:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
            <Heatmap
              bands={methodology.data.bands}
              selected={cell}
              onSelect={setCell}
              points={rows.flatMap((r) => {
                const lvl = r[matrix]
                return lvl ? [{ code: r.code, title: r.title, likelihood: lvl.likelihood, consequence: lvl.consequence }] : []
              })}
            />
            <section aria-label="Selected cell" className="grid content-start gap-2">
              {cell ? (
                <ul className="grid gap-2">
                  {rows.filter((r) => r[matrix]?.likelihood === cell[0] && r[matrix]?.consequence === cell[1]).map((r) => (
                    <li key={r.id} className="flex items-center justify-between gap-2 rounded-lg border border-line px-3 py-2">
                      <span className="min-w-0"><span className="font-mono text-[12px] text-fg-3">{r.code}</span> <RiskLink risk={r} /></span>
                      <RiskStatusPill status={r.status} />
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[13px] text-fg-3">Select a cell to see its risks.</p>
              )}
            </section>
          </div>
        )}
      </section>
    </div>
  )
}

function RiskTable({ rows }: { rows: RiskRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[13.5px]">
        <thead>
          <tr className="text-left text-[11.5px] uppercase tracking-[0.06em] text-fg-3">
            {["ID", "Risk", "Owner", "Status", "Inherent", "Current", "Target", "Treatment", "Actions", "Next review"].map((h) => (
              <th key={h} className="px-3.5 py-3 font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-t border-line hover:bg-subtle">
              <td className="whitespace-nowrap px-3.5 py-2.5 font-mono text-[12.5px] text-fg-3">{r.code}</td>
              <td className="min-w-60 px-3.5 py-2.5"><RiskLink risk={r} /></td>
              <td className="whitespace-nowrap px-3.5 py-2.5 text-fg-2">{r.owner?.full_name ?? "Unassigned"}</td>
              <td className="px-3.5 py-2.5"><RiskStatusPill status={r.status} /></td>
              <td className="px-3.5 py-2.5"><LevelPill level={r.inherent} /></td>
              <td className="px-3.5 py-2.5"><LevelPill level={r.current} /></td>
              <td className="px-3.5 py-2.5"><LevelPill level={r.target} /></td>
              <td className="px-3.5 py-2.5 text-fg-2">{r.treatment_option ? TREATMENT_LABEL[r.treatment_option] : "—"}</td>
              <td className="whitespace-nowrap px-3.5 py-2.5 tabular-nums text-fg-2">
                {r.progress.total ? `${r.progress.done} of ${r.progress.total}` : "—"}
              </td>
              <td className="whitespace-nowrap px-3.5 py-2.5 text-fg-2">{r.review_due ? formatDate(r.review_due) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function RiskBoard({ rows }: { rows: RiskRow[] }) {
  return (
    <div className="flex gap-3 overflow-x-auto p-4">
      {BOARD.map((status) => {
        const column = rows.filter((r) => r.status === status)
        return (
          <section key={status} aria-label={RISK_STATUS_LABEL[status]} className="grid w-60 shrink-0 content-start gap-2 rounded-lg bg-subtle p-2">
            <h2 className="flex justify-between px-1 text-[12px] font-semibold uppercase tracking-[0.06em] text-fg-3">
              {RISK_STATUS_LABEL[status]} <span className="tabular-nums">{column.length}</span>
            </h2>
            {column.map((r) => (
              <article key={r.id} className="grid gap-1.5 rounded-lg border border-line bg-surface p-3">
                <span className="font-mono text-[11.5px] text-fg-3">{r.code}</span>
                <RiskLink risk={r} />
                <LevelPill level={r.current ?? r.inherent} />
              </article>
            ))}
          </section>
        )
      })}
    </div>
  )
}
```

`frontend/src/pages/RiskDetail.tsx`:
```tsx
import { Link, useParams } from "@tanstack/react-router"
import { type FormEvent, useState } from "react"
import { usePeople } from "../api/people"
import {
  AUTHORITY_LABEL, TASK_STATUS_LABEL, TREATMENT_LABEL, useAcceptRisk, useAddAction, useCloseRisk, useRisk,
  useSetTreatment, useUpdateTask,
} from "../api/risks"
import type { Level, RiskDetail } from "../api/types"
import { Button } from "../components/Button"
import { LevelPill, RiskStatusPill } from "../components/LevelPill"
import { StatusPill } from "../components/StatusPill"
import { formatDate } from "../lib/format"

const card = "rounded-xl border border-line bg-surface p-5"
const input = "rounded-lg border border-line-2 bg-surface px-3 py-2 text-sm"
const OPTION_HELP: Record<string, string> = {
  modify: "Add or improve controls",
  retain: "Accept the risk as it is",
  avoid: "Stop the activity that causes it",
  share: "Insurance or outsourcing",
}

export function RiskDetailPage() {
  const { code } = useParams({ from: "/app/risks/$code" })
  const risk = useRisk(code)
  if (risk.isPending) return <p role="status" className="text-fg-3">Loading…</p>
  if (risk.isError) return <p role="alert">{risk.error.message}</p>
  const r = risk.data
  return (
    <div className="mx-auto grid max-w-5xl gap-4">
      <nav aria-label="Breadcrumb" className="text-[13px] text-fg-3">
        <Link to="/risks" className="hover:text-fg">Risks</Link> <span aria-hidden="true">›</span>{" "}
        <span className="font-mono">{r.code}</span>
      </nav>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="mb-2 font-mono text-[13px] text-fg-3">{r.code}{r.category ? ` · ${r.category}` : ""}</p>
          <h1 className="font-display text-[26px] font-extrabold tracking-tight">{r.title}</h1>
          <p className="mt-2 text-[13px] text-fg-2">
            Owner: {r.owner?.full_name ?? "Unassigned"}
            {r.review_due ? ` · Next review ${formatDate(r.review_due)}` : ""}
          </p>
        </div>
        <div className="flex items-center gap-2"><RiskStatusPill status={r.status} /></div>
      </header>
      <Levels risk={r} />
      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_320px]">
        <div className="grid content-start gap-4">
          <Scenario risk={r} />
          <MitigatingControls risk={r} />
          <Treatment risk={r} />
          <History risk={r} />
        </div>
        <div className="grid content-start gap-4">
          <Acceptance risk={r} />
          {r.closed_at && (
            <section className={card}>
              <h2 className="text-[15px] font-semibold">Closed</h2>
              <p className="text-[13px] text-fg-2">{formatDate(r.closed_at)} · {r.close_reason}</p>
            </section>
          )}
          {r.can_edit && <CloseRisk risk={r} />}
        </div>
      </div>
    </div>
  )
}

function Levels({ risk }: { risk: RiskDetail }) {
  const items: [string, Level | null][] = [["Inherent", risk.inherent], ["Current", risk.current], ["Target", risk.target]]
  return (
    <section aria-label="Risk levels" className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-surface px-5 py-4">
      {items.map(([label, value], index) => (
        <div key={label} className="flex items-center gap-2">
          {index > 0 && <span aria-hidden="true" className="text-fg-3">→</span>}
          <span className="text-[11.5px] uppercase tracking-[0.06em] text-fg-3">{label}</span>
          <LevelPill level={value} />
        </div>
      ))}
    </section>
  )
}

function Scenario({ risk }: { risk: RiskDetail }) {
  const groups: [string, { code: string; name: string }[]][] = [
    ["Threats", risk.threats],
    ["Vulnerabilities", risk.vulnerabilities],
    ["Assets", risk.assets.map((a) => ({ code: a.code, name: a.name }))],
  ]
  return (
    <section className={`${card} grid gap-3`}>
      <h2 className="text-[15px] font-semibold">Scenario</h2>
      <p className="text-[13.5px] text-fg-2">{risk.description || "No scenario written yet."}</p>
      {groups.map(([label, items]) => (
        <div key={label} className="grid gap-1.5">
          <p className="text-[11.5px] uppercase tracking-[0.06em] text-fg-3">{label}</p>
          {items.length ? (
            <ul className="flex flex-wrap gap-1.5">
              {items.map((i) => (
                <li key={i.code} className="rounded-md bg-subtle px-2 py-0.5 text-[12.5px]">
                  <span className="font-mono text-fg-3">{i.code}</span> {i.name}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[13px] text-fg-3">None</p>
          )}
        </div>
      ))}
    </section>
  )
}

function MitigatingControls({ risk }: { risk: RiskDetail }) {
  return (
    <section className={card}>
      <h2 className="mb-2 text-[15px] font-semibold">Mitigating controls</h2>
      {risk.controls.length === 0 ? (
        <p className="text-[13px] text-fg-3">No controls linked yet.</p>
      ) : (
        <ul className="grid gap-2">
          {risk.controls.map((c) => (
            <li key={c.code} className="flex flex-wrap items-center justify-between gap-2">
              <span className="min-w-0">
                <span className="font-mono text-[12.5px] text-fg-3">{c.code}</span>{" "}
                <Link to="/controls/$code" params={{ code: c.code }} className="hover:text-primary">{c.title}</Link>
                <span className="text-[12px] text-fg-3"> · reduces {c.axis}</span>
              </span>
              <StatusPill status={c.status} />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function Treatment({ risk }: { risk: RiskDetail }) {
  const setTreatment = useSetTreatment(risk.code)
  const [option, setOption] = useState(risk.treatment.option ?? "")
  const [note, setNote] = useState(risk.treatment.note ?? "")
  const [budget, setBudget] = useState(risk.treatment.budget ?? "")
  const [due, setDue] = useState(risk.treatment.due ?? "")
  const editable = risk.can_edit && !["draft", "closed"].includes(risk.status)

  function save(event: FormEvent) {
    event.preventDefault()
    setTreatment.mutate({ option, note: note.trim() || null, budget: budget.trim() || null, due: due || null })
  }

  return (
    <section className={`${card} grid gap-3`} aria-labelledby="treatment-heading">
      <h2 id="treatment-heading" className="text-[15px] font-semibold">Treatment</h2>
      {editable ? (
        <form onSubmit={save} className="grid gap-3">
          <fieldset className="grid gap-2 sm:grid-cols-2">
            <legend className="sr-only">Treatment option</legend>
            {Object.keys(TREATMENT_LABEL).map((key) => (
              <label key={key} className="flex items-start gap-2 rounded-lg border border-line px-3 py-2 text-[13px]">
                <input type="radio" name="treatment" value={key} checked={option === key} onChange={() => setOption(key)}
                  aria-describedby={`treatment-${key}-help`} />
                <span>
                  <span className="font-medium">{TREATMENT_LABEL[key]}</span>
                  <span id={`treatment-${key}-help`} className="block text-fg-3">{OPTION_HELP[key]}</span>
                </span>
              </label>
            ))}
          </fieldset>
          <label htmlFor="treatment-note" className="text-[13px] font-medium">
            {option === "avoid" ? "Decision" : option === "share" ? "Contract or insurance reference" : "Notes"}
          </label>
          <textarea id="treatment-note" rows={2} value={note} onChange={(e) => setNote(e.target.value)} className={input} />
          <div className="flex flex-wrap gap-3">
            <div className="grid gap-1">
              <label htmlFor="treatment-budget" className="text-[13px] font-medium">Budget</label>
              <input id="treatment-budget" value={budget} onChange={(e) => setBudget(e.target.value)} className={input} />
            </div>
            <div className="grid gap-1">
              <label htmlFor="treatment-due" className="text-[13px] font-medium">Due date</label>
              <input id="treatment-due" type="date" value={due} onChange={(e) => setDue(e.target.value)} className={input} />
            </div>
          </div>
          {setTreatment.isError && <p role="alert" className="text-[13px] text-bad">{setTreatment.error.message}</p>}
          <div><Button type="submit" disabled={!option || setTreatment.isPending}>Save treatment</Button></div>
        </form>
      ) : (
        <p className="text-[13px] text-fg-2">
          {risk.treatment.option ? TREATMENT_LABEL[risk.treatment.option] : risk.status === "draft" ? "Finish the assessment first." : "No treatment chosen yet."}
          {risk.treatment.note ? ` · ${risk.treatment.note}` : ""}
        </p>
      )}
      {risk.treatment.option === "modify" && <Actions risk={risk} />}
    </section>
  )
}

function Actions({ risk }: { risk: RiskDetail }) {
  const add = useAddAction(risk.code)
  const update = useUpdateTask(risk.code)
  const people = usePeople()
  const [title, setTitle] = useState("")
  const [assignee, setAssignee] = useState("")
  const [due, setDue] = useState("")

  async function submit(event: FormEvent) {
    event.preventDefault()
    await add.mutateAsync({ title: title.trim(), assignee_id: assignee || null, due: due || null })
    setTitle("")
    setAssignee("")
    setDue("")
  }

  return (
    <div className="grid gap-2 border-t border-line pt-3">
      <h3 className="text-[13.5px] font-semibold">
        Actions <span className="font-normal text-fg-3">{risk.progress.done} of {risk.progress.total} done</span>
      </h3>
      <ul className="grid gap-1.5">
        {risk.actions.map((a) => (
          <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 text-[13px]">
            <span className="min-w-0">
              <span className="font-medium">{a.title}</span>
              <span className="text-fg-3"> · {a.assignee?.full_name ?? "Unassigned"}{a.due ? ` · due ${formatDate(a.due)}` : ""}</span>
            </span>
            {risk.can_edit ? (
              <select aria-label={`Status of ${a.title}`} value={a.status} className={input}
                onChange={(e) => update.mutate({ id: a.id, status: e.target.value })}>
                {Object.entries(TASK_STATUS_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            ) : (
              <span className="text-fg-2">{TASK_STATUS_LABEL[a.status]}</span>
            )}
          </li>
        ))}
      </ul>
      {risk.can_edit && (
        <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
          <div className="grid min-w-48 flex-1 gap-1">
            <label htmlFor="action-title" className="text-[13px] font-medium">New action</label>
            <input id="action-title" value={title} onChange={(e) => setTitle(e.target.value)} className={input} />
          </div>
          <div className="grid gap-1">
            <label htmlFor="action-assignee" className="text-[13px] font-medium">Assignee</label>
            <select id="action-assignee" value={assignee} onChange={(e) => setAssignee(e.target.value)} className={input}>
              <option value="">Unassigned</option>
              {(people.data ?? []).map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
            </select>
          </div>
          <div className="grid gap-1">
            <label htmlFor="action-due" className="text-[13px] font-medium">Due</label>
            <input id="action-due" type="date" value={due} onChange={(e) => setDue(e.target.value)} className={input} />
          </div>
          <Button type="submit" variant="secondary" disabled={!title.trim() || add.isPending}>Add action</Button>
          {add.isError && <p role="alert" className="w-full text-[13px] text-bad">{add.error.message}</p>}
        </form>
      )}
    </div>
  )
}

function Acceptance({ risk }: { risk: RiskDetail }) {
  const accept = useAcceptRisk(risk.code)
  const [statement, setStatement] = useState("")
  const a = risk.acceptance
  const actionsOpen = risk.treatment.option === "modify" && risk.actions.some((t) => !["done", "cancelled"].includes(t.status))

  function submit(event: FormEvent) {
    event.preventDefault()
    accept.mutate(statement.trim())
  }

  let body
  if (a) {
    body = (
      <>
        <p className="text-[13px]">
          Accepted by {a.accepted_by ?? "unknown"} on {formatDate(a.accepted_at)}, valid until {formatDate(a.expires_at)}.
        </p>
        <blockquote className="border-l-2 border-line-2 pl-3 text-[13px] text-fg-2">{a.statement}</blockquote>
      </>
    )
  } else if (!risk.required_authority) {
    body = <p className="text-[13px] text-fg-3">Finish the assessment to decide on acceptance.</p>
  } else if (actionsOpen) {
    body = <p className="text-[13px] text-fg-3">Finish the treatment actions before accepting the residual risk.</p>
  } else if (risk.can_accept) {
    body = (
      <form onSubmit={submit} className="grid gap-2">
        <label htmlFor="acceptance-statement" className="text-[13px] font-medium">Acceptance statement</label>
        <textarea id="acceptance-statement" rows={3} value={statement} onChange={(e) => setStatement(e.target.value)} className={input} />
        {accept.isError && <p role="alert" className="text-[13px] text-bad">{accept.error.message}</p>}
        <div><Button type="submit" disabled={!statement.trim() || accept.isPending}>Accept residual risk</Button></div>
      </form>
    )
  } else {
    body = <p className="text-[13px] text-fg-2">Waiting for acceptance by {AUTHORITY_LABEL[risk.required_authority]}.</p>
  }
  return (
    <section className={`${card} grid gap-2`} aria-labelledby="acceptance-heading">
      <h2 id="acceptance-heading" className="text-[15px] font-semibold">Acceptance</h2>
      {body}
    </section>
  )
}

function History({ risk }: { risk: RiskDetail }) {
  return (
    <section className={card}>
      <h2 className="mb-2 text-[15px] font-semibold">Assessment history</h2>
      {risk.history.length === 0 ? (
        <p className="text-[13px] text-fg-3">Not assessed yet.</p>
      ) : (
        <ul className="grid gap-2">
          {risk.history.map((a) => (
            <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 text-[13px]">
              <span className="text-fg-2">
                {a.finalized_at ? formatDate(a.finalized_at) : "—"} · {a.assessed_by ?? "unknown"} · methodology v{a.methodology_version}
              </span>
              <span className="flex items-center gap-1.5"><LevelPill level={a.inherent} /> → <LevelPill level={a.current} /></span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function CloseRisk({ risk }: { risk: RiskDetail }) {
  const close = useCloseRisk(risk.code)
  const [reason, setReason] = useState("")
  return (
    <details className={card}>
      <summary className="cursor-pointer text-[13px] font-medium">Close this risk</summary>
      <form onSubmit={(e) => { e.preventDefault(); close.mutate(reason.trim()) }} className="mt-3 grid gap-2">
        <label htmlFor="close-reason" className="text-[13px] font-medium">Why is it no longer relevant?</label>
        <textarea id="close-reason" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} className={input} />
        {close.isError && <p role="alert" className="text-[13px] text-bad">{close.error.message}</p>}
        <div><Button type="submit" variant="secondary" disabled={!reason.trim() || close.isPending}>Close risk</Button></div>
      </form>
    </details>
  )
}
```

`frontend/src/pages/RiskSnapshots.tsx`:
```tsx
import { Link } from "@tanstack/react-router"
import { type FormEvent, useState } from "react"
import { useCreateSnapshot, useSnapshotCompare, useSnapshots } from "../api/risks"
import { useMe } from "../auth/session"
import { Button } from "../components/Button"
import { formatDate } from "../lib/format"

const input = "rounded-lg border border-line-2 bg-surface px-3 py-2 text-sm"

export function RiskSnapshotsPage() {
  const me = useMe()
  const canCreate = me.data?.permissions.includes("risks:write") ?? false
  const snapshots = useSnapshots()
  const create = useCreateSnapshot()
  const [label, setLabel] = useState("")
  const [base, setBase] = useState("")
  const [head, setHead] = useState("")
  const compare = useSnapshotCompare(base, head)
  const list = snapshots.data ?? []

  async function save(event: FormEvent) {
    event.preventDefault()
    await create.mutateAsync(label.trim())
    setLabel("")
  }

  return (
    <div className="mx-auto grid max-w-5xl gap-4">
      <nav aria-label="Breadcrumb" className="text-[13px] text-fg-3">
        <Link to="/risks" className="hover:text-fg">Risks</Link> <span aria-hidden="true">›</span> Snapshots
      </nav>
      <h1 className="font-display text-[26px] font-extrabold tracking-tight">Assessment snapshots</h1>
      <p className="max-w-2xl text-[13.5px] text-fg-2">
        A snapshot freezes every risk's levels and status. Keep one after each assessment as the clause 8.2 record.
      </p>
      {canCreate && (
        <form onSubmit={save} className="flex flex-wrap items-end gap-2 rounded-xl border border-line bg-surface p-4">
          <div className="grid min-w-56 flex-1 gap-1">
            <label htmlFor="snapshot-label" className="text-[13px] font-medium">Snapshot label</label>
            <input id="snapshot-label" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Q4 2026 risk assessment" className={input} />
          </div>
          <Button type="submit" disabled={!label.trim() || create.isPending}>Save snapshot</Button>
          {create.isError && <p role="alert" className="w-full text-[13px] text-bad">{create.error.message}</p>}
        </form>
      )}
      <section className="overflow-x-auto rounded-xl border border-line bg-surface">
        <table className="w-full text-[13.5px]">
          <thead>
            <tr className="text-left text-[11.5px] uppercase tracking-[0.06em] text-fg-3">
              {["Label", "Taken", "By", "Risks"].map((h) => <th key={h} className="px-3.5 py-3 font-medium">{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {list.map((s) => (
              <tr key={s.id} className="border-t border-line">
                <td className="px-3.5 py-2.5 font-medium">{s.label}</td>
                <td className="px-3.5 py-2.5 text-fg-2">{formatDate(s.taken_at)}</td>
                <td className="px-3.5 py-2.5 text-fg-2">{s.taken_by ?? "—"}</td>
                <td className="px-3.5 py-2.5 tabular-nums text-fg-2">{s.risk_count}</td>
              </tr>
            ))}
            {snapshots.isSuccess && list.length === 0 && (
              <tr><td colSpan={4} className="px-3.5 py-8 text-center text-fg-3">No snapshots yet.</td></tr>
            )}
          </tbody>
        </table>
      </section>
      {list.length >= 2 && (
        <section className="grid gap-3 rounded-xl border border-line bg-surface p-4" aria-labelledby="compare-heading">
          <h2 id="compare-heading" className="text-[15px] font-semibold">Compare snapshots</h2>
          <div className="flex flex-wrap gap-3">
            {([["Compare", base, setBase], ["With", head, setHead]] as const).map(([name, value, setter]) => (
              <div key={name} className="grid gap-1">
                <label htmlFor={`snapshot-${name}`} className="text-[13px] font-medium">{name}</label>
                <select id={`snapshot-${name}`} value={value} onChange={(e) => setter(e.target.value)} className={input}>
                  <option value="">Choose…</option>
                  {list.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
                </select>
              </div>
            ))}
          </div>
          {compare.isError && <p role="alert">{compare.error.message}</p>}
          {compare.data && (
            <div className="grid gap-2 text-[13px]">
              {compare.data.added.length > 0 && <p>Added: {compare.data.added.join(", ")}</p>}
              {compare.data.removed.length > 0 && <p>Removed: {compare.data.removed.join(", ")}</p>}
              {compare.data.changed.length === 0 && <p className="text-fg-3">No risk changed level, status or treatment.</p>}
              <ul className="grid gap-1.5">
                {compare.data.changed.flatMap((risk) =>
                  risk.changes.map((change) => (
                    <li key={`${risk.code}-${change.field}`} className="flex flex-wrap gap-2">
                      <span className="font-mono text-fg-3">{risk.code}</span>
                      <span>{risk.title}</span>
                      <span className="text-fg-3">{change.field}</span>
                      <span>{`${change.before ?? "—"} → ${change.after ?? "—"}`}</span>
                    </li>
                  )),
                )}
              </ul>
            </div>
          )}
        </section>
      )}
    </div>
  )
}
```

- [ ] **Step 6: Wire routes and navigation**

In `frontend/src/router.tsx` import `RiskDetailPage`, `RiskSnapshotsPage`, `RisksPage` and add:
```tsx
const risksRoute = createRoute({ getParentRoute: () => appRoute, path: "/risks", component: RisksPage })
const riskSnapshotsRoute = createRoute({ getParentRoute: () => appRoute, path: "/risks/snapshots", component: RiskSnapshotsPage })
const riskRoute = createRoute({ getParentRoute: () => appRoute, path: "/risks/$code", component: RiskDetailPage })
```
and add `risksRoute, riskSnapshotsRoute, riskRoute` to `appRoute.addChildren([...])`.

In `frontend/src/components/AppShell.tsx` widen `NavItem.to` to `"/" | "/controls" | "/evidence" | "/risks"` and change the Risks item to `{ label: "Risks", icon: "risk", to: "/risks" }`.

- [ ] **Step 7: Run tests, typecheck and build**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd frontend && npm run typecheck && npx vitest run --testTimeout=10000 && npm run build`
Expected: typecheck clean; all tests pass; build succeeds.

- [ ] **Step 8: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && git add -A && git commit -m "feat(web): risk register with table, board and heatmap; risk detail and snapshots"
```

---
### Task 13: Frontend — new risk from a template and the six-step assessment wizard

**Files:**
- Create: `frontend/src/components/CodePicker.tsx`, `frontend/src/pages/RiskNew.tsx`, `frontend/src/pages/RiskWizard.tsx`
- Modify: `frontend/src/pages/Risks.tsx` (New risk link), `frontend/src/pages/RiskDetail.tsx` (Assess link), `frontend/src/router.tsx`
- Test: `frontend/src/pages/RiskWizard.test.tsx`

**Interfaces:**
- Consumes: Task 12 hooks (`useRisk`, `useMethodology`, `useRiskLibrary`, `useCreateRisk`, `useUpdateRisk`, `useSetRiskControls`, `useSaveAssessment`, `useFinalizeAssessment`, `useAllControls`, `useAssets`), `Heatmap`, `LevelPill`, fixtures.
- Produces: `CodePicker({label, items, selected, onChange})`; `levelFor(methodology, likelihood, consequence) -> Level`; routes `/risks/new` (`RiskNewPage`) and `/risks/$code/assess` (`RiskWizardPage`); "New risk" on the register for `risks:write`; "Assess" / "Continue assessment" / "Reassess" on the risk page for editors. `useFinalizeAssessment` takes no argument (`(_body: void) =>`).

- [ ] **Step 1: Write the failing tests**

`frontend/src/pages/RiskWizard.test.tsx`:
```tsx
import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { Assessment } from "../api/types"
import { level, METHODOLOGY, riskDetail } from "../test/fixtures"
import { json, ME, mockApi, renderApp } from "../test/render"

const LIBRARY = {
  threats: [{ code: "T01", name: "Ransomware", category: "Malicious software", description: null, is_custom: false }],
  vulnerabilities: [{ code: "V17", name: "No backups, or backups never tested", category: "Technical", description: null, is_custom: false }],
  templates: [
    { code: "RT01", title: "Ransomware encrypts file servers", scenario: "Ransomware spreads across the network.",
      category: "Cyber attack", threat_codes: ["T01"], vulnerability_codes: ["V17"], control_codes: ["A.8.13"],
      likelihood: 3, consequence: { financial: 4, operational: 5, legal: 3, reputation: 4, data: 4 } },
    { code: "RT14", title: "Backups fail when a restore is needed", scenario: "Restores fail.", category: "Availability",
      threat_codes: [], vulnerability_codes: ["V17"], control_codes: ["A.8.13"], likelihood: 3,
      consequence: { financial: 3, operational: 4, legal: 2, reputation: 2, data: 3 } },
  ],
}

function assessment(overrides: Partial<Assessment> = {}): Assessment {
  return {
    id: "a1", likelihood: null, consequence: {}, inherent: null, suggested: null, current: null, current_reason: null,
    target: null, rationale: null, finalized_at: null, assessed_by: "Sana Malik", methodology_version: 1, ...overrides,
  }
}

const DRAFT = riskDetail({
  status: "draft", inherent: null, current: null, target: null, controls: [], draft: assessment(),
  required_authority: null, can_accept: false,
})
const common = {
  "GET /auth/me": () => json(200, ME),
  "GET /risk-library": () => json(200, LIBRARY),
  "GET /risk-methodology": () => json(200, METHODOLOGY),
  "GET /people": () => json(200, []),
}

test("a template starts a new risk and opens the wizard", async () => {
  const calls = mockApi({
    ...common,
    "POST /risks": () => json(201, DRAFT),
    "GET /risks/R-001": () => json(200, DRAFT),
  })
  renderApp("/risks/new")
  await userEvent.click(await screen.findByRole("button", { name: "Use template: Ransomware encrypts file servers" }))
  expect(await screen.findByRole("heading", { name: /Assess R-001/ })).toBeInTheDocument()
  expect(JSON.parse(String(calls.find((c) => c.method === "POST")!.init.body))).toEqual({ template_code: "RT01" })
})

test("rating likelihood and consequence moves the live position", async () => {
  let draft = assessment()
  const calls = mockApi({
    ...common,
    "GET /assets": () => json(200, []),
    "GET /controls": () => json(200, { items: [], next_cursor: null }),
    "GET /risks/R-001": () => json(200, { ...DRAFT, draft }),
    "PATCH /risks/R-001": () => json(200, { ...DRAFT, draft }),
    "PATCH /risks/R-001/assessment": (_url, init) => {
      draft = { ...draft, ...JSON.parse(String(init.body)) }
      return json(200, { ...DRAFT, draft })
    },
  })
  renderApp("/risks/R-001/assess")
  await screen.findByRole("heading", { name: "What could happen?" })
  await userEvent.click(screen.getByRole("button", { name: "Continue" }))
  await screen.findByRole("heading", { name: "Which assets are affected?" })
  await userEvent.click(screen.getByRole("button", { name: "Continue" }))
  await screen.findByRole("heading", { name: "How likely is it to happen?" })
  await userEvent.click(screen.getByRole("radio", { name: "4 · Likely" }))
  await userEvent.click(screen.getByRole("button", { name: "Continue" }))
  await screen.findByRole("heading", { name: "How bad would it be? Rate each area." })
  const choices = [["Financial", 4], ["Operational", 5], ["Legal / regulatory", 3], ["Reputation", 4], ["Data (C/I/A)", 4]] as const
  for (const [area, value] of choices) {
    await userEvent.click(screen.getByRole("radio", { name: `${area} ${value}` }))
  }
  const panel = screen.getByRole("complementary", { name: "Live position" })
  expect(panel).toHaveTextContent("Inherent: L4 × C5 = 20 · Critical")
  expect(panel).toHaveTextContent("Above appetite")
  expect(screen.getByText("Overall consequence = highest = 5 (Severe)")).toBeInTheDocument()
  await userEvent.click(screen.getByRole("button", { name: "Continue" }))
  await screen.findByRole("heading", { name: "Which controls already reduce this risk?" })
  const bodies = calls
    .filter((c) => c.method === "PATCH" && c.url.pathname.endsWith("/assessment"))
    .map((c) => JSON.parse(String(c.init.body)))
  expect(bodies).toEqual([
    { likelihood: 4 },
    { consequence: { financial: 4, operational: 5, legal: 3, reputation: 4, data: 4 } },
  ])
})

test("finishing the assessment finalizes it and opens the risk", async () => {
  const ratings = { financial: 4, operational: 5, legal: 3, reputation: 4, data: 4 }
  const ready = {
    ...DRAFT,
    draft: assessment({ likelihood: 4, consequence: ratings, inherent: level(4, 5), suggested: level(2, 5) }),
  }
  const assessed = riskDetail({ status: "assessed", draft: null, current: level(2, 5), target: level(2, 5) })
  const calls = mockApi({
    ...common,
    "GET /risks/R-001": () => json(200, ready),
    "PATCH /risks/R-001/assessment": () => json(200, ready),
    "POST /risks/R-001/assessment/finalize": () => json(200, assessed),
  })
  renderApp("/risks/R-001/assess")
  await userEvent.click(await screen.findByRole("button", { name: "6 Result" }))
  expect(screen.getByText("Above appetite. Treat, or accept with the risk owner's justification.")).toBeInTheDocument()
  await userEvent.click(screen.getByRole("button", { name: "Finish assessment" }))
  expect(await screen.findByRole("region", { name: "Risk levels" })).toBeInTheDocument()
  const patch = calls.find((c) => c.method === "PATCH")!
  expect(JSON.parse(String(patch.init.body))).toEqual({ target_l: null, target_c: null, rationale: null })
  expect(calls.some((c) => c.method === "POST" && c.url.pathname.endsWith("/finalize"))).toBe(true)
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd frontend && npx vitest run src/pages/RiskWizard.test.tsx --testTimeout=10000`
Expected: FAIL — the `/risks/new` and `/risks/R-001/assess` routes render "Not Found".

- [ ] **Step 3: Implement the template picker**

In `frontend/src/api/risks.ts`, change `useFinalizeAssessment` so it takes no argument:
```ts
export function useFinalizeAssessment(code: string) {
  return useRiskMutation((_body: void) => send<RiskDetail>(`${path(code)}/assessment/finalize`, "POST"))
}
```

`frontend/src/components/CodePicker.tsx`:
```tsx
import { useState } from "react"

export function CodePicker({ label, items, selected, onChange }: {
  label: string
  items: { code: string; name: string }[]
  selected: string[]
  onChange: (codes: string[]) => void
}) {
  const [filter, setFilter] = useState("")
  const term = filter.trim().toLowerCase()
  const shown = items.filter(
    (item) => !term || selected.includes(item.code) || `${item.code} ${item.name}`.toLowerCase().includes(term),
  )
  function toggle(code: string) {
    onChange(selected.includes(code) ? selected.filter((c) => c !== code) : [...selected, code])
  }
  return (
    <fieldset className="grid gap-2">
      <legend className="text-[13px] font-medium">
        {label} <span className="font-normal text-fg-3">({selected.length} selected)</span>
      </legend>
      <input aria-label={`Filter ${label.toLowerCase()}`} value={filter} onChange={(e) => setFilter(e.target.value)}
        placeholder="Type to filter" className="rounded-lg border border-line-2 bg-surface px-3 py-1.5 text-[13px]" />
      <div className="grid max-h-48 gap-1 overflow-y-auto rounded-lg border border-line p-2">
        {shown.map((item) => (
          <label key={item.code} className="flex items-center gap-2 text-[13px]">
            <input type="checkbox" checked={selected.includes(item.code)} onChange={() => toggle(item.code)} />
            <span className="font-mono text-fg-3">{item.code}</span> {item.name}
          </label>
        ))}
      </div>
    </fieldset>
  )
}
```

`frontend/src/pages/RiskNew.tsx`:
```tsx
import { Link, useNavigate } from "@tanstack/react-router"
import { type FormEvent, useState } from "react"
import { useCreateRisk, useRiskLibrary } from "../api/risks"
import { Button } from "../components/Button"

export function RiskNewPage() {
  const library = useRiskLibrary()
  const create = useCreateRisk()
  const navigate = useNavigate()
  const [title, setTitle] = useState("")
  const [filter, setFilter] = useState("")
  const term = filter.trim().toLowerCase()
  const templates = (library.data?.templates ?? []).filter(
    (t) => !term || `${t.title} ${t.scenario} ${t.category}`.toLowerCase().includes(term),
  )

  async function start(body: { template_code?: string; title?: string }) {
    const risk = await create.mutateAsync(body)
    navigate({ to: "/risks/$code/assess", params: { code: risk.code } })
  }

  function onOwn(event: FormEvent) {
    event.preventDefault()
    if (title.trim()) void start({ title: title.trim() })
  }

  return (
    <div className="mx-auto grid max-w-5xl gap-4">
      <nav aria-label="Breadcrumb" className="text-[13px] text-fg-3">
        <Link to="/risks" className="hover:text-fg">Risks</Link> <span aria-hidden="true">›</span> New risk
      </nav>
      <header>
        <h1 className="font-display text-[26px] font-extrabold tracking-tight">New risk</h1>
        <p className="mt-1 text-[13.5px] text-fg-2">
          Start from one of {library.data?.templates.length ?? 0} ready-made scenarios, or describe your own.
        </p>
      </header>
      <form onSubmit={onOwn} className="flex flex-wrap items-end gap-2 rounded-xl border border-line bg-surface p-4">
        <div className="grid min-w-60 flex-1 gap-1">
          <label htmlFor="risk-title" className="text-[13px] font-medium">Your own scenario</label>
          <input id="risk-title" value={title} onChange={(e) => setTitle(e.target.value)}
            placeholder="Customer data leaked by a supplier" className="rounded-lg border border-line-2 bg-surface px-3 py-2 text-sm" />
        </div>
        <Button type="submit" disabled={!title.trim() || create.isPending}>Start assessment</Button>
      </form>
      {create.isError && <p role="alert" className="text-[13px] text-bad">{create.error.message}</p>}
      <section aria-labelledby="templates-heading" className="grid gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 id="templates-heading" className="text-[15px] font-semibold">Templates</h2>
          <input aria-label="Filter templates" value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter templates"
            className="rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13px]" />
        </div>
        {library.isError && <p role="alert">{library.error.message}</p>}
        <ul className="grid gap-3 md:grid-cols-2">
          {templates.map((t) => (
            <li key={t.code} className="grid content-start gap-2 rounded-xl border border-line bg-surface p-4">
              <p className="text-[11.5px] uppercase tracking-[0.06em] text-fg-3">{t.category}</p>
              <p className="font-semibold">{t.title}</p>
              <p className="text-[13px] text-fg-2">{t.scenario}</p>
              <div>
                <Button variant="secondary" size="sm" aria-label={`Use template: ${t.title}`} disabled={create.isPending}
                  onClick={() => void start({ template_code: t.code })}>
                  Use template
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
```

- [ ] **Step 4: Implement the wizard**

`frontend/src/pages/RiskWizard.tsx`:
```tsx
import { Link, useNavigate, useParams } from "@tanstack/react-router"
import { type FormEvent, useEffect, useRef, useState } from "react"
import { useAssets } from "../api/assets"
import {
  useAllControls, useFinalizeAssessment, useMethodology, useRisk, useRiskLibrary, useSaveAssessment,
  useSetRiskControls, useUpdateRisk,
} from "../api/risks"
import type { Level, Methodology, RiskDetail } from "../api/types"
import { Button } from "../components/Button"
import { CodePicker } from "../components/CodePicker"
import { Heatmap } from "../components/Heatmap"
import { LevelPill } from "../components/LevelPill"
import { StatusPill } from "../components/StatusPill"

const STEPS = ["Scenario", "Assets", "Likelihood", "Consequence", "Controls", "Result"]
const SCALE = [1, 2, 3, 4, 5]
const input = "rounded-lg border border-line-2 bg-surface px-3 py-2 text-sm"
const heading = "text-[17px] font-semibold"

export function levelFor(methodology: Methodology, likelihood: number, consequence: number): Level {
  const score = likelihood * consequence
  const band = methodology.bands.find((b) => score >= b.min && score <= b.max)!
  return { likelihood, consequence, score, band: band.key, band_label: band.label }
}

export function RiskWizardPage() {
  const { code } = useParams({ from: "/app/risks/$code/assess" })
  const risk = useRisk(code)
  const methodology = useMethodology()
  if (risk.isError) return <p role="alert">{risk.error.message}</p>
  if (methodology.isError) return <p role="alert">{methodology.error.message}</p>
  if (!risk.data || !methodology.data) return <p role="status" className="text-fg-3">Loading…</p>
  return <Wizard risk={risk.data} methodology={methodology.data} />
}

function Wizard({ risk, methodology }: { risk: RiskDetail; methodology: Methodology }) {
  const [step, setStep] = useState(0)
  const [liveLikelihood, setLiveLikelihood] = useState<number | null>(null)
  const [liveConsequence, setLiveConsequence] = useState<number | null>(null)
  const open = useSaveAssessment(risk.code)
  const opened = useRef(risk.draft !== null)
  useEffect(() => {
    if (!opened.current && risk.status !== "closed") {
      opened.current = true
      open.mutate({})
    }
  }, [open, risk.status])

  const draft = risk.draft
  if (!draft) {
    return open.isError ? <p role="alert">{open.error.message}</p> : <p role="status" className="text-fg-3">Opening the assessment…</p>
  }
  const next = () => setStep((s) => Math.min(s + 1, STEPS.length - 1))
  const back = () => setStep((s) => Math.max(s - 1, 0))
  const likelihood = liveLikelihood ?? draft.likelihood
  const consequence = liveConsequence ?? draft.inherent?.consequence ?? null
  const position = likelihood && consequence ? levelFor(methodology, likelihood, consequence) : null

  return (
    <div className="mx-auto grid max-w-6xl gap-4">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="font-display text-[24px] font-extrabold tracking-tight">Assess {risk.code} {risk.title}</h1>
        <p className="text-[13px] text-fg-3">
          Step {step + 1} of {STEPS.length} ·{" "}
          <Link to="/risks/$code" params={{ code: risk.code }} className="text-primary underline">Save and exit</Link>
        </p>
      </header>
      <ol aria-label="Steps" className="flex flex-wrap gap-1.5">
        {STEPS.map((name, index) => (
          <li key={name}>
            <button type="button" onClick={() => setStep(index)} aria-current={index === step ? "step" : undefined}
              className="rounded-full border border-line-2 px-3 py-1 text-[12.5px] font-medium text-fg-2 aria-[current=step]:border-primary aria-[current=step]:bg-primary-soft aria-[current=step]:text-primary">
              {index + 1} {name}
            </button>
          </li>
        ))}
      </ol>
      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_300px]">
        <section className="rounded-xl border border-line bg-surface p-5">
          {step === 0 && <ScenarioStep risk={risk} onDone={next} />}
          {step === 1 && <AssetsStep risk={risk} onDone={next} onBack={back} />}
          {step === 2 && (
            <LikelihoodStep risk={risk} methodology={methodology} onLive={setLiveLikelihood} onDone={next} onBack={back} />
          )}
          {step === 3 && (
            <ConsequenceStep risk={risk} methodology={methodology} onLive={setLiveConsequence} onDone={next} onBack={back} />
          )}
          {step === 4 && <ControlsStep risk={risk} onDone={next} onBack={back} />}
          {step === 5 && <ResultStep risk={risk} methodology={methodology} onBack={back} />}
        </section>
        <LivePanel methodology={methodology} position={position} suggested={draft.suggested} />
      </div>
    </div>
  )
}

function StepButtons({ onBack, disabled, label = "Continue" }: { onBack?: () => void; disabled: boolean; label?: string }) {
  return (
    <div className="flex justify-between gap-2 border-t border-line pt-4">
      {onBack ? <Button type="button" variant="ghost" onClick={onBack}>Back</Button> : <span />}
      <Button type="submit" disabled={disabled}>{label}</Button>
    </div>
  )
}

function Failure({ error }: { error: Error | null }) {
  return error ? <p role="alert" className="text-[13px] text-bad">{error.message}</p> : null
}

function ScenarioStep({ risk, onDone }: { risk: RiskDetail; onDone: () => void }) {
  const library = useRiskLibrary()
  const update = useUpdateRisk(risk.code)
  const [title, setTitle] = useState(risk.title)
  const [description, setDescription] = useState(risk.description ?? "")
  const [category, setCategory] = useState(risk.category ?? "")
  const [approach, setApproach] = useState(risk.approach)
  const [threats, setThreats] = useState(risk.threats.map((t) => t.code))
  const [vulnerabilities, setVulnerabilities] = useState(risk.vulnerabilities.map((v) => v.code))

  async function submit(event: FormEvent) {
    event.preventDefault()
    await update.mutateAsync({
      title: title.trim(),
      description: description.trim() || null,
      category: category.trim() || null,
      approach,
      threat_codes: threats,
      vulnerability_codes: vulnerabilities,
    })
    onDone()
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <h2 className={heading}>What could happen?</h2>
      <div className="grid gap-1">
        <label htmlFor="scenario-title" className="text-[13px] font-medium">Title</label>
        <input id="scenario-title" value={title} onChange={(e) => setTitle(e.target.value)} className={input} />
      </div>
      <div className="grid gap-1">
        <label htmlFor="scenario-text" className="text-[13px] font-medium">Scenario</label>
        <textarea id="scenario-text" rows={3} value={description} onChange={(e) => setDescription(e.target.value)} className={input}
          placeholder="If … happens, then … because …" />
      </div>
      <div className="flex flex-wrap gap-4">
        <div className="grid gap-1">
          <label htmlFor="scenario-category" className="text-[13px] font-medium">Category</label>
          <input id="scenario-category" value={category} onChange={(e) => setCategory(e.target.value)} className={input} />
        </div>
        <fieldset className="grid gap-1">
          <legend className="text-[13px] font-medium">Approach</legend>
          <div className="flex gap-3 pt-1 text-[13px]">
            {[["event", "Event-based"], ["asset", "Asset-based"]].map(([value, label]) => (
              <label key={value} className="flex items-center gap-1.5">
                <input type="radio" name="approach" value={value} checked={approach === value} onChange={() => setApproach(value)} />
                {label}
              </label>
            ))}
          </div>
        </fieldset>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <CodePicker label="Threats" items={library.data?.threats ?? []} selected={threats} onChange={setThreats} />
        <CodePicker label="Vulnerabilities" items={library.data?.vulnerabilities ?? []} selected={vulnerabilities} onChange={setVulnerabilities} />
      </div>
      <Failure error={update.error} />
      <StepButtons disabled={!title.trim() || update.isPending} />
    </form>
  )
}

function AssetsStep({ risk, onDone, onBack }: { risk: RiskDetail; onDone: () => void; onBack: () => void }) {
  const assets = useAssets()
  const update = useUpdateRisk(risk.code)
  const [selected, setSelected] = useState(risk.assets.map((a) => a.id))
  const list = assets.data ?? []

  async function submit(event: FormEvent) {
    event.preventDefault()
    await update.mutateAsync({ asset_ids: selected })
    onDone()
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <h2 className={heading}>Which assets are affected?</h2>
      <p className="text-[13px] text-fg-2">
        {risk.approach === "asset" ? "Asset-based risks start from the assets they affect." : "Optional for event-based risks."}
      </p>
      {list.length === 0 ? (
        <p className="text-[13px] text-fg-3">No assets in the inventory yet.</p>
      ) : (
        <div className="grid max-h-72 gap-1 overflow-y-auto rounded-lg border border-line p-2">
          {list.map((a) => (
            <label key={a.id} className="flex items-center gap-2 text-[13px]">
              <input type="checkbox" checked={selected.includes(a.id)}
                onChange={() => setSelected((s) => (s.includes(a.id) ? s.filter((x) => x !== a.id) : [...s, a.id]))} />
              <span className="font-mono text-fg-3">{a.code}</span> {a.name}
              <span className="text-fg-3">· criticality {a.criticality}</span>
            </label>
          ))}
        </div>
      )}
      <Failure error={update.error} />
      <StepButtons onBack={onBack} disabled={update.isPending} />
    </form>
  )
}

function LikelihoodStep({ risk, methodology, onLive, onDone, onBack }: {
  risk: RiskDetail
  methodology: Methodology
  onLive: (likelihood: number) => void
  onDone: () => void
  onBack: () => void
}) {
  const save = useSaveAssessment(risk.code)
  const [value, setValue] = useState<number | null>(risk.draft?.likelihood ?? null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    await save.mutateAsync({ likelihood: value })
    onDone()
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <h2 className={heading}>How likely is it to happen?</h2>
      <fieldset className="grid gap-2">
        <legend className="sr-only">Likelihood</legend>
        {methodology.likelihood.map((option) => (
          <div key={option.level} className="flex flex-wrap items-center gap-3 rounded-lg border border-line px-3 py-2">
            <input type="radio" id={`likelihood-${option.level}`} name="likelihood" checked={value === option.level}
              aria-describedby={`likelihood-${option.level}-help`}
              onChange={() => { setValue(option.level); onLive(option.level) }} />
            <label htmlFor={`likelihood-${option.level}`} className="text-[13.5px] font-medium">
              {`${option.level} · ${option.label}`}
            </label>
            <span id={`likelihood-${option.level}-help`} className="ml-auto text-[12.5px] text-fg-3">{option.guidance}</span>
          </div>
        ))}
      </fieldset>
      <Failure error={save.error} />
      <StepButtons onBack={onBack} disabled={value === null || save.isPending} />
    </form>
  )
}

function ConsequenceStep({ risk, methodology, onLive, onDone, onBack }: {
  risk: RiskDetail
  methodology: Methodology
  onLive: (consequence: number | null) => void
  onDone: () => void
  onBack: () => void
}) {
  const save = useSaveAssessment(risk.code)
  const dimensions = methodology.consequence.dimensions
  const [ratings, setRatings] = useState<Record<string, number>>(risk.draft?.consequence ?? {})
  const highest = (values: Record<string, number>) =>
    dimensions.every((d) => values[d.key]) ? Math.max(...dimensions.map((d) => values[d.key])) : null
  const overall = highest(ratings)

  function rate(key: string, value: number) {
    const updated = { ...ratings, [key]: value }
    setRatings(updated)
    onLive(highest(updated))
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    await save.mutateAsync({ consequence: ratings })
    onDone()
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <h2 className={heading}>How bad would it be? Rate each area.</h2>
      <div className="grid gap-3">
        {dimensions.map((d) => (
          <div key={d.key} role="radiogroup" aria-label={d.label} className="grid gap-1 sm:grid-cols-[160px_auto_minmax(0,1fr)] sm:items-center">
            <span className="text-[13.5px] font-medium">{d.label}</span>
            <span className="flex gap-2">
              {SCALE.map((n) => (
                <input key={n} type="radio" name={`consequence-${d.key}`} aria-label={`${d.label} ${n}`} title={d.guidance[n - 1]}
                  checked={ratings[d.key] === n} onChange={() => rate(d.key, n)} />
              ))}
            </span>
            <span className="text-[12.5px] text-fg-3">{ratings[d.key] ? d.guidance[ratings[d.key] - 1] : "Not rated"}</span>
          </div>
        ))}
      </div>
      <p className="text-[13px] font-medium">
        {overall
          ? `Overall consequence = highest = ${overall} (${methodology.consequence.levels[overall - 1].label})`
          : "Rate every area to see the overall consequence."}
      </p>
      <Failure error={save.error} />
      <StepButtons onBack={onBack} disabled={overall === null || save.isPending} />
    </form>
  )
}

function ControlsStep({ risk, onDone, onBack }: { risk: RiskDetail; onDone: () => void; onBack: () => void }) {
  const controls = useAllControls()
  const setControls = useSetRiskControls(risk.code)
  const save = useSaveAssessment(risk.code)
  const draft = risk.draft!
  const suggested = draft.suggested
  const [links, setLinks] = useState(risk.controls.map((c) => ({ code: c.code, axis: c.axis })))
  const [adding, setAdding] = useState("")
  const [adjust, setAdjust] = useState(draft.current !== null)
  const [currentL, setCurrentL] = useState(draft.current?.likelihood ?? suggested?.likelihood ?? 1)
  const [currentC, setCurrentC] = useState(draft.current?.consequence ?? suggested?.consequence ?? 1)
  const [reason, setReason] = useState(draft.current_reason ?? "")
  const known = controls.data ?? []
  const info = (code: string) => known.find((c) => c.code === code) ?? risk.controls.find((c) => c.code === code)
  const addable = known.filter((c) => c.status !== "excluded" && !links.some((l) => l.code === c.code))

  async function submit(event: FormEvent) {
    event.preventDefault()
    await setControls.mutateAsync({ links })
    await save.mutateAsync(
      adjust
        ? { current_l: currentL, current_c: currentC, current_reason: reason.trim() || null }
        : { current_l: null, current_c: null, current_reason: null },
    )
    onDone()
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <h2 className={heading}>Which controls already reduce this risk?</h2>
      <p className="text-[13px] text-fg-2">
        A compliant control lowers the risk by one level on the axis it affects; a control at risk counts for half; at most two levels per axis.
      </p>
      {links.length === 0 ? (
        <p className="text-[13px] text-fg-3">No controls linked yet.</p>
      ) : (
        <ul className="grid gap-2">
          {links.map((link) => {
            const control = info(link.code)
            return (
              <li key={link.code} className="flex flex-wrap items-center gap-2 rounded-lg border border-line px-3 py-2 text-[13px]">
                <span className="font-mono text-fg-3">{link.code}</span>
                <span className="min-w-0 flex-1">{control?.title}</span>
                {control && <StatusPill status={control.status} />}
                <select aria-label={`Effect of ${link.code}`} value={link.axis} className={input}
                  onChange={(e) => setLinks((ls) => ls.map((l) => (l.code === link.code ? { ...l, axis: e.target.value } : l)))}>
                  <option value="likelihood">Reduces likelihood</option>
                  <option value="consequence">Reduces consequence</option>
                </select>
                <Button type="button" variant="ghost" size="sm" aria-label={`Remove ${link.code}`}
                  onClick={() => setLinks((ls) => ls.filter((l) => l.code !== link.code))}>
                  Remove
                </Button>
              </li>
            )
          })}
        </ul>
      )}
      <div className="flex flex-wrap items-end gap-2">
        <div className="grid min-w-60 flex-1 gap-1">
          <label htmlFor="add-control" className="text-[13px] font-medium">Add a mitigating control</label>
          <select id="add-control" value={adding} onChange={(e) => setAdding(e.target.value)} className={input}>
            <option value="">Choose a control…</option>
            {addable.map((c) => <option key={c.code} value={c.code}>{c.code} {c.title}</option>)}
          </select>
        </div>
        <Button type="button" variant="secondary" disabled={!adding}
          onClick={() => { setLinks((ls) => [...ls, { code: adding, axis: "likelihood" }]); setAdding("") }}>
          Link control
        </Button>
      </div>
      <div className="grid gap-2 rounded-lg bg-subtle p-3 text-[13px]">
        <p className="flex flex-wrap items-center gap-2">
          Suggested current level <LevelPill level={suggested} />
          <span className="text-fg-3">Updates when you continue.</span>
        </p>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={adjust} onChange={(e) => setAdjust(e.target.checked)} />
          Adjust the current level
        </label>
        {adjust && (
          <div className="flex flex-wrap items-end gap-2">
            {([["Current likelihood", currentL, setCurrentL], ["Current consequence", currentC, setCurrentC]] as const).map(
              ([label, value, setter]) => (
                <div key={label} className="grid gap-1">
                  <label htmlFor={label.toLowerCase().replace(" ", "-")} className="font-medium">{label}</label>
                  <select id={label.toLowerCase().replace(" ", "-")} value={value} onChange={(e) => setter(Number(e.target.value))} className={input}>
                    {SCALE.map((n) => <option key={n} value={n}>{n}</option>)}
                  </select>
                </div>
              ),
            )}
            <div className="grid min-w-60 flex-1 gap-1">
              <label htmlFor="current-reason" className="font-medium">Why is it different from the suggestion?</label>
              <textarea id="current-reason" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} className={input} />
            </div>
          </div>
        )}
      </div>
      <Failure error={setControls.error ?? save.error} />
      <StepButtons onBack={onBack} disabled={setControls.isPending || save.isPending} />
    </form>
  )
}

function ResultStep({ risk, methodology, onBack }: { risk: RiskDetail; methodology: Methodology; onBack: () => void }) {
  const save = useSaveAssessment(risk.code)
  const finalize = useFinalizeAssessment(risk.code)
  const navigate = useNavigate()
  const draft = risk.draft!
  const current = draft.current ?? draft.suggested
  const [setTarget, setSetTarget] = useState(draft.target !== null)
  const [targetL, setTargetL] = useState(draft.target?.likelihood ?? current?.likelihood ?? 1)
  const [targetC, setTargetC] = useState(draft.target?.consequence ?? current?.consequence ?? 1)
  const [rationale, setRationale] = useState(draft.rationale ?? "")
  const band = current ? methodology.bands.find((b) => b.key === current.band) : undefined

  async function finish(event: FormEvent) {
    event.preventDefault()
    await save.mutateAsync({
      target_l: setTarget ? targetL : null,
      target_c: setTarget ? targetC : null,
      rationale: rationale.trim() || null,
    })
    await finalize.mutateAsync()
    navigate({ to: "/risks/$code", params: { code: risk.code } })
  }

  return (
    <form onSubmit={finish} className="grid gap-4">
      <h2 className={heading}>Result</h2>
      <div className="flex flex-wrap items-center gap-2 text-[13px]">
        <span className="text-fg-3">Inherent</span> <LevelPill level={draft.inherent} />
        <span aria-hidden="true">→</span>
        <span className="text-fg-3">{draft.current ? "Current (adjusted)" : "Current (suggested)"}</span> <LevelPill level={current} />
      </div>
      {band && (
        <p className={band.above_appetite ? "rounded-lg bg-warn-soft px-3 py-2 text-[13px]" : "text-[13px] text-fg-2"}>
          {`${band.above_appetite ? "Above appetite. " : ""}${band.rule}`}
        </p>
      )}
      <label className="flex items-center gap-2 text-[13px]">
        <input type="checkbox" checked={setTarget} onChange={(e) => setSetTarget(e.target.checked)} />
        Set a target level for after treatment
      </label>
      {setTarget && (
        <div className="flex flex-wrap gap-2 text-[13px]">
          {([["Target likelihood", targetL, setTargetL], ["Target consequence", targetC, setTargetC]] as const).map(
            ([label, value, setter]) => (
              <div key={label} className="grid gap-1">
                <label htmlFor={label.toLowerCase().replace(" ", "-")} className="font-medium">{label}</label>
                <select id={label.toLowerCase().replace(" ", "-")} value={value} onChange={(e) => setter(Number(e.target.value))} className={input}>
                  {SCALE.map((n) => <option key={n} value={n}>{n}</option>)}
                </select>
              </div>
            ),
          )}
        </div>
      )}
      <div className="grid gap-1">
        <label htmlFor="rationale" className="text-[13px] font-medium">Rationale</label>
        <textarea id="rationale" rows={3} value={rationale} onChange={(e) => setRationale(e.target.value)} className={input} />
      </div>
      <Failure error={save.error ?? finalize.error} />
      <StepButtons onBack={onBack} disabled={save.isPending || finalize.isPending || !current} label="Finish assessment" />
    </form>
  )
}

function LivePanel({ methodology, position, suggested }: {
  methodology: Methodology
  position: Level | null
  suggested: Level | null
}) {
  const band = position ? methodology.bands.find((b) => b.key === position.band) : undefined
  return (
    <aside aria-label="Live position" className="grid content-start gap-3 rounded-xl border border-line bg-surface p-4">
      <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Live position</p>
      <Heatmap size="sm" points={[]} bands={methodology.bands} marker={position} />
      {position ? (
        <>
          <p className="text-[13px]">
            Inherent: L{position.likelihood} × C{position.consequence} = {position.score} · <b>{position.band_label}</b>
          </p>
          {band && (
            <p className={band.above_appetite ? "rounded-lg bg-warn-soft px-3 py-2 text-[13px]" : "text-[13px] text-fg-2"}>
              {`${band.above_appetite ? "Above appetite. " : ""}${band.rule}`}
            </p>
          )}
        </>
      ) : (
        <p className="text-[13px] text-fg-3">Rate the likelihood and every consequence area to see where this risk sits.</p>
      )}
      {suggested && (
        <p className="flex items-center gap-2 text-[13px]">Suggested current <LevelPill level={suggested} /></p>
      )}
    </aside>
  )
}
```

- [ ] **Step 5: Wire routes and entry points**

In `frontend/src/router.tsx` import `RiskNewPage` and `RiskWizardPage` and add:
```tsx
const riskNewRoute = createRoute({ getParentRoute: () => appRoute, path: "/risks/new", component: RiskNewPage })
const riskAssessRoute = createRoute({ getParentRoute: () => appRoute, path: "/risks/$code/assess", component: RiskWizardPage })
```
and add `riskNewRoute, riskAssessRoute` to `appRoute.addChildren([...])`.

In `frontend/src/pages/Risks.tsx` add `import { useMe } from "../auth/session"`, at the top of `RisksPage` add:
```tsx
  const me = useMe()
  const canCreate = me.data?.permissions.includes("risks:write") ?? false
```
and after the "Export XLSX" link in the header add:
```tsx
          {canCreate && (
            <Link to="/risks/new" className="rounded-lg bg-primary px-2.5 py-1 text-[13px] font-medium text-on-primary hover:bg-primary-hover">
              New risk
            </Link>
          )}
```

In `frontend/src/pages/RiskDetail.tsx`, replace `<div className="flex items-center gap-2"><RiskStatusPill status={r.status} /></div>` with:
```tsx
        <div className="flex items-center gap-2">
          {r.can_edit && !r.closed_at && (
            <Link to="/risks/$code/assess" params={{ code: r.code }}
              className="rounded-lg bg-primary px-3 py-1.5 text-[13px] font-medium text-on-primary hover:bg-primary-hover">
              {r.draft ? "Continue assessment" : r.latest ? "Reassess" : "Assess"}
            </Link>
          )}
          <RiskStatusPill status={r.status} />
        </div>
```

- [ ] **Step 6: Run tests, typecheck and build**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd frontend && npm run typecheck && npx vitest run --testTimeout=10000 && npm run build`
Expected: typecheck clean; all tests pass; build succeeds.

- [ ] **Step 7: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && git add -A && git commit -m "feat(web): new risk from templates and the six-step assessment wizard"
```

---
### Task 14: Frontend — asset inventory

**Files:**
- Create: `frontend/src/pages/Assets.tsx`
- Modify: `frontend/src/router.tsx`, `frontend/src/components/AppShell.tsx`, `frontend/src/components/icons.tsx`
- Test: `frontend/src/pages/Assets.test.tsx`

**Interfaces:**
- Consumes: `useAssets`, `useCreateAsset`, `useUpdateAsset`, labels (Task 12); `usePeople`.
- Produces: route `/assets` (`AssetsPage`); "Assets" nav item under Risk with an `asset` icon.

- [ ] **Step 1: Write the failing tests**

`frontend/src/pages/Assets.test.tsx`:
```tsx
import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { json, ME, mockApi, renderApp } from "../test/render"

const ASSET = {
  id: "a1", code: "AST-001", name: "Core banking database", type: "information",
  owner: { id: "u2", full_name: "Bilal Khan" }, classification: "restricted", confidentiality: 5, integrity: 5,
  availability: 4, criticality: 5, location: "Data centre", description: null, lifecycle: "in_use",
}
const base = {
  "GET /auth/me": () => json(200, ME),
  "GET /assets": () => json(200, [ASSET]),
  "GET /people": () => json(200, [{ id: "u2", full_name: "Bilal Khan", email: "bilal@acme.com", roles: ["control_owner"] }]),
}

test("lists assets with their ratings", async () => {
  mockApi(base)
  renderApp("/assets")
  const row = await screen.findByRole("row", { name: /AST-001/ })
  expect(row).toHaveTextContent("Core banking database")
  expect(row).toHaveTextContent("Restricted")
  expect(row).toHaveTextContent("5 / 5 / 4")
  expect(row).toHaveTextContent("Bilal Khan")
})

test("a manager adds an asset", async () => {
  const calls = mockApi({ ...base, "POST /assets": () => json(201, ASSET) })
  renderApp("/assets")
  await userEvent.click(await screen.findByRole("button", { name: "Add asset" }))
  await userEvent.type(screen.getByLabelText("Name"), "File server")
  await userEvent.selectOptions(screen.getByLabelText("Type"), "server")
  await userEvent.selectOptions(screen.getByLabelText("Confidentiality"), "5")
  await userEvent.click(screen.getByRole("button", { name: "Save asset" }))
  await screen.findByRole("button", { name: "Add asset" })
  const post = calls.find((c) => c.method === "POST")!
  expect(JSON.parse(String(post.init.body))).toEqual({
    name: "File server", type: "server", owner_id: null, classification: "internal", confidentiality: 5,
    integrity: 3, availability: 3, location: null, description: null, lifecycle: "in_use",
  })
})

test("an asset is retired from the edit form", async () => {
  const calls = mockApi({ ...base, "PATCH /assets/a1": () => json(200, { ...ASSET, lifecycle: "retired" }) })
  renderApp("/assets")
  await userEvent.click(await screen.findByRole("button", { name: "Edit AST-001" }))
  expect(screen.getByLabelText("Name")).toHaveValue("Core banking database")
  await userEvent.selectOptions(screen.getByLabelText("Lifecycle"), "retired")
  await userEvent.click(screen.getByRole("button", { name: "Save asset" }))
  await screen.findByRole("button", { name: "Add asset" })
  const patch = calls.find((c) => c.method === "PATCH")!
  expect(JSON.parse(String(patch.init.body))).toMatchObject({ lifecycle: "retired", owner_id: "u2" })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd frontend && npx vitest run src/pages/Assets.test.tsx --testTimeout=10000`
Expected: FAIL — `/assets` renders "Not Found".

- [ ] **Step 3: Implement**

`frontend/src/pages/Assets.tsx`:
```tsx
import { type FormEvent, useState } from "react"
import {
  ASSET_TYPE_LABEL, type AssetInput, CLASSIFICATION_LABEL, LIFECYCLE_LABEL, useAssets, useCreateAsset, useUpdateAsset,
} from "../api/assets"
import { usePeople } from "../api/people"
import type { Asset } from "../api/types"
import { useMe } from "../auth/session"
import { Button } from "../components/Button"

const input = "rounded-lg border border-line-2 bg-surface px-3 py-2 text-sm"
const RATINGS = [1, 2, 3, 4, 5]

export function AssetsPage() {
  const me = useMe()
  const perms = me.data?.permissions ?? []
  const canManage = perms.includes("assets:write")
  const [showRetired, setShowRetired] = useState(false)
  const assets = useAssets(showRetired)
  const [editing, setEditing] = useState<Asset | "new" | null>(null)
  const canEdit = (asset: Asset) => canManage || (perms.includes("assets:write_own") && asset.owner?.id === me.data?.id)
  const rows = assets.data ?? []

  return (
    <div className="mx-auto grid max-w-6xl gap-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Risk</p>
          <h1 className="font-display text-[26px] font-extrabold tracking-tight">Assets</h1>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-[13px]">
            <input type="checkbox" checked={showRetired} onChange={(e) => setShowRetired(e.target.checked)} />
            Show retired
          </label>
          {canManage && !editing && <Button onClick={() => setEditing("new")}>Add asset</Button>}
        </div>
      </header>
      {editing && (
        <AssetForm key={editing === "new" ? "new" : editing.id} asset={editing === "new" ? null : editing}
          canChangeOwner={canManage} onDone={() => setEditing(null)} />
      )}
      <section className="overflow-x-auto rounded-xl border border-line bg-surface">
        {assets.isError && <p role="alert" className="p-4">{assets.error.message}</p>}
        <table className="w-full text-[13.5px]">
          <thead>
            <tr className="text-left text-[11.5px] uppercase tracking-[0.06em] text-fg-3">
              {["ID", "Name", "Type", "Owner", "Classification", "C / I / A", "Criticality", "Lifecycle", ""].map((h, i) => (
                <th key={i} className="px-3.5 py-3 font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => (
              <tr key={a.id} className="border-t border-line hover:bg-subtle">
                <td className="whitespace-nowrap px-3.5 py-2.5 font-mono text-[12.5px] text-fg-3">{a.code}</td>
                <td className="min-w-48 px-3.5 py-2.5">{a.name}</td>
                <td className="px-3.5 py-2.5 text-fg-2">{ASSET_TYPE_LABEL[a.type] ?? a.type}</td>
                <td className="whitespace-nowrap px-3.5 py-2.5 text-fg-2">{a.owner?.full_name ?? "Unassigned"}</td>
                <td className="px-3.5 py-2.5 text-fg-2">{CLASSIFICATION_LABEL[a.classification] ?? a.classification}</td>
                <td className="whitespace-nowrap px-3.5 py-2.5 tabular-nums">{`${a.confidentiality} / ${a.integrity} / ${a.availability}`}</td>
                <td className="px-3.5 py-2.5 font-semibold tabular-nums">{a.criticality}</td>
                <td className="px-3.5 py-2.5 text-fg-2">{LIFECYCLE_LABEL[a.lifecycle] ?? a.lifecycle}</td>
                <td className="px-3.5 py-2.5 text-right">
                  {canEdit(a) && (
                    <Button variant="ghost" size="sm" aria-label={`Edit ${a.code}`} onClick={() => setEditing(a)}>Edit</Button>
                  )}
                </td>
              </tr>
            ))}
            {assets.isSuccess && rows.length === 0 && (
              <tr>
                <td colSpan={9} className="px-3.5 py-8 text-center text-fg-3">
                  No assets yet. Add the information, systems and services in scope.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  )
}

function AssetForm({ asset, canChangeOwner, onDone }: { asset: Asset | null; canChangeOwner: boolean; onDone: () => void }) {
  const people = usePeople()
  const create = useCreateAsset()
  const update = useUpdateAsset()
  const [name, setName] = useState(asset?.name ?? "")
  const [type, setType] = useState(asset?.type ?? "information")
  const [owner, setOwner] = useState(asset?.owner?.id ?? "")
  const [classification, setClassification] = useState(asset?.classification ?? "internal")
  const [ratings, setRatings] = useState({
    confidentiality: asset?.confidentiality ?? 3,
    integrity: asset?.integrity ?? 3,
    availability: asset?.availability ?? 3,
  })
  const [location, setLocation] = useState(asset?.location ?? "")
  const [description, setDescription] = useState(asset?.description ?? "")
  const [lifecycle, setLifecycle] = useState(asset?.lifecycle ?? "in_use")
  const error = create.error ?? update.error

  async function submit(event: FormEvent) {
    event.preventDefault()
    const body: AssetInput = {
      name: name.trim(), type, classification, ...ratings,
      location: location.trim() || null, description: description.trim() || null, lifecycle,
    }
    if (canChangeOwner) body.owner_id = owner || null
    if (asset) await update.mutateAsync({ id: asset.id, ...body })
    else await create.mutateAsync({ owner_id: null, ...body })
    onDone()
  }

  const select = (id: string, label: string, value: string, onChange: (v: string) => void, options: Record<string, string>, disabled = false) => (
    <div className="grid gap-1">
      <label htmlFor={id} className="text-[13px] font-medium">{label}</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)} disabled={disabled} className={input}>
        {Object.entries(options).map(([key, text]) => <option key={key} value={key}>{text}</option>)}
      </select>
    </div>
  )

  return (
    <form onSubmit={submit} className="grid gap-3 rounded-xl border border-line bg-surface p-5">
      <h2 className="text-[15px] font-semibold">{asset ? `Edit ${asset.code}` : "New asset"}</h2>
      <div className="grid gap-3 md:grid-cols-3">
        <div className="grid gap-1 md:col-span-2">
          <label htmlFor="asset-name" className="text-[13px] font-medium">Name</label>
          <input id="asset-name" value={name} onChange={(e) => setName(e.target.value)} className={input} />
        </div>
        {select("asset-type", "Type", type, setType, ASSET_TYPE_LABEL)}
        {select("asset-owner", "Owner", owner, setOwner,
          { "": "Unassigned", ...Object.fromEntries((people.data ?? []).map((p) => [p.id, p.full_name])) }, !canChangeOwner)}
        {select("asset-classification", "Classification", classification, setClassification, CLASSIFICATION_LABEL)}
        {select("asset-lifecycle", "Lifecycle", lifecycle, setLifecycle, LIFECYCLE_LABEL)}
        {(["confidentiality", "integrity", "availability"] as const).map((key) => (
          <div key={key} className="grid gap-1">
            <label htmlFor={`asset-${key}`} className="text-[13px] font-medium">{key.charAt(0).toUpperCase() + key.slice(1)}</label>
            <select id={`asset-${key}`} value={ratings[key]} className={input}
              onChange={(e) => setRatings((r) => ({ ...r, [key]: Number(e.target.value) }))}>
              {RATINGS.map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
        ))}
        <div className="grid gap-1 md:col-span-3">
          <label htmlFor="asset-location" className="text-[13px] font-medium">Location</label>
          <input id="asset-location" value={location} onChange={(e) => setLocation(e.target.value)} className={input} />
        </div>
        <div className="grid gap-1 md:col-span-3">
          <label htmlFor="asset-description" className="text-[13px] font-medium">Description</label>
          <textarea id="asset-description" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} className={input} />
        </div>
      </div>
      {error && <p role="alert" className="text-[13px] text-bad">{error.message}</p>}
      <div className="flex gap-2">
        <Button type="submit" disabled={!name.trim() || create.isPending || update.isPending}>Save asset</Button>
        <Button type="button" variant="ghost" onClick={onDone}>Cancel</Button>
      </div>
    </form>
  )
}
```

Add to `PATHS` in `frontend/src/components/icons.tsx`:
```ts
  asset: "M4 8h16v11H4zM9 8V5h6v3M4 13h16",
```

In `frontend/src/router.tsx` import `AssetsPage` and add `const assetsRoute = createRoute({ getParentRoute: () => appRoute, path: "/assets", component: AssetsPage })` to `appRoute.addChildren([...])`.

In `frontend/src/components/AppShell.tsx` widen `NavItem.to` to `"/" | "/controls" | "/evidence" | "/risks" | "/assets"` and change the Risk group to:
```tsx
  { group: "Risk", items: [{ label: "Risks", icon: "risk", to: "/risks" }, { label: "Assets", icon: "asset", to: "/assets" }] },
```

- [ ] **Step 4: Run tests, typecheck and build**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd frontend && npm run typecheck && npx vitest run --testTimeout=10000 && npm run build`
Expected: typecheck clean; all tests pass; build succeeds.

- [ ] **Step 5: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && git add -A && git commit -m "feat(web): asset inventory page"
```

---

### Task 15: Frontend — Statement of Applicability

**Files:**
- Create: `frontend/src/api/soa.ts`, `frontend/src/pages/Soa.tsx`
- Modify: `frontend/src/api/types.ts`, `frontend/src/router.tsx`, `frontend/src/components/AppShell.tsx`
- Test: `frontend/src/pages/Soa.test.tsx`

**Interfaces:**
- Consumes: backend Tasks 10–11; `IMPLEMENTATION_LABEL` (`api/controls`); `Icon`, `ControlId`.
- Produces: types `SoaSource`, `SoaItem`, `SoaChecks`, `Soa`, `SoaVersion`; hooks `useSoa`, `useUpdateSoaItems`, `useSoaVersions`, `useSubmitSoa`, `useDecideSoa`; `SOURCE_LABEL`; route `/soa` (`SoaPage`); SoA nav item enabled.

- [ ] **Step 1: Write the failing tests**

`frontend/src/pages/Soa.test.tsx`:
```tsx
import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { json, ME, mockApi, renderApp } from "../test/render"

const item = (code: string, title: string) => ({
  code, title, theme: "Organizational", applicable: true, sources: [], justification: null, exclusion_reason: null,
  implementation_status: "not_started", status: "not_started", evidence_verified: 0, evidence_required: 2, owner: null,
})
const SOA = {
  items: [
    item("A.5.1", "Policies for information security"),
    item("A.5.2", "Information security roles and responsibilities"),
    item("A.8.30", "Outsourced development"),
  ],
  checks: { orphans: ["A.5.1", "A.5.2", "A.8.30"], excluded_mitigating: [], untreated_risks: ["R-004"], ok: false },
}
const base = {
  "GET /auth/me": () => json(200, ME),
  "GET /soa": () => json(200, SOA),
  "GET /soa/versions": () => json(200, []),
}

test("shows the traceability checks and blocks submission until they pass", async () => {
  mockApi(base)
  renderApp("/soa")
  const checks = await screen.findByRole("region", { name: "Traceability checks" })
  expect(checks).toHaveTextContent("3 applicable controls without a justification")
  expect(checks).toHaveTextContent("1 risk above appetite without a treatment")
  expect(within(checks).getByRole("link", { name: "R-004" })).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Submit for approval" })).toBeDisabled()
})

test("excluding a control asks for a reason", async () => {
  const calls = mockApi({ ...base, "PATCH /soa/items": () => json(200, SOA) })
  renderApp("/soa")
  await userEvent.click(await screen.findByRole("button", { name: "Exclude A.8.30" }))
  await userEvent.type(screen.getByLabelText("Reason for excluding A.8.30"), "All development is in-house.")
  await userEvent.click(screen.getByRole("button", { name: "Exclude" }))
  const patch = calls.find((c) => c.method === "PATCH")!
  expect(JSON.parse(String(patch.init.body))).toEqual({
    codes: ["A.8.30"], applicable: false, exclusion_reason: "All development is in-house.",
  })
})

test("justification sources are set for several controls at once", async () => {
  const calls = mockApi({ ...base, "PATCH /soa/items": () => json(200, SOA) })
  renderApp("/soa")
  await userEvent.click(await screen.findByRole("checkbox", { name: "Select A.5.1" }))
  await userEvent.click(screen.getByRole("checkbox", { name: "Select A.5.2" }))
  const bulk = screen.getByRole("region", { name: "Bulk edit" })
  await userEvent.click(within(bulk).getByRole("checkbox", { name: "Best practice" }))
  await userEvent.click(within(bulk).getByRole("button", { name: "Apply to 2 controls" }))
  const patch = calls.find((c) => c.method === "PATCH")!
  expect(JSON.parse(String(patch.init.body))).toEqual({ codes: ["A.5.1", "A.5.2"], sources: ["best_practice"] })
})

test("an executive approves a pending version", async () => {
  const pending = {
    version_no: 1, status: "pending", prepared_by: "Sana Malik", prepared_at: "2026-10-08T09:00:00Z",
    decided_by: null, decided_at: null, decision_note: null, applicable: 93, excluded: 0,
  }
  const calls = mockApi({
    ...base,
    "GET /auth/me": () => json(200, { ...ME, permissions: [...ME.permissions, "soa:approve"] }),
    "GET /soa/versions": () => json(200, [pending]),
    "POST /soa/versions/1/approve": () => json(200, { ...pending, status: "approved", decided_by: "Tariq Qureshi" }),
  })
  renderApp("/soa")
  expect(await screen.findByText("v1 is waiting for approval")).toBeInTheDocument()
  await userEvent.click(screen.getByRole("button", { name: "Approve v1" }))
  expect(calls.some((c) => c.method === "POST" && c.url.pathname === "/api/v1/soa/versions/1/approve")).toBe(true)
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd frontend && npx vitest run src/pages/Soa.test.tsx --testTimeout=10000`
Expected: FAIL — `/soa` renders "Not Found".

- [ ] **Step 3: Implement types and hooks**

Append to `frontend/src/api/types.ts`:
```ts
export interface SoaSource { kind: string; label: string; ref: string | null }
export interface SoaItem {
  code: string
  title: string
  theme: string | null
  applicable: boolean
  sources: SoaSource[]
  justification: string | null
  exclusion_reason: string | null
  implementation_status: string
  status: string
  evidence_verified: number
  evidence_required: number
  owner: string | null
}
export interface SoaChecks {
  orphans: string[]
  excluded_mitigating: { code: string; risks: string[] }[]
  untreated_risks: string[]
  ok: boolean
}
export interface Soa { items: SoaItem[]; checks: SoaChecks }
export interface SoaVersion {
  version_no: number
  status: string
  prepared_by: string | null
  prepared_at: string
  decided_by: string | null
  decided_at: string | null
  decision_note: string | null
  applicable: number
  excluded: number
}
```

`frontend/src/api/soa.ts`:
```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"
import type { Soa, SoaVersion } from "./types"

export const SOURCE_LABEL: Record<string, string> = {
  legal: "Legal or regulatory",
  contractual: "Contractual",
  business: "Business requirement",
  best_practice: "Best practice",
}

export function useSoa() {
  return useQuery({ queryKey: ["soa"], queryFn: () => api<Soa>("/soa") })
}

export function useSoaVersions() {
  return useQuery({ queryKey: ["soa-versions"], queryFn: () => api<SoaVersion[]>("/soa/versions") })
}

export function useUpdateSoaItems() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      codes: string[]
      applicable?: boolean
      sources?: string[]
      justification?: string | null
      exclusion_reason?: string | null
    }) => api<Soa>("/soa/items", { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: (soa) => {
      queryClient.setQueryData(["soa"], soa)
      queryClient.invalidateQueries({ queryKey: ["controls"] })
      queryClient.invalidateQueries({ queryKey: ["readiness"] })
    },
  })
}

export function useSubmitSoa() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (_body: void) => api<SoaVersion>("/soa/versions", { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["soa-versions"] }),
  })
}

export function useDecideSoa() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ version, decision, reason }: { version: number; decision: "approve" | "return"; reason?: string }) =>
      api<SoaVersion>(`/soa/versions/${version}/${decision}`, {
        method: "POST",
        body: decision === "return" ? JSON.stringify({ reason }) : undefined,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["soa-versions"] }),
  })
}
```

- [ ] **Step 4: Implement the page**

`frontend/src/pages/Soa.tsx`:
```tsx
import { Link } from "@tanstack/react-router"
import { type FormEvent, Fragment, useState } from "react"
import { IMPLEMENTATION_LABEL } from "../api/controls"
import { SOURCE_LABEL, useDecideSoa, useSoa, useSoaVersions, useSubmitSoa, useUpdateSoaItems } from "../api/soa"
import type { SoaChecks, SoaItem, SoaVersion } from "../api/types"
import { useMe } from "../auth/session"
import { Button } from "../components/Button"
import { ControlId } from "../components/ControlId"
import { Icon } from "../components/icons"
import { formatDate } from "../lib/format"

const VERSION_STATUS: Record<string, string> = { pending: "Waiting for approval", approved: "Approved", returned: "Returned" }
const input = "rounded-lg border border-line-2 bg-surface px-3 py-2 text-sm"
const linkClass = "rounded-lg border border-line-2 bg-surface px-2.5 py-1 text-[13px] font-medium hover:border-fg-3"
const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? "" : "s"}`

export function SoaPage() {
  const me = useMe()
  const perms = me.data?.permissions ?? []
  const canEdit = perms.includes("soa:write")
  const canApprove = perms.includes("soa:approve")
  const soa = useSoa()
  const versions = useSoaVersions()
  const submit = useSubmitSoa()
  const update = useUpdateSoaItems()
  const [selected, setSelected] = useState<string[]>([])
  const [excluding, setExcluding] = useState<string | null>(null)

  if (soa.isPending) return <p role="status" className="text-fg-3">Loading…</p>
  if (soa.isError) return <p role="alert">{soa.error.message}</p>
  const { items, checks } = soa.data
  const pending = versions.data?.find((v) => v.status === "pending")
  const approved = versions.data?.find((v) => v.status === "approved")
  const toggle = (code: string) =>
    setSelected((s) => (s.includes(code) ? s.filter((c) => c !== code) : [...s, code]))

  return (
    <div className="mx-auto grid max-w-6xl gap-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Comply</p>
          <h1 className="font-display text-[26px] font-extrabold tracking-tight">Statement of Applicability</h1>
          <p className="mt-1 text-[13px] text-fg-2">
            {approved && approved.decided_at
              ? `Approved v${approved.version_no} · ${formatDate(approved.decided_at)}`
              : "No approved version yet"}
            {pending ? ` · ` : ""}
            {pending && <span>{`v${pending.version_no} is waiting for approval`}</span>}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <a href="/api/v1/soa/export.xlsx" className={linkClass}>Export XLSX</a>
          {canEdit && (
            <Button onClick={() => submit.mutate()} disabled={!checks.ok || Boolean(pending) || submit.isPending}>
              Submit for approval
            </Button>
          )}
        </div>
      </header>
      {submit.isError && <p role="alert" className="text-[13px] text-bad">{submit.error.message}</p>}
      {update.isError && <p role="alert" className="text-[13px] text-bad">{update.error.message}</p>}
      <Checks checks={checks} />
      {canEdit && selected.length > 0 && <BulkSources codes={selected} onDone={() => setSelected([])} />}
      <section className="overflow-x-auto rounded-xl border border-line bg-surface">
        <table className="w-full text-[13.5px]">
          <thead>
            <tr className="text-left text-[11.5px] uppercase tracking-[0.06em] text-fg-3">
              {canEdit && <th className="px-3.5 py-3"><span className="sr-only">Select</span></th>}
              {["ID", "Control", "Applicable", "Justification", "Implementation", "Evidence"].map((h) => (
                <th key={h} className="px-3.5 py-3 font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((row) => (
              <Fragment key={row.code}>
                <tr className="border-t border-line align-top hover:bg-subtle">
                  {canEdit && (
                    <td className="px-3.5 py-2.5">
                      <input type="checkbox" aria-label={`Select ${row.code}`} checked={selected.includes(row.code)}
                        onChange={() => toggle(row.code)} />
                    </td>
                  )}
                  <td className="px-3.5 py-2.5"><ControlId code={row.code} /></td>
                  <td className="min-w-56 px-3.5 py-2.5">
                    <Link to="/controls/$code" params={{ code: row.code }} className="hover:text-primary">{row.title}</Link>
                  </td>
                  <td className="whitespace-nowrap px-3.5 py-2.5">
                    <Applicability row={row} canEdit={canEdit} onExclude={() => setExcluding(row.code)}
                      onInclude={() => update.mutate({ codes: [row.code], applicable: true })} />
                  </td>
                  <td className="px-3.5 py-2.5"><Justification row={row} /></td>
                  <td className="px-3.5 py-2.5 text-fg-2">
                    {row.applicable ? IMPLEMENTATION_LABEL[row.implementation_status] ?? row.implementation_status : "—"}
                  </td>
                  <td className="whitespace-nowrap px-3.5 py-2.5 tabular-nums text-fg-2">
                    {row.applicable ? `${row.evidence_verified} of ${row.evidence_required}` : "—"}
                  </td>
                </tr>
                {excluding === row.code && (
                  <tr>
                    <td colSpan={canEdit ? 7 : 6} className="bg-subtle px-3.5 py-3">
                      <ExcludeForm code={row.code} onDone={() => setExcluding(null)} />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </section>
      <Versions versions={versions.data ?? []} canApprove={canApprove} />
    </div>
  )
}

function Checks({ checks }: { checks: SoaChecks }) {
  const lines = [
    { ok: checks.orphans.length === 0, text: `${plural(checks.orphans.length, "applicable control")} without a justification` },
    {
      ok: checks.excluded_mitigating.length === 0,
      text: `${plural(checks.excluded_mitigating.length, "excluded control")} that mitigate a risk`,
    },
    {
      ok: checks.untreated_risks.length === 0,
      text: `${plural(checks.untreated_risks.length, "risk")} above appetite without a treatment`,
    },
  ]
  return (
    <section aria-label="Traceability checks"
      className={`grid gap-2 rounded-xl border px-5 py-3 text-[13px] ${checks.ok ? "border-ok/30 bg-ok-soft" : "border-warn/30 bg-warn-soft"}`}>
      <ul className="flex flex-wrap gap-x-6 gap-y-1">
        {lines.map((line) => (
          <li key={line.text} className={`flex items-center gap-1.5 ${line.ok ? "text-ok" : "text-warn"}`}>
            <Icon name={line.ok ? "pass" : "warn"} size={14} />
            <span className="text-fg">{line.text}</span>
          </li>
        ))}
      </ul>
      {checks.excluded_mitigating.map((e) => (
        <p key={e.code}>{`${e.code} is excluded but mitigates ${e.risks.join(", ")}.`}</p>
      ))}
      {checks.untreated_risks.length > 0 && (
        <p className="flex flex-wrap items-center gap-1.5">
          Choose a treatment for:
          {checks.untreated_risks.map((code) => (
            <Link key={code} to="/risks/$code" params={{ code }} className="font-mono text-primary underline">{code}</Link>
          ))}
        </p>
      )}
    </section>
  )
}

function Applicability({ row, canEdit, onExclude, onInclude }: {
  row: SoaItem
  canEdit: boolean
  onExclude: () => void
  onInclude: () => void
}) {
  if (!canEdit) return <span>{row.applicable ? "Yes" : "No"}</span>
  return row.applicable ? (
    <Button variant="ghost" size="sm" aria-label={`Exclude ${row.code}`} onClick={onExclude}>● Yes</Button>
  ) : (
    <Button variant="ghost" size="sm" aria-label={`Include ${row.code}`} onClick={onInclude}>○ No</Button>
  )
}

function Justification({ row }: { row: SoaItem }) {
  if (!row.applicable) return <span className="text-fg-2">{`“${row.exclusion_reason ?? ""}”`}</span>
  if (row.sources.length === 0) return <span className="text-warn">No justification</span>
  return (
    <span className="flex flex-wrap gap-1">
      {row.sources.map((s) =>
        s.kind === "risk" && s.ref ? (
          <Link key={s.label} to="/risks/$code" params={{ code: s.ref }} className="rounded-md bg-primary-soft px-1.5 py-0.5 text-[12px] text-primary">
            {s.label}
          </Link>
        ) : (
          <span key={s.label} className="rounded-md bg-subtle px-1.5 py-0.5 text-[12px]">{s.label}</span>
        ),
      )}
    </span>
  )
}

function ExcludeForm({ code, onDone }: { code: string; onDone: () => void }) {
  const update = useUpdateSoaItems()
  const [reason, setReason] = useState("")
  const id = `exclude-${code.replace(/\./g, "-")}`

  async function submit(event: FormEvent) {
    event.preventDefault()
    await update.mutateAsync({ codes: [code], applicable: false, exclusion_reason: reason.trim() })
    onDone()
  }

  return (
    <form onSubmit={submit} className="grid max-w-xl gap-2">
      <label htmlFor={id} className="text-[13px] font-medium">{`Reason for excluding ${code}`}</label>
      <textarea id={id} rows={2} value={reason} onChange={(e) => setReason(e.target.value)} className={input} />
      {update.isError && <p role="alert" className="text-[13px] text-bad">{update.error.message}</p>}
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={!reason.trim() || update.isPending}>Exclude</Button>
        <Button type="button" size="sm" variant="ghost" onClick={onDone}>Cancel</Button>
      </div>
    </form>
  )
}

function BulkSources({ codes, onDone }: { codes: string[]; onDone: () => void }) {
  const update = useUpdateSoaItems()
  const [kinds, setKinds] = useState<string[]>([])

  async function apply() {
    await update.mutateAsync({ codes, sources: kinds })
    onDone()
  }

  return (
    <section aria-label="Bulk edit" className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-surface px-5 py-3 text-[13px]">
      <span className="font-medium">{codes.length} selected · justification sources:</span>
      {Object.entries(SOURCE_LABEL).map(([kind, label]) => (
        <label key={kind} className="flex items-center gap-1.5">
          <input type="checkbox" checked={kinds.includes(kind)}
            onChange={() => setKinds((k) => (k.includes(kind) ? k.filter((x) => x !== kind) : [...k, kind]))} />
          {label}
        </label>
      ))}
      <Button size="sm" onClick={() => void apply()} disabled={update.isPending}>
        {`Apply to ${plural(codes.length, "control")}`}
      </Button>
    </section>
  )
}

function Versions({ versions, canApprove }: { versions: SoaVersion[]; canApprove: boolean }) {
  const decide = useDecideSoa()
  const [returning, setReturning] = useState<number | null>(null)
  const [reason, setReason] = useState("")

  return (
    <section aria-labelledby="versions-heading" className="rounded-xl border border-line bg-surface">
      <h2 id="versions-heading" className="border-b border-line px-5 py-3.5 text-[15px] font-semibold">Versions</h2>
      {decide.isError && <p role="alert" className="px-5 py-2 text-[13px] text-bad">{decide.error.message}</p>}
      {versions.length === 0 ? (
        <p className="px-5 py-4 text-[13px] text-fg-3">No version has been submitted yet.</p>
      ) : (
        <ul>
          {versions.map((v) => (
            <li key={v.version_no} className="grid gap-2 border-b border-line px-5 py-3 text-[13px] last:border-0">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  <b>{`v${v.version_no}`}</b> · {VERSION_STATUS[v.status] ?? v.status} · prepared by {v.prepared_by ?? "unknown"}{" "}
                  on {formatDate(v.prepared_at)}
                  {v.decided_by && v.decided_at ? ` · ${v.status} by ${v.decided_by} on ${formatDate(v.decided_at)}` : ""}
                  {` · ${v.applicable} applicable, ${v.excluded} excluded`}
                </span>
                <span className="flex items-center gap-2">
                  <a href={`/api/v1/soa/versions/${v.version_no}/export.xlsx`} className={linkClass}>Export</a>
                  {canApprove && v.status === "pending" && (
                    <>
                      <Button size="sm" aria-label={`Approve v${v.version_no}`} disabled={decide.isPending}
                        onClick={() => decide.mutate({ version: v.version_no, decision: "approve" })}>
                        Approve
                      </Button>
                      <Button size="sm" variant="secondary" onClick={() => setReturning(v.version_no)}>Return</Button>
                    </>
                  )}
                </span>
              </div>
              {v.decision_note && <p className="text-fg-2">{`“${v.decision_note}”`}</p>}
              {returning === v.version_no && (
                <form className="grid max-w-xl gap-2" onSubmit={(e) => {
                  e.preventDefault()
                  decide.mutate({ version: v.version_no, decision: "return", reason: reason.trim() }, {
                    onSuccess: () => { setReturning(null); setReason("") },
                  })
                }}>
                  <label htmlFor={`return-${v.version_no}`} className="font-medium">What needs to change?</label>
                  <textarea id={`return-${v.version_no}`} rows={2} value={reason} onChange={(e) => setReason(e.target.value)} className={input} />
                  <div><Button type="submit" size="sm" disabled={!reason.trim()}>Return to the preparer</Button></div>
                </form>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
```

In `frontend/src/router.tsx` import `SoaPage` and add `const soaRoute = createRoute({ getParentRoute: () => appRoute, path: "/soa", component: SoaPage })` to `appRoute.addChildren([...])`.

In `frontend/src/components/AppShell.tsx` widen `NavItem.to` to `"/" | "/controls" | "/evidence" | "/soa" | "/risks" | "/assets"` and change the SoA item to `{ label: "SoA", icon: "soa", to: "/soa" }`.

- [ ] **Step 5: Run tests, typecheck and build**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd frontend && npm run typecheck && npx vitest run --testTimeout=10000 && npm run build`
Expected: typecheck clean; all tests pass; build succeeds.

- [ ] **Step 6: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && git add -A && git commit -m "feat(web): statement of applicability with checks, bulk justification and approval"
```

---

### Task 16: Documentation, vault notes and smoke test

**Files:**
- Modify: `README.md`, `deploy/smoke.sh`, `E:/Work/GRC Tool/Assayr-Vault/03-Product/Risk Methodology.md`, `E:/Work/GRC Tool/Assayr-Vault/03-Product/Requirements/FR-06 Risk Management.md`, `FR-07 Statement of Applicability.md`, `FR-08 Asset Inventory.md`
- Create: `E:/Work/GRC Tool/Assayr-Vault/06-Architecture/ADRs/ADR-011 Derived risk status.md`

**Interfaces:**
- Consumes: everything above.
- Produces: documentation only; the smoke test also proves the risk methodology and the SoA are served by a fresh install.

- [ ] **Step 1: Extend the smoke test**

In `deploy/smoke.sh`, insert before `compose exec -T api assayr audit-verify`:
```bash
curl -fsS -b "$JAR" "$BASE/api/v1/risk-methodology" | grep -q '"key":"critical"' \
  || { echo "The risk methodology is missing (did assayr seed run?)" >&2; exit 1; }
soa_rows="$(curl -fsS -b "$JAR" "$BASE/api/v1/soa" | grep -o '"code":"A\.[0-9.]*"' | wc -l)"
[ "$soa_rows" -eq 93 ] || { echo "Expected 93 controls in the SoA, got $soa_rows" >&2; exit 1; }
echo "Risk methodology and SoA served"
```
Run (Docker available): `cd "E:/Work/GRC Tool/assayr" && deploy/smoke.sh` → ends with `Smoke test passed …`. Without a Docker daemon, record that it was not run and validate the compose file instead (`cd deploy && docker compose --env-file assayr.env config --quiet`).

- [ ] **Step 2: Update the README**

In `README.md`, after the first paragraph add:
```markdown
What it covers today: the ISO/IEC 27001:2022 catalogue with evidence slots, evidence upload with automatic verification and review,
derived control status and readiness, a risk register with a guided assessment wizard, treatment and residual-risk acceptance,
an asset inventory, and a Statement of Applicability with traceability checks and executive approval.
```
and change the `assayr seed` row of the Administration table to:
```markdown
| `assayr seed` | Load the ISO/IEC 27001:2022 catalogue, the risk methodology and the threat, vulnerability and template libraries (safe to repeat) |
```

- [ ] **Step 3: Update the vault**

Create `E:/Work/GRC Tool/Assayr-Vault/06-Architecture/ADRs/ADR-011 Derived risk status.md`:
```markdown
---
adr: 11
status: Accepted
date: 2026-10-08
tags: [adr]
---

# ADR-011 Derived risk status

**Context.** A risk moves through assessment, treatment, acceptance and review ([[State Machines]]). Letting people set the status by hand drifts from reality: an "accepted" risk whose acceptance expired, or "in treatment" with every action finished.

**Decision.** As with controls ([[ADR-005 Derived control status]]), the risk status is computed from facts and cached on the row: closed → no finalized assessment (draft) → an open reassessment (reassessing) → review date passed or acceptance lapsed (review due) → valid acceptance of the latest assessment (accepted) → treatment option and action progress (treated, in treatment, treatment planned) → assessed. Every change to a risk, its assessment, actions or acceptance recalculates it, and the scheduled check (`assayr worker`) refreshes all risks so dates take effect without anyone touching the risk.

**Consequences.** + The register never shows a stale status; auditors can trace each status to its facts. − Status cannot be overridden by hand; to change it, change the underlying fact (for example accept the risk, finish an action or close it with a reason).
```

In `E:/Work/GRC Tool/Assayr-Vault/03-Product/Risk Methodology.md`, under the "## 4. Risk level and appetite" table add:
```markdown
> Implementation note: the bands are stored as contiguous score ranges so every score has a band — Very low 1–3, Low 4–6, Medium 7–10, High 11–16, Critical 17–25. Scores 7, 11, 13, 14, 17–19 and 21–24 cannot occur with two 1–5 ratings, so the result is the same as the table above.
```

Append to `FR-06 Risk Management.md`, `FR-07 Statement of Applicability.md` and `FR-08 Asset Inventory.md` respectively:
```markdown
## Build status (Phase 1b, Oct 2026)
Done: FR-06.2, 06.3, 06.4 (threats and vulnerabilities extendable; templates read-only), 06.5 (controls and assets), 06.6, 06.7, 06.8, 06.9, 06.11, register and treatment plan as XLSX (06.13 without PDF). Methodology is versioned but not yet editable (06.1, comes with [[FR-24 ISMS Setup Wizard]]). Deferred: 06.10 campaigns, 06.12 triggered reassessment, 06.14, 06.15, PDF exports.
```
```markdown
## Build status (Phase 1b, Oct 2026)
Done: FR-07.1, 07.2, 07.3, 07.4 (the ISMS Manager prepares, the Executive approves; the preparer can never approve their own version), 07.5 as XLSX, 07.7 bulk applicability and sources. Deferred: PDF export, 07.6 version diff, justification templates.
```
```markdown
## Build status (Phase 1b, Oct 2026)
Done: FR-08.1 built-in types, 08.2 core fields, criticality = max(C, I, A) (08.6, shown but not yet used to propose risks). Deferred: custom types and fields, 08.3 import, 08.4 dependency graph, 08.5 review campaign.
```

- [ ] **Step 4: Verify everything**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest -W error) && (cd frontend && npm run typecheck && npx vitest run --testTimeout=10000 && npm run build)`
Expected: every command succeeds.

- [ ] **Step 5: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && git add -A && git commit -m "docs: risk and SoA documentation, ADR-011 and smoke checks"
```

---

## Self-Review Notes

- **Spec coverage:** FR-06.2 register (Task 6), 06.3 wizard with live heatmap (Task 13), 06.4 libraries (Task 4), 06.5 controls and assets (Task 6), 06.6 suggested current from control status with owner confirmation and reason (Tasks 3, 7), 06.7 treatment plans with actions, budget, due date, target (Tasks 7, 8), 06.8 acceptance with authority levels, expiry and automatic re-request through review-due (Task 8), 06.9 table / board / heatmap with inherent-current-target toggle and owner filter (Task 12), 06.11 snapshots and compare (Task 9), 06.13 as XLSX (Task 9); FR-07.1–07.5 and 07.7 (Tasks 10, 11, 15); FR-08.1/08.2/08.6 (Tasks 5, 14); WF-07 steps (Tasks 6, 7, 13), WF-08 (Task 8, including "avoid closes the risk with a reason" and "controls added in treatment become applicable with justification Risk R-xxx" via live risk sources in Task 10), WF-09 (Tasks 10, 11, 15); RBAC matrix rows for risk register, risk acceptance, SoA and assets (Task 1). Deferred items are listed in the header.
- **Type consistency checked:** `rights_for`, `has_perm`, `check_active_user`; `band_for(definition, l, c)`; `suggest_current(definition, l, c, links)`; `risk_row(db, risk)`, `risk_detail(db, risk, user)`, `refresh_risk(db, risk, now)`; `load_risk`, `require_edit`, `require_open`; `soa_view(db, scope_id, settings, today)`; `safe_cell`, `add_sheet`, `xlsx_response`; frontend `useRiskMutation(request)`, `useFinalizeAssessment` with `void`, `RiskDetail`/`RiskRow`/`Level` field names match the backend schemas.
- **Placeholder scan:** none; every code step carries the full code.
