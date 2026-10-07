# Assayr Phase 1a — Evidence Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a control owner upload evidence to a control's evidence slot, have it checked automatically by a rules-based verification engine (with explainable per-rule results shown live), let a reviewer decide uncertain items, and keep each control's status, score and the scope's readiness up to date — the core loop of the product.

**Architecture:** Files are stored content-addressed on local disk (`BlobStore`). An upload creates an `Artefact` → `ArtefactVersion` → `ArtefactLink` (one per slot) and enqueues a `verify_link` job in a PostgreSQL-backed job table; a separate `assayr worker` process claims jobs (`SELECT … FOR UPDATE SKIP LOCKED`), extracts text (PDF, DOCX, XLSX, plain text), runs the deterministic rules, writes each rule result as it completes, decides ACCEPT / REVIEW / REJECT and recomputes the control's derived status. The browser polls the link until verification finishes. Scoring is a pure function of slot states + owner attestation, recomputed on every evidence event and periodically by the worker.

**Tech Stack:** existing Phase 0 stack (FastAPI, SQLAlchemy 2, Alembic, pg8000, React 19, TanStack Router/Query, Tailwind v4) plus pypdfium2 (PDF text), python-docx, openpyxl, python-multipart; optional ClamAV daemon in its own container.

**Spec:** Obsidian vault `E:\Work\GRC Tool\Assayr-Vault`: `03-Product/Requirements/FR-03 Evidence Management.md`, `FR-04 Evidence Verification Engine.md`, `FR-05 Compliance Scoring.md`, `03-Product/Verification Rule Library.md`, `03-Product/Compliance Scoring Model.md`, `05-Workflows/WF-04 Evidence Upload and Verification.md`, `WF-05 Evidence Review and Approval.md`, `WF-06 Evidence Expiry and Renewal.md`, `05-Workflows/State Machines.md`, `06-Architecture/Evidence Verification Engine Design.md`, `06-Architecture/Data Model.md`, `03-Product/RBAC Matrix.md`, `07-Design/Screens/Screen - Control Detail.md`, `Screen - Evidence Upload.md`, `Screen - Evidence Review.md`, `Screen - Dashboard.md`.

**Phase 1 split (this plan is 1a):**
- **1a (this plan):** evidence upload/storage, rules-based verification, review queue, scoring + status, attestation, readiness, worker.
- **1b:** risk register + methodology + wizard, Statement of Applicability (adds `excluded`), policy management, tasks, mandatory-document clause slots.
- **1c:** local AI (`V-RELEVANCE` via embeddings + LLM), OCR (`V-SCREENSHOT`), digital signatures (`V-SIGNATURE`), live progress over SSE, notifications/email, reports and evidence packs.

**Deliberate deviations from the spec (ledger them; the vault gets ADR-010 in Task 14):**
- Jobs run on a PostgreSQL table + `assayr worker` instead of Celery + Valkey (Tech Stack note). One datastore to back up (ADR-003), no extra container; the queue interface is small enough to swap later.
- Live verification progress is delivered by polling `GET /artefact-links/{id}` every 0.8 s instead of SSE (FR-04.5). Each rule result is committed as soon as it runs, so the UI still shows results appearing one by one.
- Rules that need components not built yet (`V-RELEVANCE`, `V-SCREENSHOT`, `V-COMPLETENESS`, `V-SIGNATURE`) return `skipped` with a plain-language reason. In rules-only mode an ACCEPT is still possible when every rule that ran passes (FR-04.7 "rules-only mode is first-class").
- `V-AV` runs only when `ASSAYR_CLAMAV_HOST` is set; otherwise it is `skipped` ("Malware scanning is not configured").
- ZIP uploads, email-in, bulk upload and structured "record" evidence (FR-03.1/03.3/03.14) are out of scope for 1a.
- The "expiring" warning window is 30 days **or a quarter of the slot's freshness window, whichever is shorter** (Compliance Scoring Model §2 says a flat 30 days, which would mark monthly evidence "expiring" the day after it is uploaded). Task 14 updates the vault note.

## Global Constraints

- Everything from the Phase 0 plan still applies: Python ≥3.12, permissive in-process dependencies only (ADR-009), no outbound network calls at runtime, UTC storage, deny-by-default RBAC, hash-chained audit trail, sentence-case UI copy, Strata tokens, `source scripts/dev-env.sh` before every command, commit trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- New dependency licences: pypdfium2 (Apache-2.0 / BSD-3-Clause), python-docx (MIT), openpyxl (MIT), python-multipart (Apache-2.0). ClamAV (GPL) runs only as a separate container.
- Files are immutable once uploaded; a new upload is a new version (FR-03 business rules). Storage keys are SHA-256 hex only.
- Downloads are always `Content-Disposition: attachment`, `application/octet-stream`, `X-Content-Type-Options: nosniff` — the server never renders uploaded content inline.
- Rule result values: `pass`, `warn`, `fail`, `skipped`. Verdicts: `accept`, `review`, `reject`. Link states: `verifying`, `accepted`, `in_review`, `rejected`, `superseded`. Slot states: `verified`, `expiring`, `expired_grace`, `expired`, `pending`, `rejected`, `missing`. Control statuses as in Phase 0.
- Confidence = Σ(weight × score) / Σ(weight) over **soft** rules that ran (`pass`=1, `warn`=0.5, `fail`=0); REJECT if any hard rule fails or confidence < 0.60; REVIEW if confidence < 0.85 or no soft rule ran; else ACCEPT (Verification Rule Library). Thresholds are settings.
- Slot score: verified 1.0, expiring 0.8, pending 0.5, expired_grace 0.4, rejected/missing/expired 0 (Compliance Scoring Model §2). Expiry warning window 30 days capped at a quarter of the freshness window, grace 14 days (settings).
- A reviewer can never decide on evidence they uploaded (RBAC Matrix separation of duties).
- Dates shown to users as `14 Feb 2026`; numeric dates in documents are read day-first (`14/02/2026`), which matches the target users' convention; the uploader can always supply the evidence date explicitly.

## Review Focus

- A file whose name or type lies — `invoice.pdf` that is really an `.exe`, an HTML page renamed `.txt`, `..\..\evil.pdf` paths, control characters in names — must be identified by its content, rejected by `V-FMT`, stored only under its hash, and never served inline → Task 1 (`test_safe_filename_*`), Task 2 (`test_sniff` cases), Task 8 (`test_upload_of_disguised_executable_is_rejected`, `test_upload_filename_is_sanitised`).
- Uploads larger than the limit must be refused with a clear message and leave no partial file on disk → Task 1 (`test_oversized_upload_leaves_nothing_behind`), Task 8 (`test_upload_over_the_size_limit_is_refused`).
- The person who uploaded a file must not be able to approve it in review, even if they hold the reviewer role → Task 9 (`test_uploader_cannot_review_their_own_evidence`).
- If the worker dies mid-verification, the evidence must not stay "Verifying" forever: a stale running job is reclaimed and the link is verified on the next attempt → Task 6 (`test_stale_running_job_is_reclaimed`), Task 7 (`test_reverification_after_a_crash_completes`).
- Impossible or ambiguous dates in documents (`31/02/2026`, future dates, a "next review" date) must not be taken as the evidence date → Task 3 (`test_invalid_dates_are_ignored`, `test_next_review_and_future_dates_are_not_the_evidence_date`).

---

## File Structure

```
backend/src/assayr/
├── config.py                    # + storage, upload, AV, scoring, worker settings
├── storage.py                   # BlobStore (content-addressed), safe_filename, TooLargeError
├── jobs.py                      # Job model, enqueue, claim, run_one/run_pending, HANDLERS registry
├── job_handlers.py              # imports modules that register handlers
├── models.py                    # + evidence, scoring, job models
├── evidence/
│   ├── models.py                # Artefact, ArtefactVersion, ArtefactLink, VerificationRun, RuleResult
│   ├── extract.py               # sniff(), extract() for PDF/DOCX/XLSX/text/images
│   ├── schemas.py               # LinkOut, RuleResultOut, ReviewItemOut, DecisionIn, link_out()
│   └── router.py                # upload, link status, download, review queue, decision
├── verification/
│   ├── dates.py                 # find_dates(), best_evidence_date()
│   ├── rules.py                 # RuleContext, Outcome, Rule, RULES, run_order(), decide()
│   ├── av.py                    # ClamAV INSTREAM client
│   └── engine.py                # verify_link(), supersede_older(), "verify_link" job handler
├── scoring/
│   ├── models.py                # Attestation, StatusTransition, ScoreSnapshot
│   ├── service.py               # slot views, evaluate(), recompute_control/scope, readiness, snapshots
│   ├── jobs.py                  # "recompute_scope" handler, enqueue_recompute_all()
│   └── router.py                # /readiness, /controls/{code}/attest
├── catalogue/
│   ├── access.py                # EditRights, edit_rights()
│   ├── schemas.py               # + slot state/artefact, score, attestation on control detail
│   └── router.py                # uses edit_rights; detail includes slot views
├── identity/rbac.py             # + Perm.EVIDENCE_REVIEW
├── cli.py                       # + `assayr worker`
└── migrations/versions/0004_evidence_scoring_jobs.py
backend/tests/
├── fixtures.py                  # make_pdf, make_docx, make_xlsx, PNG_BYTES
├── evidence_helpers.py          # add_link(), run_jobs(), policy_text()
└── test_storage.py, test_evidence_models.py, test_extract.py, test_dates.py, test_rules.py,
    test_av.py, test_scoring.py, test_jobs.py, test_engine.py, test_evidence_api.py,
    test_review_api.py, test_scoring_api.py (+ edits to conftest, test_rbac, test_cli)
frontend/src/
├── api/client.ts                # FormData bodies keep the browser's multipart header
├── api/types.ts                 # + slot state, links, rules, review items, readiness
├── api/evidence.ts              # uploadEvidence, useLink, useUploadEvidence, useReviewQueue, useDecision, useAttest, useReadiness
├── lib/format.ts                # formatDate()
├── components/StatusPill.tsx    # + optional label
├── components/SlotStatePill.tsx
├── components/VerificationPanel.tsx
├── components/ReadinessRing.tsx
├── components/icons.tsx         # + pass/warn/fail/skip
├── components/AppShell.tsx      # Evidence enabled
├── pages/ControlDetail.tsx      # upload, live verification, attestation
├── pages/ReviewQueue.tsx
├── pages/Dashboard.tsx          # readiness ring, status counts, theme readiness
├── pages/Controls.tsx           # score column
└── router.tsx                   # + /evidence
deploy/compose.yaml              # + worker, blobs volume, optional clamav profile
frontend/Caddyfile               # + request body limit
Assayr-Vault/06-Architecture/ADRs/ADR-010 Database job queue.md (+ Tech Stack line)
```

---

### Task 1: Settings, blob storage and evidence/scoring/job tables

**Files:**
- Create: `backend/src/assayr/storage.py`, `backend/src/assayr/evidence/__init__.py` (empty), `backend/src/assayr/evidence/models.py`, `backend/src/assayr/scoring/__init__.py` (empty), `backend/src/assayr/scoring/models.py`, `backend/src/assayr/jobs.py` (model only in this task), `backend/src/assayr/migrations/versions/0004_evidence_scoring_jobs.py`
- Modify: `backend/src/assayr/config.py`, `backend/src/assayr/main.py`, `backend/src/assayr/models.py`, `backend/src/assayr/catalogue/models.py` (add `Control.score`), `backend/tests/conftest.py`, `.gitignore`
- Test: `backend/tests/test_storage.py`, `backend/tests/test_evidence_models.py` (migration drift is covered by the existing `test_migrations.py`)

**Interfaces:**
- Produces: `Settings` fields `storage_dir: str = "./data/blobs"`, `max_upload_mb: int = 100`, `clamav_host: str | None = None` (blank → None), `clamav_port: int = 3310`, `expiry_warning_days: int = 30`, `evidence_grace_days: int = 14`, `accept_threshold: float = 0.85`, `reject_threshold: float = 0.60`, `worker_poll_seconds: float = 2.0`, `recompute_interval_minutes: int = 60`; `BlobStore(root)` with `.put(stream, max_bytes) -> StoredBlob(sha256, size)`, `.path_for(sha256) -> Path`; `TooLargeError`; `safe_filename(name) -> str`; `app.state.store`; models `Artefact`, `ArtefactVersion` (`doc_metadata` JSON), `ArtefactLink`, `VerificationRun`, `RuleResult`, `Attestation`, `StatusTransition`, `ScoreSnapshot`, `Job`; `Control.score: float | None`; conftest `settings` now stores blobs under `tmp_path`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_storage.py`:
```python
import io

import pytest

from assayr.storage import BlobStore, TooLargeError, safe_filename


def files_under(path):
    return [p for p in path.rglob("*") if p.is_file()]


def test_put_stores_by_content_hash(tmp_path):
    store = BlobStore(tmp_path)
    blob = store.put(io.BytesIO(b"hello evidence"), max_bytes=1000)
    assert blob.size == 14
    assert store.path_for(blob.sha256).read_bytes() == b"hello evidence"


def test_identical_content_is_stored_once(tmp_path):
    store = BlobStore(tmp_path)
    first = store.put(io.BytesIO(b"same"), max_bytes=100)
    second = store.put(io.BytesIO(b"same"), max_bytes=100)
    assert first == second
    assert len(files_under(tmp_path)) == 1


def test_oversized_upload_leaves_nothing_behind(tmp_path):
    store = BlobStore(tmp_path)
    with pytest.raises(TooLargeError):
        store.put(io.BytesIO(b"x" * 101), max_bytes=100)
    assert files_under(tmp_path) == []


@pytest.mark.parametrize("bad", ["../../etc/passwd", "ABC", "g" * 64, ""])
def test_only_hex_hashes_map_to_paths(tmp_path, bad):
    with pytest.raises(ValueError):
        BlobStore(tmp_path).path_for(bad)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("..\\..\\evil.pdf", "evil.pdf"),
        ("../../x.txt", "x.txt"),
        ("a\x00b\n.pdf", "ab.pdf"),
        ('re<po>rt:"q3"?.xlsx', "reportq3.xlsx"),
        ("", "upload"),
        ("....", "upload"),
    ],
)
def test_safe_filename_strips_paths_and_unsafe_characters(raw, expected):
    assert safe_filename(raw) == expected


def test_safe_filename_shortens_long_names_but_keeps_the_extension():
    name = safe_filename("a" * 400 + ".pdf")
    assert len(name) <= 200 and name.endswith(".pdf")
```

`backend/tests/test_evidence_models.py`:
```python
from sqlalchemy import func, select

from assayr.catalogue.models import EvidenceSlot
from assayr.evidence.models import Artefact, ArtefactLink, ArtefactVersion


def test_deleting_an_artefact_removes_versions_and_links(db, seeded):
    slot = db.scalar(select(EvidenceSlot).limit(1))
    artefact = Artefact(scope_id=seeded.id, title="Policy")
    version = ArtefactVersion(version_no=1, sha256="a" * 64, size=10, filename="p.pdf", mime="application/pdf")
    artefact.versions.append(version)
    db.add(artefact)
    db.flush()
    db.add(ArtefactLink(version_id=version.id, slot_id=slot.id))
    db.commit()
    db.delete(artefact)
    db.commit()
    assert db.scalar(select(func.count()).select_from(ArtefactLink)) == 0
    assert db.scalar(select(func.count()).select_from(ArtefactVersion)) == 0


def test_new_link_starts_verifying(db, seeded):
    slot = db.scalar(select(EvidenceSlot).limit(1))
    artefact = Artefact(scope_id=seeded.id, title="Policy")
    artefact.versions.append(ArtefactVersion(version_no=1, sha256="b" * 64, size=1, filename="p.pdf", mime=None))
    db.add(artefact)
    db.flush()
    link = ArtefactLink(version_id=artefact.versions[0].id, slot_id=slot.id)
    db.add(link)
    db.commit()
    assert link.state == "verifying"
    assert link.created_at.utcoffset().total_seconds() == 0
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_storage.py tests/test_evidence_models.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'assayr.storage'`.

- [ ] **Step 3: Implement settings and storage**

Add to `Settings` in `backend/src/assayr/config.py` (import `field_validator` from `pydantic`):
```python
    storage_dir: str = "./data/blobs"
    max_upload_mb: int = 100
    clamav_host: str | None = None
    clamav_port: int = 3310
    expiry_warning_days: int = 30
    evidence_grace_days: int = 14
    accept_threshold: float = 0.85
    reject_threshold: float = 0.60
    worker_poll_seconds: float = 2.0
    recompute_interval_minutes: int = 60

    @field_validator("clamav_host", mode="before")
    @classmethod
    def _blank_host_is_none(cls, value):
        return value or None
```

`backend/src/assayr/storage.py`:
```python
"""Content-addressed evidence file storage on local disk: <root>/<aa>/<bb>/<sha256>."""

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

CHUNK_SIZE = 1024 * 1024
_HEX = frozenset("0123456789abcdef")
_UNSAFE_NAME_CHARS = re.compile(r'[\x00-\x1f\x7f<>:"|?*]')


class TooLargeError(Exception):
    pass


@dataclass(frozen=True)
class StoredBlob:
    sha256: str
    size: int


class BlobStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def path_for(self, sha256: str) -> Path:
        if len(sha256) != 64 or not set(sha256) <= _HEX:
            raise ValueError("Invalid content hash.")
        return self.root / sha256[:2] / sha256[2:4] / sha256

    def put(self, stream: BinaryIO, max_bytes: int) -> StoredBlob:
        """Stream to a temp file while hashing; move into place only if within the size limit."""
        self.root.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        fd, tmp_name = tempfile.mkstemp(dir=self.root, prefix=".upload-")
        try:
            with os.fdopen(fd, "wb") as tmp:
                while chunk := stream.read(CHUNK_SIZE):
                    size += len(chunk)
                    if size > max_bytes:
                        raise TooLargeError(f"File exceeds {max_bytes} bytes.")
                    digest.update(chunk)
                    tmp.write(chunk)
            sha256 = digest.hexdigest()
            target = self.path_for(sha256)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                os.remove(tmp_name)
            else:
                os.replace(tmp_name, target)
            return StoredBlob(sha256=sha256, size=size)
        except BaseException:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
            raise


def safe_filename(name: str) -> str:
    """Keep only the final path component, without control or reserved characters."""
    base = re.split(r"[\\/]", name)[-1]
    base = _UNSAFE_NAME_CHARS.sub("", base).strip().strip(".")
    if len(base) > 200:
        stem, dot, ext = base.rpartition(".")
        base = f"{stem[:190]}.{ext[-9:]}" if dot and stem else base[:200]
    return base or "upload"
```

In `backend/src/assayr/main.py`: `from assayr.storage import BlobStore` and after `app.state.clock = utcnow` add `app.state.store = BlobStore(settings.storage_dir)`.

Append to `.gitignore`: `backend/data/`.

- [ ] **Step 4: Implement the models**

`backend/src/assayr/evidence/models.py`:
```python
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import JSON, BigInteger, Date, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from assayr.catalogue.models import EvidenceSlot
from assayr.db import Base, IdMixin, TimestampMixin, UTCDateTime, utcnow


class Artefact(IdMixin, TimestampMixin, Base):
    """A piece of evidence (a document or file) with one or more immutable versions."""

    __tablename__ = "artefact"

    scope_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(300))
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))

    versions: Mapped[list[ArtefactVersion]] = relationship(
        back_populates="artefact", cascade="all, delete-orphan", order_by="ArtefactVersion.version_no"
    )


class ArtefactVersion(IdMixin, Base):
    __tablename__ = "artefact_version"
    __table_args__ = (
        UniqueConstraint("artefact_id", "version_no", name="uq_artefact_version_artefact_no"),
        Index("ix_artefact_version_sha256", "sha256"),
    )

    artefact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artefact.id", ondelete="CASCADE"))
    version_no: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(BigInteger)
    filename: Mapped[str] = mapped_column(String(255))
    mime: Mapped[str | None] = mapped_column(String(100))
    evidence_date: Mapped[date | None] = mapped_column(Date)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    extract_error: Mapped[str | None] = mapped_column(String(300))
    page_count: Mapped[int | None] = mapped_column(Integer)
    doc_metadata: Mapped[dict | None] = mapped_column(JSON)
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    artefact: Mapped[Artefact] = relationship(back_populates="versions")


class ArtefactLink(IdMixin, Base):
    """One version of an artefact offered as evidence for one slot, with its verification outcome."""

    __tablename__ = "artefact_link"
    __table_args__ = (UniqueConstraint("version_id", "slot_id", name="uq_artefact_link_version_slot"),)

    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artefact_version.id", ondelete="CASCADE"))
    slot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evidence_slot.id", ondelete="CASCADE"), index=True)
    state: Mapped[str] = mapped_column(String(20), default="verifying")
    confidence: Mapped[float | None] = mapped_column(Float)
    evidence_date: Mapped[date | None] = mapped_column(Date)
    expires_on: Mapped[date | None] = mapped_column(Date)
    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    decision_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    version: Mapped[ArtefactVersion] = relationship(lazy="joined")
    slot: Mapped[EvidenceSlot] = relationship(lazy="joined")


class VerificationRun(IdMixin, Base):
    __tablename__ = "verification_run"

    link_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artefact_link.id", ondelete="CASCADE"), index=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    rules_version: Mapped[str] = mapped_column(String(20))
    confidence: Mapped[float | None] = mapped_column(Float)
    verdict: Mapped[str | None] = mapped_column(String(10))

    results: Mapped[list[RuleResult]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="RuleResult.seq"
    )


class RuleResult(IdMixin, Base):
    __tablename__ = "rule_result"

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("verification_run.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(10))
    weight: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(Text)
    fix_hint: Mapped[str | None] = mapped_column(Text)
    excerpt: Mapped[str | None] = mapped_column(Text)
```

`backend/src/assayr/scoring/models.py`:
```python
import uuid
from datetime import datetime

from sqlalchemy import JSON, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from assayr.db import Base, IdMixin, UTCDateTime


class Attestation(IdMixin, Base):
    """The owner's periodic confirmation that a control operates as described."""

    __tablename__ = "attestation"

    control_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("control.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    statement: Mapped[str] = mapped_column(Text)
    attested_at: Mapped[datetime] = mapped_column(UTCDateTime)
    valid_until: Mapped[datetime] = mapped_column(UTCDateTime)


class StatusTransition(IdMixin, Base):
    __tablename__ = "status_transition"

    control_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("control.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30))
    trigger: Mapped[str] = mapped_column(String(300))
    at: Mapped[datetime] = mapped_column(UTCDateTime)


class ScoreSnapshot(IdMixin, Base):
    __tablename__ = "score_snapshot"
    __table_args__ = (Index("ix_score_snapshot_scope_taken", "scope_id", "taken_at"),)

    scope_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"))
    taken_at: Mapped[datetime] = mapped_column(UTCDateTime)
    readiness: Mapped[float] = mapped_column(Float)
    status_counts: Mapped[dict] = mapped_column(JSON)
```

`backend/src/assayr/jobs.py` (model only for now — Task 6 adds the functions below it):
```python
"""A small job queue in the main database, processed by `assayr worker`."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from assayr.db import Base, UTCDateTime, utcnow


class Job(Base):
    __tablename__ = "job"
    __table_args__ = (Index("ix_job_status_run_after", "status", "run_after"),)

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(10), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    run_after: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    locked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
```

In `backend/src/assayr/catalogue/models.py`, add to `Control` after `sort_order`:
```python
    score: Mapped[float | None] = mapped_column(Float)
```
(`Float` is already imported there.)

Replace `backend/src/assayr/models.py`:
```python
"""Import every model module so Base.metadata is complete (used by create_all and Alembic)."""

from assayr.audit.models import AuditLog  # noqa: F401
from assayr.catalogue.models import (  # noqa: F401
    Control,
    ControlRequirement,
    EvidenceSlot,
    Framework,
    Requirement,
)
from assayr.evidence.models import (  # noqa: F401
    Artefact,
    ArtefactLink,
    ArtefactVersion,
    RuleResult,
    VerificationRun,
)
from assayr.identity.models import Organization, RoleAssignment, Scope, User, UserSession  # noqa: F401
from assayr.jobs import Job  # noqa: F401
from assayr.scoring.models import Attestation, ScoreSnapshot, StatusTransition  # noqa: F401
```

- [ ] **Step 5: Write migration 0004**

`backend/src/assayr/migrations/versions/0004_evidence_scoring_jobs.py`:
```python
"""evidence, verification, scoring and job tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-07
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _user_fk(column: str, table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["user_account.id"], name=f"fk_{table}_{column}_user_account", ondelete="SET NULL"
    )


def upgrade() -> None:
    op.add_column("control", sa.Column("score", sa.Float(), nullable=True))
    op.create_table(
        "artefact",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("uploaded_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["scope_id"], ["scope.id"], name="fk_artefact_scope_id_scope", ondelete="CASCADE"),
        _user_fk("uploaded_by_id", "artefact"),
        sa.PrimaryKeyConstraint("id", name="pk_artefact"),
    )
    op.create_table(
        "artefact_version",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("artefact_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime", sa.String(length=100), nullable=True),
        sa.Column("evidence_date", sa.Date(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("extract_error", sa.String(length=300), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("doc_metadata", sa.JSON(), nullable=True),
        sa.Column("uploaded_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["artefact_id"], ["artefact.id"], name="fk_artefact_version_artefact_id_artefact", ondelete="CASCADE"
        ),
        _user_fk("uploaded_by_id", "artefact_version"),
        sa.PrimaryKeyConstraint("id", name="pk_artefact_version"),
        sa.UniqueConstraint("artefact_id", "version_no", name="uq_artefact_version_artefact_no"),
    )
    op.create_index("ix_artefact_version_sha256", "artefact_version", ["sha256"])
    op.create_table(
        "artefact_link",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("slot_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence_date", sa.Date(), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("decided_by_id", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["artefact_version.id"],
            name="fk_artefact_link_version_id_artefact_version",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["slot_id"], ["evidence_slot.id"], name="fk_artefact_link_slot_id_evidence_slot", ondelete="CASCADE"
        ),
        _user_fk("decided_by_id", "artefact_link"),
        sa.PrimaryKeyConstraint("id", name="pk_artefact_link"),
        sa.UniqueConstraint("version_id", "slot_id", name="uq_artefact_link_version_slot"),
    )
    op.create_index("ix_artefact_link_slot_id", "artefact_link", ["slot_id"])
    op.create_table(
        "verification_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("link_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rules_version", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("verdict", sa.String(length=10), nullable=True),
        sa.ForeignKeyConstraint(
            ["link_id"], ["artefact_link.id"], name="fk_verification_run_link_id_artefact_link", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_verification_run"),
    )
    op.create_index("ix_verification_run_link_id", "verification_run", ["link_id"])
    op.create_table(
        "rule_result",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("fix_hint", sa.Text(), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id"], ["verification_run.id"], name="fk_rule_result_run_id_verification_run", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_rule_result"),
    )
    op.create_index("ix_rule_result_run_id", "rule_result", ["run_id"])
    op.create_table(
        "attestation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("control_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("attested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["control_id"], ["control.id"], name="fk_attestation_control_id_control", ondelete="CASCADE"
        ),
        _user_fk("user_id", "attestation"),
        sa.PrimaryKeyConstraint("id", name="pk_attestation"),
    )
    op.create_index("ix_attestation_control_id", "attestation", ["control_id"])
    op.create_table(
        "status_transition",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("control_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.String(length=30), nullable=False),
        sa.Column("to_status", sa.String(length=30), nullable=False),
        sa.Column("trigger", sa.String(length=300), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["control_id"], ["control.id"], name="fk_status_transition_control_id_control", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_status_transition"),
    )
    op.create_index("ix_status_transition_control_id", "status_transition", ["control_id"])
    op.create_table(
        "score_snapshot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("readiness", sa.Float(), nullable=False),
        sa.Column("status_counts", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["scope_id"], ["scope.id"], name="fk_score_snapshot_scope_id_scope", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_score_snapshot"),
    )
    op.create_index("ix_score_snapshot_scope_taken", "score_snapshot", ["scope_id", "taken_at"])
    op.create_table(
        "job",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("run_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_job"),
    )
    op.create_index("ix_job_status_run_after", "job", ["status", "run_after"])


def downgrade() -> None:
    op.drop_index("ix_job_status_run_after", table_name="job")
    op.drop_table("job")
    op.drop_index("ix_score_snapshot_scope_taken", table_name="score_snapshot")
    op.drop_table("score_snapshot")
    op.drop_index("ix_status_transition_control_id", table_name="status_transition")
    op.drop_table("status_transition")
    op.drop_index("ix_attestation_control_id", table_name="attestation")
    op.drop_table("attestation")
    op.drop_index("ix_rule_result_run_id", table_name="rule_result")
    op.drop_table("rule_result")
    op.drop_index("ix_verification_run_link_id", table_name="verification_run")
    op.drop_table("verification_run")
    op.drop_index("ix_artefact_link_slot_id", table_name="artefact_link")
    op.drop_table("artefact_link")
    op.drop_index("ix_artefact_version_sha256", table_name="artefact_version")
    op.drop_table("artefact_version")
    op.drop_table("artefact")
    with op.batch_alter_table("control") as batch:
        batch.drop_column("score")
```

In `backend/tests/conftest.py`, change the `settings` fixture to keep blobs per test:
```python
@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        database_url=TEST_DB_URL,
        secure_cookies=False,
        org_name="Acme Financial Services",
        storage_dir=str(tmp_path / "blobs"),
    )
```

- [ ] **Step 6: Run the whole backend suite**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest -W error`
Expected: all pass, including `test_migrations_match_models_and_downgrade_cleanly` (proves 0004 matches the models and downgrades cleanly).

- [ ] **Step 7: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(evidence): blob storage and evidence, scoring and job tables" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: File type detection and text extraction

**Files:**
- Modify: `backend/pyproject.toml` (dependencies)
- Create: `backend/src/assayr/evidence/extract.py`, `backend/tests/fixtures.py`
- Test: `backend/tests/test_extract.py`

**Interfaces:**
- Produces: constants `PDF`, `DOCX`, `XLSX`, `TEXT_TYPES`, `IMAGE_TYPES`, `ALLOWED_TYPES`, `KIND_LABEL: dict[str, str]`; `sniff(head: bytes, filename: str) -> str | None`; `Extracted(text: str = "", pages: int | None = None, metadata: dict[str, str] = {}, error: str | None = None)`; `extract(path: Path, mime: str | None) -> Extracted`; test helpers `make_pdf(lines: list[str]) -> bytes`, `make_docx(paragraphs, table=None, author=None) -> bytes`, `make_xlsx(rows) -> bytes`, `PNG_BYTES`.

- [ ] **Step 1: Add dependencies**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv add "pypdfium2>=4.30" "python-docx>=1.1" "openpyxl>=3.1" "python-multipart>=0.0.9"
```
Expected: `uv.lock` updated, packages installed.

- [ ] **Step 2: Write test fixtures and failing tests**

`backend/tests/fixtures.py`:
```python
"""Small in-memory documents for extraction and verification tests."""

import base64
import io

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def make_pdf(lines: list[str]) -> bytes:
    """A minimal valid one-page PDF with Helvetica text, one line per entry."""
    ops = ["BT", "/F1 11 Tf", "50 780 Td", "14 TL"]
    for line in lines:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        ops.append(f"({safe}) Tj T*")
    ops.append("ET")
    stream = "\n".join(ops).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode()
    return bytes(out)


def make_docx(paragraphs: list[str], table: list[list[str]] | None = None, author: str | None = None) -> bytes:
    import docx

    document = docx.Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    if table:
        grid = document.add_table(rows=len(table), cols=len(table[0]))
        for r, row in enumerate(table):
            for c, value in enumerate(row):
                grid.cell(r, c).text = value
    if author:
        document.core_properties.author = author
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def make_xlsx(rows: list[list[object]]) -> bytes:
    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Review"
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
```

`backend/tests/test_extract.py`:
```python
import pytest

from assayr.evidence.extract import DOCX, PDF, XLSX, extract, sniff
from tests.fixtures import PNG_BYTES, make_docx, make_pdf, make_xlsx


def write(tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data)
    return path


@pytest.mark.parametrize(
    "head,name,expected",
    [
        (b"%PDF-1.4 rest", "policy.pdf", PDF),
        (b"%PDF-1.4 rest", "renamed.txt", PDF),
        (PNG_BYTES[:16], "shot.png", "image/png"),
        (b"\xff\xd8\xff\xe0\x00\x10JFIF", "photo.jpg", "image/jpeg"),
        (b"PK\x03\x04rest", "review.xlsx", XLSX),
        (b"PK\x03\x04rest", "policy.docx", DOCX),
        (b"PK\x03\x04rest", "archive.zip", None),
        (b"MZ\x90\x00\x03\x00", "invoice.pdf", None),
        (b"<html><script>alert(1)</script>", "page.html", None),
        (b"<html><script>alert(1)</script>", "notes.txt", None),
        (b"Access review\ncompleted", "notes.txt", "text/plain"),
        (b"user,approved\nsana,yes", "export.csv", "text/csv"),
        (b'{"mfa": true}', "config.json", "application/json"),
    ],
)
def test_sniff(head, name, expected):
    assert sniff(head, name) == expected


def test_pdf_text_and_page_count(tmp_path):
    path = write(tmp_path, "p.pdf", make_pdf(["Acme Financial Services", "Approved by: Tariq Qureshi"]))
    result = extract(path, PDF)
    assert result.error is None and result.pages == 1
    assert "Approved by: Tariq Qureshi" in result.text


def test_docx_text_tables_and_author(tmp_path):
    data = make_docx(["Backup policy"], table=[["Version", "Approved by"], ["3.0", "Tariq Qureshi"]], author="Sana")
    result = extract(write(tmp_path, "b.docx", data), DOCX)
    assert "Backup policy" in result.text and "Tariq Qureshi" in result.text
    assert result.metadata["author"] == "Sana"


def test_xlsx_cell_values(tmp_path):
    result = extract(write(tmp_path, "r.xlsx", make_xlsx([["User", "Reviewed"], ["sana", "yes"]])), XLSX)
    assert "sana | yes" in result.text


def test_corrupt_pdf_is_reported_unreadable(tmp_path):
    result = extract(write(tmp_path, "bad.pdf", b"%PDF-1.4\nnot really a pdf"), PDF)
    assert result.error == "The file could not be read."


def test_text_file_is_read(tmp_path):
    assert extract(write(tmp_path, "n.txt", "Résumé ok".encode()), "text/plain").text == "Résumé ok"


def test_images_have_no_text_yet(tmp_path):
    result = extract(write(tmp_path, "s.png", PNG_BYTES), "image/png")
    assert result.text == "" and result.error is None


def test_unsupported_type_is_an_error(tmp_path):
    assert extract(write(tmp_path, "x.bin", b"\x00\x01"), None).error == "This file type isn't accepted as evidence."
```

- [ ] **Step 3: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_extract.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'assayr.evidence.extract'`.

- [ ] **Step 4: Implement**

`backend/src/assayr/evidence/extract.py`:
```python
"""Identify uploaded files by content and pull out their text for verification."""

from dataclasses import dataclass, field
from pathlib import Path

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TEXT_TYPES = {"text/plain", "text/csv", "text/markdown", "application/json"}
IMAGE_TYPES = {"image/png", "image/jpeg"}
ALLOWED_TYPES = {PDF, DOCX, XLSX, *TEXT_TYPES, *IMAGE_TYPES}
KIND_LABEL = {
    PDF: "PDF",
    DOCX: "Word document",
    XLSX: "Excel workbook",
    "text/plain": "Text file",
    "text/csv": "CSV file",
    "text/markdown": "Markdown file",
    "application/json": "JSON file",
    "image/png": "PNG image",
    "image/jpeg": "JPEG image",
}
MAX_TEXT_CHARS = 2_000_000
_TEXT_EXTENSIONS = {".txt": "text/plain", ".csv": "text/csv", ".md": "text/markdown", ".json": "application/json"}
_MARKUP_PREFIXES = (b"<html", b"<!doctype", b"<script", b"<svg", b"<?xml")


@dataclass
class Extracted:
    text: str = ""
    pages: int | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    error: str | None = None


def sniff(head: bytes, filename: str) -> str | None:
    """Decide the type from the file's first bytes; the extension only picks between text and zip flavours."""
    name = filename.lower()
    if head.startswith(b"%PDF-"):
        return PDF
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"PK\x03\x04"):
        if name.endswith(".docx"):
            return DOCX
        if name.endswith(".xlsx"):
            return XLSX
        return None
    if _looks_like_text(head):
        if head.lstrip().lower().startswith(_MARKUP_PREFIXES):
            return None
        for extension, mime in _TEXT_EXTENSIONS.items():
            if name.endswith(extension):
                return mime
    return None


def _looks_like_text(head: bytes) -> bool:
    if not head or b"\x00" in head:
        return False
    return head.decode("utf-8", errors="replace").count("\ufffd") <= 2


def extract(path: Path, mime: str | None) -> Extracted:
    try:
        if mime == PDF:
            return _pdf(path)
        if mime == DOCX:
            return _docx(path)
        if mime == XLSX:
            return _xlsx(path)
        if mime in TEXT_TYPES:
            return Extracted(text=path.read_text(encoding="utf-8", errors="replace")[:MAX_TEXT_CHARS])
        if mime in IMAGE_TYPES:
            return Extracted()
        return Extracted(error="This file type isn't accepted as evidence.")
    except Exception as exc:  # noqa: BLE001 - any parser failure means the file is unreadable
        if "password" in str(exc).lower():
            return Extracted(error="The PDF is password-protected.")
        return Extracted(error="The file could not be read.")


def _pdf(path: Path) -> Extracted:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    try:
        if len(pdf) == 0:
            return Extracted(error="The file could not be read.")
        parts: list[str] = []
        total = 0
        for index in range(len(pdf)):
            page = pdf[index]
            textpage = page.get_textpage()
            text = textpage.get_text_range()
            textpage.close()
            page.close()
            parts.append(text)
            total += len(text)
            if total > MAX_TEXT_CHARS:
                break
        metadata = {k.lower(): str(v) for k, v in pdf.get_metadata_dict(skip_empty=True).items()}
        return Extracted(text="\n".join(parts)[:MAX_TEXT_CHARS], pages=len(pdf), metadata=metadata)
    finally:
        pdf.close()


def _docx(path: Path) -> Extracted:
    import docx

    document = docx.Document(str(path))
    parts = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text for cell in row.cells))
    for section in document.sections:
        parts.extend(p.text for p in section.header.paragraphs)
        parts.extend(p.text for p in section.footer.paragraphs)
    props = document.core_properties
    metadata = {
        key: str(value)
        for key, value in {
            "author": props.author,
            "title": props.title,
            "created": props.created,
            "modified": props.modified,
        }.items()
        if value
    }
    return Extracted(text="\n".join(p for p in parts if p)[:MAX_TEXT_CHARS], metadata=metadata)


def _xlsx(path: Path) -> Extracted:
    import openpyxl

    workbook = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    try:
        parts: list[str] = []
        cells = 0
        for sheet in workbook.worksheets:
            parts.append(f"[{sheet.title}]")
            for row in sheet.iter_rows(values_only=True):
                values = [str(v) for v in row if v is not None]
                if values:
                    parts.append(" | ".join(values))
                    cells += len(values)
                if cells > 200_000:
                    break
        return Extracted(text="\n".join(parts)[:MAX_TEXT_CHARS])
    finally:
        workbook.close()
```

- [ ] **Step 5: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_extract.py -W error`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(evidence): content-based file type detection and text extraction" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Date finding and the verification rule library

**Files:**
- Create: `backend/src/assayr/verification/__init__.py` (empty), `backend/src/assayr/verification/dates.py`, `backend/src/assayr/verification/rules.py`, `backend/src/assayr/verification/av.py` (only the `AvResult` dataclass in this task — Task 4 adds the scanner)
- Test: `backend/tests/test_dates.py`, `backend/tests/test_rules.py`

**Interfaces:**
- Consumes: `Extracted`, `ALLOWED_TYPES`, `KIND_LABEL` (Task 2).
- Produces: `FoundDate(value: date, label: str | None, position: int, excerpt: str)`; `find_dates(text) -> list[FoundDate]`; `best_evidence_date(found, today) -> FoundDate | None`; `format_day(d: date) -> str` ("14 Jan 2026"); `AvResult(status: "clean" | "infected" | "error", signature: str | None = None, message: str | None = None)`; `RuleContext` (fields below); `Outcome(status, reason, fix_hint=None, excerpt=None)`; `Rule(code, name, severity: "hard" | "soft" | "advisory", weight, check)`; `RULES: dict[str, Rule]`; `RULES_VERSION = "1a.1"`; `run_order(slot_rules: list[str]) -> list[str]`; `Decision(verdict: "accept" | "review" | "reject", confidence: float | None)`; `decide(results: list[tuple[Rule, Outcome]], accept: float, reject: float) -> Decision`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_dates.py`:
```python
from datetime import date

from assayr.verification.dates import best_evidence_date, find_dates, format_day

TODAY = date(2026, 10, 7)


def values(text):
    return [f.value for f in find_dates(text)]


def test_common_formats():
    text = "A 2026-03-14 B 14/03/2026 C 14 March 2026 D March 14, 2026 E 3rd Feb 2026 F 14-Mar-2026"
    assert values(text) == [date(2026, 3, 14)] * 4 + [date(2026, 2, 3), date(2026, 3, 14)]


def test_invalid_dates_are_ignored():
    assert values("Dated 31/02/2026 and 2026-13-01 and 14 March 1900") == []


def test_labels_come_from_the_words_just_before_the_date():
    found = find_dates(
        "Approval date: 14 January 2026. Next review: 14 January 2027. "
        "Last reviewed on 3 March 2026. Effective 1 Feb 2026."
    )
    assert [(f.value, f.label) for f in found] == [
        (date(2026, 1, 14), "approval"),
        (date(2027, 1, 14), "next_review"),
        (date(2026, 3, 3), "review"),
        (date(2026, 2, 1), "effective"),
    ]


def test_next_review_and_future_dates_are_not_the_evidence_date():
    found = find_dates("Next review date: 1 Jan 2026. Printed 2026-12-25. Dated 2026-02-01.")
    assert best_evidence_date(found, TODAY).value == date(2026, 2, 1)


def test_labelled_dates_beat_unlabelled_ones():
    found = find_dates("Change log 2026-09-01. Approved by S. Malik on 2026-03-01.")
    assert best_evidence_date(found, TODAY).value == date(2026, 3, 1)


def test_no_dates():
    assert best_evidence_date(find_dates("no dates here"), TODAY) is None


def test_format_day():
    assert format_day(date(2026, 2, 4)) == "4 Feb 2026"
```

`backend/tests/test_rules.py`:
```python
from datetime import date, timedelta

from assayr.evidence.extract import PDF, Extracted
from assayr.verification.av import AvResult
from assayr.verification.dates import best_evidence_date, find_dates
from assayr.verification.rules import RULES, RuleContext, decide, run_order

TODAY = date(2026, 10, 7)
GOOD_POLICY = (
    "Acme Financial Services\nInformation Security Policy\nVersion 3.0\nDocument owner: Sana Malik\n"
    "Approved by: Tariq Qureshi. Approval date: 14 January 2026\nNext review: 14 January 2027\n"
    "Objectives and responsibilities are set out below."
)


def ctx(text="", *, mime=PDF, filename="evidence.pdf", freshness=365, concepts=(), supplied=None,
        duplicate=False, av=None, error=None, pages=1, metadata=None):
    found = find_dates(text)
    best = best_evidence_date(found, TODAY)
    return RuleContext(
        filename=filename, mime=mime,
        extracted=Extracted(text=text, pages=pages, metadata=metadata or {}, error=error),
        org_names=["Acme Financial Services"], freshness_days=freshness, required_concepts=list(concepts),
        today=TODAY, supplied_date=supplied, evidence_date=supplied or (best.value if best else None),
        found_dates=found, duplicate_in_slot=duplicate, av_result=av,
    )


def check(code, context):
    return RULES[code].check(context)


def test_format_rule():
    assert check("V-FMT", ctx("x", mime=None)).status == "fail"
    unreadable = check("V-FMT", ctx(error="The PDF is password-protected."))
    assert unreadable.status == "fail" and unreadable.reason == "The PDF is password-protected."
    assert check("V-FMT", ctx("text")).reason == "PDF opened and read, 1 page."


def test_malware_rule():
    assert check("V-AV", ctx("x")).status == "skipped"
    assert check("V-AV", ctx("x", av=AvResult("clean"))).status == "pass"
    infected = check("V-AV", ctx("x", av=AvResult("infected", signature="Eicar-Signature")))
    assert infected.status == "fail" and "Eicar-Signature" in infected.reason
    assert check("V-AV", ctx("x", av=AvResult("error", message="refused"))).status == "warn"


def test_scope_rule():
    assert check("V-SCOPE", ctx(GOOD_POLICY)).status == "pass"
    assert check("V-SCOPE", ctx("Globex Corp policy")).status == "fail"
    assert check("V-SCOPE", ctx("", mime="image/png")).status == "skipped"


def test_date_rule():
    assert check("V-DATE", ctx(GOOD_POLICY)).reason == "Document date 14 Jan 2026 (approval date)."
    assert check("V-DATE", ctx("no date", supplied=date(2026, 9, 1))).status == "pass"
    assert check("V-DATE", ctx("no date at all")).status == "fail"


def test_freshness_rule():
    recent = (TODAY - timedelta(days=30)).isoformat()
    old = (TODAY - timedelta(days=400)).isoformat()
    assert check("V-FRESH", ctx(f"Dated {recent}")).status == "pass"
    stale = check("V-FRESH", ctx(f"Dated {old}"))
    assert stale.status == "fail" and "outside the 365-day window" in stale.reason
    assert check("V-FRESH", ctx("no date")).status == "fail"
    assert check("V-FRESH", ctx("", mime="image/png")).status == "warn"
    assert check("V-FRESH", ctx(f"Dated {recent}", freshness=None)).status == "skipped"


def test_document_control_rules():
    for code in ("V-APPROVAL", "V-VERSION", "V-OWNER"):
        assert check(code, ctx(GOOD_POLICY)).status == "pass", code
        assert check(code, ctx("A plain draft with no control details.")).status == "fail", code
    assert check("V-OWNER", ctx("plain text", metadata={"author": "Sana"})).status == "pass"


def test_review_rule():
    assert check("V-REVIEW", ctx(GOOD_POLICY)).reason == "Next review 14 Jan 2027."
    assert check("V-REVIEW", ctx("Next review: 1 March 2026")).status == "fail"
    assert check("V-REVIEW", ctx("Last reviewed on 1 March 2026")).status == "pass"
    assert check("V-REVIEW", ctx("nothing about reviews")).status == "warn"


def test_keyword_rule_uses_synonyms():
    concepts = ["MFA", "authentication", "password", "length"]
    assert check("V-KEYWORDS", ctx("Multi-factor authentication; password length 14", concepts=concepts)).status == "pass"
    assert check("V-KEYWORDS", ctx("authentication and password only", concepts=concepts)).status == "warn"
    assert check("V-KEYWORDS", ctx("nothing relevant", concepts=concepts)).status == "fail"
    assert check("V-KEYWORDS", ctx("text", concepts=())).status == "skipped"


def test_sensitive_data_rule():
    assert check("V-PII", ctx("card 4111 1111 1111 1111")).status == "warn"
    assert check("V-PII", ctx("password: hunter2hunter")).status == "warn"
    assert check("V-PII", ctx("-----BEGIN RSA PRIVATE KEY-----")).status == "warn"
    assert check("V-PII", ctx(GOOD_POLICY)).status == "pass"


def test_rules_that_need_later_components_are_skipped_with_a_reason():
    for code in ("V-RELEVANCE", "V-SCREENSHOT", "V-COMPLETENESS", "V-SIGNATURE"):
        outcome = check(code, ctx(GOOD_POLICY))
        assert outcome.status == "skipped" and outcome.reason


def test_run_order_dedupes_and_wraps_slot_rules():
    assert run_order(["V-FMT", "V-DATE", "V-NOPE", "V-APPROVAL"]) == [
        "V-FMT", "V-AV", "V-HASH", "V-SCOPE", "V-DATE", "V-APPROVAL", "V-PII",
    ]


def outcome(code, status):
    from assayr.verification.rules import Outcome

    return RULES[code], Outcome(status, "r")


def test_decide():
    assert decide([outcome("V-FMT", "fail"), outcome("V-APPROVAL", "pass")], 0.85, 0.6).verdict == "reject"
    accept = decide([outcome("V-SCOPE", "pass"), outcome("V-APPROVAL", "pass")], 0.85, 0.6)
    assert (accept.verdict, accept.confidence) == ("accept", 1.0)
    review = decide([outcome("V-DATE", "pass"), outcome("V-OWNER", "pass"), outcome("V-APPROVAL", "fail"),
                     outcome("V-REVIEW", "pass"), outcome("V-KEYWORDS", "pass"), outcome("V-SCOPE", "pass")],
                    0.85, 0.6)
    assert (review.verdict, review.confidence) == ("review", 0.73)
    assert decide([outcome("V-APPROVAL", "fail"), outcome("V-DATE", "pass")], 0.85, 0.6).verdict == "reject"
    nothing = decide([outcome("V-FMT", "pass"), outcome("V-RELEVANCE", "skipped")], 0.85, 0.6)
    assert (nothing.verdict, nothing.confidence) == ("review", None)
```
(The review case: DATE 2 + OWNER 1 + REVIEW 2 + KEYWORDS 2 + SCOPE 1 = 8 passing of 11 total weight → 0.727 → 0.73.)

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_dates.py tests/test_rules.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'assayr.verification'`.

- [ ] **Step 3: Implement dates**

`backend/src/assayr/verification/dates.py`:
```python
"""Find dates in document text and work out which one dates the evidence."""

import re
from dataclasses import dataclass
from datetime import date, timedelta

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4,
    "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9,
    "september": 9, "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
_MONTH = (
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
    r"sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_PATTERNS = [
    (re.compile(r"(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)"), "ymd"),
    (re.compile(r"(?<!\d)(\d{1,2})[/.](\d{1,2})[/.](\d{4})(?!\d)"), "dmy"),
    (re.compile(r"(?<!\d)(\d{1,2})(?:st|nd|rd|th)?[\s-]+" + _MONTH + r"\.?,?[\s-]+(\d{4})(?!\d)", re.I), "d_mon_y"),
    (re.compile(r"\b" + _MONTH + r"\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})(?!\d)", re.I), "mon_d_y"),
]
# (keyword, label). The keyword ending closest before a date labels it; specific beats the generic "date".
_LABELS = [
    ("next review date", "next_review"), ("next review", "next_review"), ("review due", "next_review"),
    ("last reviewed", "review"), ("reviewed", "review"), ("review date", "review"),
    ("approved", "approval"), ("approval", "approval"), ("signed", "approval"),
    ("effective", "effective"), ("issued", "issue"), ("issue date", "issue"),
    ("as of", "as_of"), ("as at", "as_of"), ("period", "period"), ("dated", "date"), ("date", "date"),
]
_EVIDENCE_LABELS = {"approval", "effective", "issue", "as_of", "period", "date"}


@dataclass(frozen=True)
class FoundDate:
    value: date
    label: str | None
    position: int
    excerpt: str


def format_day(value: date) -> str:
    return f"{value.day} {value.strftime('%b %Y')}"


def find_dates(text: str) -> list[FoundDate]:
    found: dict[int, FoundDate] = {}
    for pattern, kind in _PATTERNS:
        for match in pattern.finditer(text):
            value = _to_date(match, kind)
            if value is None or match.start() in found:
                continue
            start = match.start()
            context = text[max(0, start - 60) : start].lower()
            excerpt = " ".join(text[max(0, start - 40) : match.end() + 5].split())
            found[start] = FoundDate(value=value, label=_label(context), position=start, excerpt=excerpt)
    return sorted(found.values(), key=lambda f: f.position)


def best_evidence_date(found: list[FoundDate], today: date) -> FoundDate | None:
    """The latest labelled date that isn't in the future or a next-review date; else the latest past date."""
    candidates = [f for f in found if f.value <= today + timedelta(days=1) and f.label != "next_review"]
    preferred = [f for f in candidates if f.label in _EVIDENCE_LABELS]
    pool = preferred or candidates
    return max(pool, key=lambda f: f.value) if pool else None


def _to_date(match: re.Match, kind: str) -> date | None:
    try:
        if kind == "ymd":
            year, month, day = int(match[1]), int(match[2]), int(match[3])
        elif kind == "dmy":
            day, month, year = int(match[1]), int(match[2]), int(match[3])
        elif kind == "d_mon_y":
            day, month, year = int(match[1]), _MONTHS[match[2].lower()], int(match[3])
        else:
            month, day, year = _MONTHS[match[1].lower()], int(match[2]), int(match[3])
        if not 1990 <= year <= 2100:
            return None
        return date(year, month, day)
    except (ValueError, KeyError):
        return None


def _label(context: str) -> str | None:
    hits = []
    for keyword, label in _LABELS:
        index = context.rfind(keyword)
        if index >= 0:
            hits.append((index + len(keyword), len(keyword), label))
    if not hits:
        return None
    specific = [h for h in hits if h[2] != "date" and len(context) - h[0] <= 25]
    return max(specific or hits)[2]
```

- [ ] **Step 4: Implement the rule library**

`backend/src/assayr/verification/av.py` (dataclass only for now):
```python
"""ClamAV client (clamd INSTREAM protocol)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AvResult:
    status: str  # clean | infected | error
    signature: str | None = None
    message: str | None = None
```

`backend/src/assayr/verification/rules.py`:
```python
"""Deterministic evidence checks (see vault: 03-Product/Verification Rule Library.md)."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from assayr.evidence.extract import ALLOWED_TYPES, KIND_LABEL, Extracted
from assayr.verification.av import AvResult
from assayr.verification.dates import FoundDate, best_evidence_date, format_day

RULES_VERSION = "1a.1"
_SCORE = {"pass": 1.0, "warn": 0.5, "fail": 0.0}
_GLOBAL_FIRST = ["V-FMT", "V-AV", "V-HASH", "V-SCOPE"]
_GLOBAL_LAST = ["V-PII"]
_DATE_LABEL_TEXT = {
    "approval": "approval date", "effective": "effective date", "issue": "issue date",
    "as_of": "as-of date", "period": "period", "date": "dated",
}
_APPROVAL = re.compile(r"\b(approved\s+by|approval|approver|signed\s+off|sign-off|signed\s+by|authori[sz]ed\s+by)\b", re.I)
_VERSION = re.compile(r"\b(version\s*\d+(\.\d+)*|v\d+(\.\d+)+|revision\s+history|document\s+control|rev\.?\s*\d+)\b", re.I)
_OWNER = re.compile(r"\b(document\s+owner|owner\s*:|owned\s+by|author\s*:|prepared\s+by)", re.I)
_PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----")
_CLOUD_KEY = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_PASSWORD = re.compile(r"\b(?:password|passwd|pwd)\s*[:=]\s*\S{4,}", re.I)
_NATIONAL_ID = re.compile(r"(?<!\d)\d{5}-\d{7}-\d(?!\d)")
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_SYNONYMS = {
    "mfa": ["multi-factor", "multifactor", "two-factor", "2fa"],
    "multi-factor": ["mfa", "two-factor", "2fa"],
    "access review": ["access recertification", "user access review", "access certification"],
    "backup": ["back-up", "back up"],
    "restore test": ["restoration test", "recovery test", "restore testing"],
    "encryption": ["encrypted", "encrypt", "cryptograph"],
    "approved": ["approval", "approve"],
    "approval": ["approved", "approve", "sign-off", "signed off"],
    "review": ["reviewed"],
    "responsibilities": ["responsibility", "responsible"],
    "training": ["trained", "course"],
    "rto": ["recovery time objective"],
    "rpo": ["recovery point objective"],
}


@dataclass
class RuleContext:
    filename: str
    mime: str | None
    extracted: Extracted
    org_names: list[str]
    freshness_days: int | None
    required_concepts: list[str]
    today: date
    supplied_date: date | None
    evidence_date: date | None
    found_dates: list[FoundDate]
    duplicate_in_slot: bool
    av_result: AvResult | None


@dataclass(frozen=True)
class Outcome:
    status: str  # pass | warn | fail | skipped
    reason: str
    fix_hint: str | None = None
    excerpt: str | None = None


@dataclass(frozen=True)
class Rule:
    code: str
    name: str
    severity: str  # hard | soft | advisory
    weight: float
    check: Callable[[RuleContext], Outcome]


@dataclass(frozen=True)
class Decision:
    verdict: str  # accept | review | reject
    confidence: float | None


def _no_text(ctx: RuleContext) -> bool:
    return not ctx.extracted.text.strip()


def _line_at(text: str, start: int) -> str:
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    return text[line_start : line_end if line_end >= 0 else len(text)].strip()[:200]


def check_format(ctx: RuleContext) -> Outcome:
    if ctx.mime is None or ctx.mime not in ALLOWED_TYPES:
        return Outcome("fail", "This file type isn't accepted as evidence.",
                       "Upload a PDF, Word, Excel, CSV, text, PNG or JPEG file.")
    if ctx.extracted.error:
        return Outcome("fail", ctx.extracted.error,
                       "Save or export the document again (for example as PDF) without a password, then upload it.")
    pages = ctx.extracted.pages
    detail = f", {pages} page{'s' if pages != 1 else ''}" if pages else ""
    return Outcome("pass", f"{KIND_LABEL[ctx.mime]} opened and read{detail}.")


def check_av(ctx: RuleContext) -> Outcome:
    result = ctx.av_result
    if result is None:
        return Outcome("skipped", "Malware scanning is not configured on this server.")
    if result.status == "clean":
        return Outcome("pass", "No malware found.")
    if result.status == "infected":
        return Outcome("fail", f"Flagged by the malware scanner: {result.signature}.",
                       "Don't use this file. Contact your administrator.")
    return Outcome("warn", "The malware scanner could not be reached, so this file wasn't scanned.")


def check_duplicate(ctx: RuleContext) -> Outcome:
    if ctx.duplicate_in_slot:
        return Outcome("warn", "This exact file is already attached to this evidence slot.")
    return Outcome("pass", "New file for this slot.")


def check_scope(ctx: RuleContext) -> Outcome:
    names = [n for n in ctx.org_names if len(n.strip()) >= 3]
    if not names:
        return Outcome("skipped", "No organization name is configured.")
    haystack = f"{ctx.extracted.text} {ctx.filename}".lower()
    for name in names:
        if name.lower() in haystack:
            return Outcome("pass", f"Found “{name}”.")
    if _no_text(ctx):
        return Outcome("skipped", "There's no readable text to check.")
    return Outcome("fail", "Your organization's name doesn't appear in the document.",
                   "Is this a template or another company's document? Upload your own version.")


def check_date(ctx: RuleContext) -> Outcome:
    if ctx.supplied_date:
        return Outcome("pass", f"Evidence date given at upload: {format_day(ctx.supplied_date)}.")
    best = best_evidence_date(ctx.found_dates, ctx.today)
    if best:
        label = _DATE_LABEL_TEXT.get(best.label or "")
        return Outcome("pass", f"Document date {format_day(best.value)}{f' ({label})' if label else ''}.",
                       excerpt=best.excerpt)
    if _no_text(ctx):
        return Outcome("skipped", "There's no readable text to find a date in.", "Add the evidence date when you upload.")
    return Outcome("fail", "No document date found.", "Add the evidence date when you upload, or upload a dated version.")


def check_fresh(ctx: RuleContext) -> Outcome:
    if not ctx.freshness_days:
        return Outcome("skipped", "This evidence has no freshness window.")
    if ctx.evidence_date is None:
        if _no_text(ctx):
            return Outcome("warn", "Couldn't read a date from this file, so a reviewer will confirm it's recent.",
                           "Add the evidence date when you upload.")
        return Outcome("fail", "Couldn't confirm the evidence is recent: no date found.",
                       "Add the evidence date when you upload, or upload a dated version.")
    age = (ctx.today - ctx.evidence_date).days
    when = format_day(ctx.evidence_date)
    if age > ctx.freshness_days:
        return Outcome("fail", f"Dated {when}, which is outside the {ctx.freshness_days}-day window.",
                       "Upload the latest version of this evidence.")
    return Outcome("pass", f"Dated {when}, within the {ctx.freshness_days}-day window.")


def _pattern_rule(pattern: re.Pattern, found: str, missing: str, hint: str) -> Callable[[RuleContext], Outcome]:
    def check(ctx: RuleContext) -> Outcome:
        if _no_text(ctx):
            return Outcome("skipped", "There's no readable text to check.")
        match = pattern.search(ctx.extracted.text)
        if match:
            return Outcome("pass", found, excerpt=_line_at(ctx.extracted.text, match.start()))
        return Outcome("fail", missing, hint)

    return check


check_approval = _pattern_rule(
    _APPROVAL, "Approval or sign-off found.", "No approval or sign-off found. This looks like a draft.",
    "Upload the approved version, or add an approval record to the document.",
)
check_version = _pattern_rule(
    _VERSION, "Version number or revision history found.", "No version number or revision history found.",
    "Add a version number and a revision history table.",
)
_owner_in_text = _pattern_rule(
    _OWNER, "Document owner named.", "No document owner named.", "Name the document owner in the document control table."
)


def check_owner(ctx: RuleContext) -> Outcome:
    outcome = _owner_in_text(ctx)
    author = ctx.extracted.metadata.get("author")
    if outcome.status != "pass" and author:
        return Outcome("pass", f"Author in the file properties: {author}.")
    return outcome


def check_review(ctx: RuleContext) -> Outcome:
    if _no_text(ctx):
        return Outcome("skipped", "There's no readable text to check.")
    next_reviews = [f for f in ctx.found_dates if f.label == "next_review"]
    upcoming = [f for f in next_reviews if f.value >= ctx.today]
    if upcoming:
        return Outcome("pass", f"Next review {format_day(min(f.value for f in upcoming))}.")
    if next_reviews:
        latest = max(f.value for f in next_reviews)
        return Outcome("fail", f"The next review date ({format_day(latest)}) has passed.",
                       "Review the document and upload the updated version.")
    reviews = [f for f in ctx.found_dates if f.label == "review" and 0 <= (ctx.today - f.value).days <= 365]
    if reviews:
        return Outcome("pass", f"Last reviewed {format_day(max(f.value for f in reviews))}.")
    return Outcome("warn", "No review date found.", "Add a next-review date to the document control table.")


def _has_concept(concept: str, text: str) -> bool:
    lowered = concept.lower()
    variants = [lowered, *_SYNONYMS.get(lowered, [])]
    return any(re.search(r"(?<![a-z0-9])" + re.escape(v), text) for v in variants)


def check_keywords(ctx: RuleContext) -> Outcome:
    concepts = ctx.required_concepts
    if not concepts:
        return Outcome("skipped", "No required topics are defined for this evidence.")
    if _no_text(ctx):
        return Outcome("skipped", "There's no readable text to check.")
    text = ctx.extracted.text.lower()
    missing = [c for c in concepts if not _has_concept(c, text)]
    found = len(concepts) - len(missing)
    ratio = found / len(concepts)
    summary = f"{found} of {len(concepts)} required topics found"
    if ratio >= 0.8:
        return Outcome("pass", f"{summary}." if not missing else f"{summary}; missing: {', '.join(missing)}.")
    return Outcome("warn" if ratio >= 0.5 else "fail", f"{summary}; missing: {', '.join(missing)}.",
                   "Check the document covers the points under “What auditors look for”.")


def _luhn(digits: str) -> bool:
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2 == 1:
            value = value * 2 - 9 if value > 4 else value * 2
        total += value
    return total % 10 == 0


def check_pii(ctx: RuleContext) -> Outcome:
    if _no_text(ctx):
        return Outcome("skipped", "There's no readable text to scan.")
    text = ctx.extracted.text
    findings = []
    if _PRIVATE_KEY.search(text):
        findings.append("a private key")
    if _CLOUD_KEY.search(text):
        findings.append("a cloud access key")
    if _PASSWORD.search(text):
        findings.append("a password")
    if _NATIONAL_ID.search(text):
        findings.append("national ID numbers")
    if any(_luhn(re.sub(r"\D", "", m.group())) for m in _CARD.finditer(text)):
        findings.append("payment card numbers")
    if len(set(_EMAIL.findall(text))) >= 50:
        findings.append("a bulk list of email addresses")
    if not findings:
        return Outcome("pass", "No secrets or personal identifiers found.")
    return Outcome("warn", f"Possible sensitive data: {', '.join(findings)}.",
                   "Redact it before keeping this as evidence, and rotate any exposed credentials.")


def _unavailable(reason: str) -> Callable[[RuleContext], Outcome]:
    return lambda ctx: Outcome("skipped", reason)


RULES: dict[str, Rule] = {
    rule.code: rule
    for rule in [
        Rule("V-FMT", "File readable", "hard", 0, check_format),
        Rule("V-AV", "Malware scan", "hard", 0, check_av),
        Rule("V-HASH", "Duplicate check", "advisory", 0, check_duplicate),
        Rule("V-SCOPE", "Organization match", "soft", 1, check_scope),
        Rule("V-DATE", "Document date", "soft", 2, check_date),
        Rule("V-FRESH", "Within freshness window", "hard", 2, check_fresh),
        Rule("V-APPROVAL", "Approval / sign-off", "soft", 3, check_approval),
        Rule("V-VERSION", "Version control", "soft", 1, check_version),
        Rule("V-OWNER", "Owner named", "soft", 1, check_owner),
        Rule("V-REVIEW", "Review cycle", "soft", 2, check_review),
        Rule("V-KEYWORDS", "Required topics", "soft", 2, check_keywords),
        Rule("V-PII", "Sensitive data scan", "advisory", 0, check_pii),
        Rule("V-RELEVANCE", "Relevance to the control", "soft", 3,
             _unavailable("Needs the local AI model, which isn't enabled yet.")),
        Rule("V-SCREENSHOT", "Screenshot provenance", "soft", 2,
             _unavailable("Needs text recognition (OCR), which isn't enabled yet.")),
        Rule("V-COMPLETENESS", "Population coverage", "soft", 3,
             _unavailable("Needs the people directory, which isn't connected yet.")),
        Rule("V-SIGNATURE", "Digital signature", "soft", 2,
             _unavailable("Digital signature checks aren't available yet.")),
    ]
}


def run_order(slot_rules: list[str]) -> list[str]:
    ordered: list[str] = []
    for code in [*_GLOBAL_FIRST, *slot_rules, *_GLOBAL_LAST]:
        if code in RULES and code not in ordered:
            ordered.append(code)
    return ordered


def decide(results: list[tuple[Rule, Outcome]], accept: float, reject: float) -> Decision:
    hard_fail = any(rule.severity == "hard" and o.status == "fail" for rule, o in results)
    soft = [(rule, o) for rule, o in results if rule.severity == "soft" and o.status in _SCORE]
    weight = sum(rule.weight for rule, _ in soft)
    confidence = round(sum(rule.weight * _SCORE[o.status] for rule, o in soft) / weight, 2) if weight else None
    if hard_fail:
        return Decision("reject", confidence)
    if confidence is None:
        return Decision("review", None)
    if confidence < reject:
        return Decision("reject", confidence)
    if confidence < accept:
        return Decision("review", confidence)
    return Decision("accept", confidence)
```

- [ ] **Step 5: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_dates.py tests/test_rules.py -W error`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(verification): date finding and deterministic rule library" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: ClamAV scanner client

**Files:**
- Modify: `backend/src/assayr/verification/av.py`
- Test: `backend/tests/test_av.py`

**Interfaces:**
- Produces: `scan_file(path: Path, host: str, port: int, timeout: float = 30.0) -> AvResult`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_av.py`:
```python
import socket
import struct
import threading

import pytest

from assayr.verification.av import scan_file

EICAR_MARKER = b"EICAR-TEST"


def _fake_clamd(reply_for):
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)

    def serve():
        conn, _ = server.accept()
        with conn:
            command = b""
            while not command.endswith(b"\0"):
                command += conn.recv(1)
            assert command == b"zINSTREAM\0"
            data = b""
            while True:
                (size,) = struct.unpack("!I", conn.recv(4, socket.MSG_WAITALL))
                if size == 0:
                    break
                data += conn.recv(size, socket.MSG_WAITALL)
            conn.sendall(reply_for(data))
        server.close()

    threading.Thread(target=serve, daemon=True).start()
    return server.getsockname()[1]


@pytest.fixture
def sample(tmp_path):
    def make(content):
        path = tmp_path / "f.bin"
        path.write_bytes(content)
        return path

    return make


def reply(data):
    return b"stream: Eicar-Signature FOUND\0" if EICAR_MARKER in data else b"stream: OK\0"


def test_clean_file(sample):
    assert scan_file(sample(b"hello" * 50_000), "127.0.0.1", _fake_clamd(reply)).status == "clean"


def test_infected_file_reports_the_signature(sample):
    result = scan_file(sample(b"x" + EICAR_MARKER), "127.0.0.1", _fake_clamd(reply))
    assert (result.status, result.signature) == ("infected", "Eicar-Signature")


def test_unreachable_scanner_is_an_error(sample):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        free_port = probe.getsockname()[1]
    assert scan_file(sample(b"x"), "127.0.0.1", free_port, timeout=1).status == "error"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_av.py`
Expected: FAIL — `ImportError: cannot import name 'scan_file'`.

- [ ] **Step 3: Implement**

Append to `backend/src/assayr/verification/av.py` (add imports `socket`, `struct`, `from pathlib import Path` at the top):
```python
_CHUNK = 64 * 1024


def scan_file(path: Path, host: str, port: int, timeout: float = 30.0) -> AvResult:
    """Stream the file to clamd with INSTREAM and interpret its one-line reply."""
    try:
        with socket.create_connection((host, port), timeout=timeout) as conn:
            conn.sendall(b"zINSTREAM\0")
            with path.open("rb") as handle:
                while chunk := handle.read(_CHUNK):
                    conn.sendall(struct.pack("!I", len(chunk)) + chunk)
            conn.sendall(struct.pack("!I", 0))
            reply = b""
            while not reply.endswith(b"\0"):
                part = conn.recv(4096)
                if not part:
                    break
                reply += part
    except OSError as exc:
        return AvResult("error", message=str(exc))
    text = reply.rstrip(b"\0").decode(errors="replace").strip()
    if text.endswith(" OK"):
        return AvResult("clean")
    if text.endswith(" FOUND"):
        return AvResult("infected", signature=text.split(":", 1)[-1].rsplit(" FOUND", 1)[0].strip())
    return AvResult("error", message=text or "Empty reply from the malware scanner.")
```

- [ ] **Step 4: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_av.py -W error`
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(verification): ClamAV INSTREAM client" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Compliance scoring service

**Files:**
- Create: `backend/src/assayr/scoring/service.py`, `backend/tests/evidence_helpers.py`
- Test: `backend/tests/test_scoring.py`

**Interfaces:**
- Consumes: `Control`, `EvidenceSlot` (Phase 0), `ArtefactLink`, `Artefact`, `ArtefactVersion`, `Attestation`, `StatusTransition`, `ScoreSnapshot` (Task 1), `FREQ_DAYS` (`assayr.catalogue.seed`).
- Produces: `SLOT_SCORE: dict[str, float]`; `SlotView(slot_id, required: bool, state: str, link: ArtefactLink | None)`; `freshness_state(expires_on: date | None, today: date, warning_days: int, grace_days: int) -> str`; `slot_view(slot, links, today, settings) -> SlotView`; `slot_views(db, control, today, settings) -> list[SlotView]`; `latest_attestation(db, control) -> Attestation | None`; `ControlScore(status, score, views, attested)`; `evaluate(implementation_status, views, attested: bool, has_any_link: bool) -> ControlScore`; `recompute_control(db, control, now, settings, trigger) -> ControlScore`; `weighted_readiness(controls) -> float | None`; `scope_has_evidence(db, scope_id) -> bool`; `recompute_scope(db, scope_id, now, settings, trigger="Scheduled check") -> None` (also snapshots); `take_snapshot(db, scope_id, now) -> ScoreSnapshot | None`; `attestation_days(control) -> int`. Test helper `add_link(db, store, slot, *, scope_id, state="accepted", evidence_date=None, content=None, filename="evidence.pdf", mime="application/pdf", uploaded_by=None, artefact=None) -> ArtefactLink`.

- [ ] **Step 1: Write the test helper and failing tests**

`backend/tests/evidence_helpers.py`:
```python
"""Shortcuts for building evidence in tests without going through the API."""

import io
import uuid
from datetime import timedelta

from assayr.evidence.models import Artefact, ArtefactLink, ArtefactVersion


def add_link(db, store, slot, *, scope_id, state="accepted", evidence_date=None, content=None,
             filename="evidence.pdf", mime="application/pdf", uploaded_by=None, artefact=None):
    data = content if content is not None else f"evidence {uuid.uuid4()}".encode()
    blob = store.put(io.BytesIO(data), max_bytes=50_000_000)
    if artefact is None:
        artefact = Artefact(scope_id=scope_id, title=filename, uploaded_by_id=uploaded_by)
        db.add(artefact)
    version = ArtefactVersion(
        version_no=len(artefact.versions) + 1, sha256=blob.sha256, size=blob.size, filename=filename,
        mime=mime, uploaded_by_id=uploaded_by,
    )
    artefact.versions.append(version)
    db.flush()
    expires = evidence_date + timedelta(days=slot.freshness_days) if evidence_date and slot.freshness_days else None
    link = ArtefactLink(
        version_id=version.id, slot_id=slot.id, state=state, evidence_date=evidence_date, expires_on=expires,
        confidence=0.95 if state == "accepted" else None,
    )
    db.add(link)
    db.flush()
    return link
```

`backend/tests/test_scoring.py`:
```python
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from assayr.catalogue.models import Control
from assayr.db import utcnow
from assayr.scoring.models import Attestation, ScoreSnapshot, StatusTransition
from assayr.scoring.service import (
    SlotView,
    evaluate,
    freshness_state,
    recompute_control,
    recompute_scope,
    slot_views,
    take_snapshot,
    weighted_readiness,
)
from tests.evidence_helpers import add_link

TODAY = date(2026, 10, 7)


@pytest.mark.parametrize(
    "days_left,expected",
    [(None, "verified"), (31, "verified"), (30, "expiring"), (1, "expiring"), (0, "expired_grace"),
     (-13, "expired_grace"), (-14, "expired")],
)
def test_freshness_state(days_left, expected):
    expires = None if days_left is None else TODAY + timedelta(days=days_left)
    assert freshness_state(expires, TODAY, warning_days=30, grace_days=14) == expected


def views(*states, required=True):
    return [SlotView(slot_id=None, required=required, state=s, link=None) for s in states]


def test_evaluate_status_and_score():
    assert evaluate("implemented", views("verified", "verified"), True, True)[:2] == ("compliant", 100.0)
    assert evaluate("implemented", views("verified", "verified"), False, True)[:2] == ("at_risk", 90.0)
    assert evaluate("implemented", views("verified", "expiring"), True, True)[:2] == ("at_risk", 90.0)
    assert evaluate("implemented", views("verified", "pending"), True, True).status == "in_review"
    assert evaluate("implemented", views("verified", "missing"), True, True).status == "in_progress"
    assert evaluate("implemented", views("verified", "rejected"), True, True).status == "in_progress"
    expired = evaluate("implemented", views("verified", "verified", "expired"), True, True)
    assert (expired.status, expired.score) == ("non_compliant", 40.0)
    assert evaluate("not_started", views("missing", "missing"), False, False)[:2] == ("not_started", 0.0)
    assert evaluate("planned", views("missing"), False, False).status == "in_progress"


def test_optional_slots_do_not_count():
    result = evaluate("implemented", views("verified") + views("missing", required=False), True, True)
    assert result.status == "compliant"


def control_with_slots(db, code="A.8.13"):
    return db.scalar(select(Control).where(Control.code == code))


def test_slot_views_pick_the_newest_accepted_evidence(db, seeded, app, settings):
    control = control_with_slots(db)
    slot = control.slots[0]
    add_link(db, app.state.store, slot, scope_id=seeded.id, evidence_date=TODAY - timedelta(days=400))
    newest = add_link(db, app.state.store, slot, scope_id=seeded.id, evidence_date=TODAY - timedelta(days=2))
    add_link(db, app.state.store, control.slots[1], scope_id=seeded.id, state="in_review")
    db.commit()
    by_slot = {v.slot_id: v for v in slot_views(db, control, TODAY, settings)}
    assert by_slot[slot.id].state == "verified" and by_slot[slot.id].link.id == newest.id
    assert by_slot[control.slots[1].id].state == "pending"
    assert by_slot[control.slots[2].id].state == "missing"


def test_recompute_records_a_transition_only_when_status_changes(db, seeded, app, settings):
    control = control_with_slots(db)
    now = utcnow()
    add_link(db, app.state.store, control.slots[0], scope_id=seeded.id, evidence_date=now.date())
    result = recompute_control(db, control, now, settings, trigger="Evidence accepted: backup.pdf")
    db.commit()
    assert result.status == "in_progress" and control.status == "in_progress"
    # One of three slots verified: (1 + 0 + 0) / 3 × 100 × 0.9 (not attested) = 30.0
    assert control.score == pytest.approx(30.0)
    recompute_control(db, control, now, settings, trigger="Again")
    db.commit()
    transitions = list(db.scalars(select(StatusTransition)))
    assert [(t.from_status, t.to_status, t.trigger) for t in transitions] == [
        ("not_started", "in_progress", "Evidence accepted: backup.pdf")
    ]


def test_full_evidence_and_attestation_make_a_control_compliant(db, seeded, app, settings):
    now = utcnow()
    control = control_with_slots(db)
    for slot in control.slots:
        add_link(db, app.state.store, slot, scope_id=seeded.id, evidence_date=now.date())
    db.add(Attestation(control_id=control.id, statement="Operates as described.", attested_at=now,
                       valid_until=now + timedelta(days=31)))
    result = recompute_control(db, control, now, settings, trigger="test")
    assert (result.status, result.score) == ("compliant", 100.0)


def test_readiness_and_daily_snapshots(db, seeded, app, settings):
    now = utcnow()
    control = control_with_slots(db)
    add_link(db, app.state.store, control.slots[0], scope_id=seeded.id, evidence_date=now.date())
    recompute_scope(db, seeded.id, now, settings)
    db.commit()
    controls = list(db.scalars(select(Control).where(Control.scope_id == seeded.id)))
    assert weighted_readiness(controls) == pytest.approx(round(control.score / 93, 1), abs=0.1)
    assert db.scalar(select(func.count()).select_from(ScoreSnapshot)) == 1
    assert take_snapshot(db, seeded.id, now) is None
    assert db.scalar(select(func.count()).select_from(ScoreSnapshot)) == 1


def test_readiness_is_none_without_controls():
    assert weighted_readiness([]) is None
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_scoring.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'assayr.scoring.service'`.

- [ ] **Step 3: Implement**

`backend/src/assayr/scoring/service.py`:
```python
"""Derive slot states, control status and score, scope readiness (vault: Compliance Scoring Model)."""

import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from assayr.catalogue.models import Control, EvidenceSlot
from assayr.catalogue.seed import FREQ_DAYS
from assayr.config import Settings
from assayr.evidence.models import ArtefactLink
from assayr.scoring.models import Attestation, ScoreSnapshot, StatusTransition

SLOT_SCORE = {
    "verified": 1.0, "expiring": 0.8, "pending": 0.5, "expired_grace": 0.4,
    "rejected": 0.0, "missing": 0.0, "expired": 0.0,
}
NON_COMPLIANT_CAP = 40.0
UNATTESTED_FACTOR = 0.9


@dataclass(frozen=True)
class SlotView:
    slot_id: uuid.UUID | None
    required: bool
    state: str
    link: ArtefactLink | None


@dataclass(frozen=True)
class ControlScore:
    status: str
    score: float
    views: list[SlotView]
    attested: bool


def freshness_state(expires_on: date | None, today: date, warning_days: int, grace_days: int) -> str:
    if expires_on is None or today < expires_on - timedelta(days=warning_days):
        return "verified"
    if today < expires_on:
        return "expiring"
    if today < expires_on + timedelta(days=grace_days):
        return "expired_grace"
    return "expired"


def slot_view(slot: EvidenceSlot, links: list[ArtefactLink], today: date, settings: Settings) -> SlotView:
    live = [link for link in links if link.state != "superseded"]
    accepted = [link for link in live if link.state == "accepted"]
    if accepted:
        best = max(accepted, key=lambda link: (link.evidence_date or date.min, link.created_at))
        warning = settings.expiry_warning_days
        if slot.freshness_days:
            # A fixed 30-day warning would mark monthly evidence "expiring" the day after upload.
            warning = min(warning, slot.freshness_days // 4)
        state = freshness_state(best.expires_on, today, warning, settings.evidence_grace_days)
        return SlotView(slot.id, slot.required, state, best)
    for states, view_state in ((("verifying", "in_review"), "pending"), (("rejected",), "rejected")):
        matching = [link for link in live if link.state in states]
        if matching:
            return SlotView(slot.id, slot.required, view_state, max(matching, key=lambda link: link.created_at))
    return SlotView(slot.id, slot.required, "missing", None)


def slot_views(db: Session, control: Control, today: date, settings: Settings) -> list[SlotView]:
    links = db.scalars(
        select(ArtefactLink).join(EvidenceSlot, ArtefactLink.slot_id == EvidenceSlot.id)
        .where(EvidenceSlot.control_id == control.id)
    ).unique()
    by_slot: dict[uuid.UUID, list[ArtefactLink]] = {}
    for link in links:
        by_slot.setdefault(link.slot_id, []).append(link)
    return [slot_view(slot, by_slot.get(slot.id, []), today, settings) for slot in control.slots]


def latest_attestation(db: Session, control: Control) -> Attestation | None:
    return db.scalar(
        select(Attestation).where(Attestation.control_id == control.id).order_by(Attestation.attested_at.desc()).limit(1)
    )


def attestation_days(control: Control) -> int:
    return FREQ_DAYS.get(control.review_frequency or "", 365)


def evaluate(implementation_status: str, views: list[SlotView], attested: bool, has_any_link: bool) -> ControlScore:
    required = [v for v in views if v.required]
    states = [v.state for v in required]
    if any(s == "expired" for s in states):
        status = "non_compliant"
    elif not has_any_link and implementation_status == "not_started":
        status = "not_started"
    elif any(s in ("missing", "rejected") for s in states):
        status = "in_progress"
    elif any(s == "pending" for s in states):
        status = "in_review"
    elif any(s in ("expiring", "expired_grace") for s in states) or not attested:
        status = "at_risk"
    else:
        status = "compliant"
    base = sum(SLOT_SCORE[s] for s in states) / len(states) * 100 if states else 100.0
    score = base * (1.0 if attested else UNATTESTED_FACTOR)
    if status == "non_compliant":
        score = min(score, NON_COMPLIANT_CAP)
    elif status == "not_started":
        score = 0.0  # a control nobody has touched never counts toward readiness, even without required slots
    return ControlScore(status=status, score=round(score, 1), views=views, attested=attested)


def recompute_control(db: Session, control: Control, now: datetime, settings: Settings, trigger: str) -> ControlScore:
    views = slot_views(db, control, now.date(), settings)
    attestation = latest_attestation(db, control)
    attested = attestation is not None and attestation.valid_until > now
    has_any_link = any(v.link is not None for v in views)
    result = evaluate(control.implementation_status, views, attested, has_any_link)
    if result.status != control.status:
        db.add(StatusTransition(control_id=control.id, from_status=control.status, to_status=result.status,
                                trigger=trigger[:300], at=now))
        control.status = result.status
    control.score = result.score
    return result


def weighted_readiness(controls: list[Control]) -> float | None:
    counted = [c for c in controls if c.status != "excluded"]
    if not counted:
        return None
    return round(sum(c.score or 0.0 for c in counted) / len(counted), 1)


def scope_has_evidence(db: Session, scope_id: uuid.UUID) -> bool:
    count = db.scalar(
        select(func.count()).select_from(ArtefactLink)
        .join(EvidenceSlot, ArtefactLink.slot_id == EvidenceSlot.id)
        .join(Control, EvidenceSlot.control_id == Control.id)
        .where(Control.scope_id == scope_id)
    )
    return bool(count)


def take_snapshot(db: Session, scope_id: uuid.UUID, now: datetime) -> ScoreSnapshot | None:
    """One snapshot per scope per day, plus one whenever readiness changes during the day."""
    controls = list(db.scalars(select(Control).where(Control.scope_id == scope_id)))
    readiness = weighted_readiness(controls)
    if readiness is None:
        return None
    last = db.scalar(
        select(ScoreSnapshot).where(ScoreSnapshot.scope_id == scope_id).order_by(ScoreSnapshot.taken_at.desc()).limit(1)
    )
    if last is not None and last.taken_at.date() == now.date() and last.readiness == readiness:
        return None
    snapshot = ScoreSnapshot(scope_id=scope_id, taken_at=now, readiness=readiness,
                             status_counts=dict(Counter(c.status for c in controls)))
    db.add(snapshot)
    return snapshot


def recompute_scope(db: Session, scope_id: uuid.UUID, now: datetime, settings: Settings,
                    trigger: str = "Scheduled check") -> None:
    for control in db.scalars(select(Control).where(Control.scope_id == scope_id)):
        recompute_control(db, control, now, settings, trigger)
    db.flush()
    take_snapshot(db, scope_id, now)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_scoring.py -W error`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(scoring): slot states, derived control status, readiness and snapshots" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Job queue and `assayr worker`

**Files:**
- Modify: `backend/src/assayr/jobs.py` (functions), `backend/src/assayr/cli.py`, `backend/tests/conftest.py`, `backend/tests/evidence_helpers.py`
- Create: `backend/src/assayr/job_handlers.py`, `backend/src/assayr/scoring/jobs.py`
- Test: `backend/tests/test_jobs.py`, `backend/tests/test_cli.py` (append)

**Interfaces:**
- Consumes: `Job` model (Task 1), `recompute_scope` (Task 5), `BlobStore` (Task 1).
- Produces: `MAX_ATTEMPTS = 3`, `STALE_AFTER = timedelta(minutes=10)`; `JobEnv(settings: Settings, store: BlobStore, now: Callable[[], datetime])`; `HANDLERS: dict[str, Callable[[Session, dict, JobEnv], None]]`; `handler(kind)` decorator; `enqueue(db, kind, payload, now) -> Job`; `claim_next(db, now) -> Job | None`; `run_one(sessionmaker, env) -> bool`; `run_pending(sessionmaker, env, limit=100) -> int`; `enqueue_recompute_all(db, now)` (in `scoring/jobs.py`, handler kind `"recompute_scope"`); CLI `assayr worker [--once]`; test helper `run_jobs(app) -> int`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/evidence_helpers.py`:
```python
def run_jobs(app) -> int:
    from assayr.jobs import JobEnv, run_pending

    env = JobEnv(settings=app.state.settings, store=app.state.store, now=app.state.clock)
    return run_pending(app.state.db.sessionmaker, env)
```

Add to the top of `backend/tests/conftest.py` imports: `import assayr.job_handlers  # noqa: F401  (registers job handlers)`.

`backend/tests/test_jobs.py`:
```python
from datetime import timedelta

from sqlalchemy import select

from assayr.db import utcnow
from assayr.jobs import HANDLERS, Job, enqueue
from assayr.scoring.jobs import enqueue_recompute_all
from tests.evidence_helpers import run_jobs


def test_queued_job_runs_once(app, db, monkeypatch):
    seen = []
    monkeypatch.setitem(HANDLERS, "test.echo", lambda session, payload, env: seen.append(payload["n"]))
    enqueue(db, "test.echo", {"n": 1}, now=utcnow())
    db.commit()
    assert run_jobs(app) == 1
    assert seen == [1]
    assert db.scalar(select(Job.status)) == "done"
    assert run_jobs(app) == 0


def test_failing_job_retries_then_fails(app, db, clock, monkeypatch):
    def boom(session, payload, env):
        raise RuntimeError("disk full")

    monkeypatch.setitem(HANDLERS, "test.boom", boom)
    enqueue(db, "test.boom", {}, now=clock())
    db.commit()
    for attempt in (1, 2, 3):
        assert run_jobs(app) == 1
        db.expire_all()
        job = db.scalar(select(Job))
        assert job.attempts == attempt
        clock.advance(minutes=5)
    assert job.status == "failed" and "disk full" in job.last_error
    assert run_jobs(app) == 0


def test_unknown_kind_fails_immediately(app, db):
    enqueue(db, "test.nope", {}, now=utcnow())
    db.commit()
    run_jobs(app)
    job = db.scalar(select(Job))
    assert (job.status, job.last_error) == ("failed", "Unknown job kind: test.nope")


def test_stale_running_job_is_reclaimed(app, db, clock, monkeypatch):
    seen = []
    monkeypatch.setitem(HANDLERS, "test.echo", lambda session, payload, env: seen.append(1))
    job = enqueue(db, "test.echo", {}, now=clock())
    job.status, job.locked_at, job.attempts = "running", clock() - timedelta(minutes=11), 1
    db.commit()
    assert run_jobs(app) == 1 and seen == [1]


def test_recompute_all_enqueues_each_scope_once(app, db, seeded):
    enqueue_recompute_all(db, utcnow())
    enqueue_recompute_all(db, utcnow())
    db.commit()
    assert [j.kind for j in db.scalars(select(Job))] == ["recompute_scope"]
    assert run_jobs(app) == 1
```

Append to `backend/tests/test_cli.py`:
```python
def test_worker_once_processes_queued_jobs(cli_db, monkeypatch):
    from assayr.db import utcnow
    from assayr.jobs import HANDLERS, enqueue

    run("migrate")
    seen = []
    monkeypatch.setitem(HANDLERS, "test.echo", lambda session, payload, env: seen.append(payload))
    with Session(cli_db) as session:
        enqueue(session, "test.echo", {"n": 7}, now=utcnow())
        session.commit()
    result = run("worker", "--once")
    assert result.exit_code == 0 and "Processed 1 job." in result.output
    assert seen == [{"n": 7}]
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_jobs.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'assayr.job_handlers'`.

- [ ] **Step 3: Implement**

Append to `backend/src/assayr/jobs.py` (add imports `from collections.abc import Callable`, `from dataclasses import dataclass`, `from datetime import timedelta`, `from sqlalchemy import and_, or_, select`, `from sqlalchemy.orm import Session, sessionmaker`, `from assayr.config import Settings`, `from assayr.storage import BlobStore`):
```python
MAX_ATTEMPTS = 3
STALE_AFTER = timedelta(minutes=10)


@dataclass(frozen=True)
class JobEnv:
    settings: Settings
    store: BlobStore
    now: Callable[[], datetime]


HANDLERS: dict[str, Callable[[Session, dict, JobEnv], None]] = {}


def handler(kind: str):
    def register(func):
        HANDLERS[kind] = func
        return func

    return register


def enqueue(db: Session, kind: str, payload: dict, now: datetime) -> Job:
    job = Job(kind=kind, payload=payload, status="queued", attempts=0, run_after=now, created_at=now)
    db.add(job)
    db.flush()
    return job


def claim_next(db: Session, now: datetime) -> Job | None:
    """Claim the oldest runnable job; on PostgreSQL concurrent workers skip each other's locked rows."""
    stmt = (
        select(Job)
        .where(
            or_(
                and_(Job.status == "queued", Job.run_after <= now),
                and_(Job.status == "running", Job.locked_at < now - STALE_AFTER),
            )
        )
        .order_by(Job.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = db.scalar(stmt)
    if job is None:
        return None
    job.status = "running"
    job.locked_at = now
    job.attempts += 1
    db.commit()
    return job


def run_one(make_session: sessionmaker, env: JobEnv) -> bool:
    with make_session() as db:
        job = claim_next(db, env.now())
        if job is None:
            return False
        job_id = job.id
        func = HANDLERS.get(job.kind)
        if func is None:
            job.status = "failed"
            job.last_error = f"Unknown job kind: {job.kind}"
            db.commit()
            return True
        try:
            func(db, dict(job.payload), env)
            job = db.get(Job, job_id)
            job.status = "done"
            job.last_error = None
            db.commit()
        except Exception as exc:  # noqa: BLE001 - a failing job must never stop the worker
            db.rollback()
            job = db.get(Job, job_id)
            job.last_error = f"{type(exc).__name__}: {exc}"[:2000]
            if job.attempts >= MAX_ATTEMPTS:
                job.status = "failed"
            else:
                job.status = "queued"
                job.run_after = env.now() + timedelta(seconds=30 * job.attempts)
            db.commit()
        return True


def run_pending(make_session: sessionmaker, env: JobEnv, limit: int = 100) -> int:
    processed = 0
    while processed < limit and run_one(make_session, env):
        processed += 1
    return processed
```

`backend/src/assayr/scoring/jobs.py`:
```python
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.identity.models import Scope
from assayr.jobs import Job, JobEnv, enqueue, handler
from assayr.scoring.service import recompute_scope


@handler("recompute_scope")
def recompute_scope_job(db: Session, payload: dict, env: JobEnv) -> None:
    recompute_scope(db, uuid.UUID(payload["scope_id"]), env.now(), env.settings)
    db.commit()


def enqueue_recompute_all(db: Session, now: datetime) -> None:
    waiting = {
        job.payload.get("scope_id")
        for job in db.scalars(select(Job).where(Job.kind == "recompute_scope", Job.status.in_(["queued", "running"])))
    }
    for scope_id in db.scalars(select(Scope.id)):
        if str(scope_id) not in waiting:
            enqueue(db, "recompute_scope", {"scope_id": str(scope_id)}, now)
```

`backend/src/assayr/job_handlers.py`:
```python
"""Import every module that registers a job handler (used by the worker and tests)."""

import assayr.scoring.jobs  # noqa: F401
```

Add to `backend/src/assayr/cli.py` (imports: `import time`, `from datetime import timedelta`, `from assayr.db import utcnow`, `from assayr.jobs import JobEnv, run_one, run_pending`, `from assayr.storage import BlobStore`):
```python
@app.command()
def worker(once: bool = typer.Option(False, "--once", help="Process the queued jobs, then exit.")) -> None:
    """Run background jobs: evidence verification and scheduled status checks."""
    import assayr.job_handlers  # noqa: F401
    from assayr.scoring.jobs import enqueue_recompute_all

    settings = get_settings()
    database = _database()
    env = JobEnv(settings=settings, store=BlobStore(settings.storage_dir), now=utcnow)
    if once:
        processed = run_pending(database.sessionmaker, env)
        typer.echo(f"Processed {processed} job{'s' if processed != 1 else ''}.")
        return
    typer.echo("Worker started.")
    next_recompute = utcnow()
    while True:
        if utcnow() >= next_recompute:
            with database.sessionmaker() as session:
                enqueue_recompute_all(session, utcnow())
                session.commit()
            next_recompute = utcnow() + timedelta(minutes=settings.recompute_interval_minutes)
        if not run_one(database.sessionmaker, env):
            time.sleep(settings.worker_poll_seconds)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest -W error`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(jobs): database-backed job queue and assayr worker" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Verification engine

**Files:**
- Create: `backend/src/assayr/verification/engine.py`
- Modify: `backend/src/assayr/job_handlers.py`, `backend/tests/evidence_helpers.py`
- Test: `backend/tests/test_engine.py`

**Interfaces:**
- Consumes: `extract`, `sniff` (Task 2); `find_dates`, `best_evidence_date`, `RuleContext`, `RULES`, `RULES_VERSION`, `run_order`, `decide` (Task 3); `scan_file` (Task 4); `recompute_control` (Task 5); `handler`, `JobEnv` (Task 6); `record`, `SYSTEM` (Phase 0).
- Produces: `verify_link(db, link_id: uuid.UUID, env: JobEnv) -> VerificationRun | None` (no-op unless the link is `verifying`); `supersede_older(db, link)`; `VERDICT_STATE = {"accept": "accepted", "review": "in_review", "reject": "rejected"}`; job kind `"verify_link"` with payload `{"link_id": str}`; test helper `policy_text(today, *, approved=True, dated=None) -> str`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/evidence_helpers.py`:
```python
def long_date(value) -> str:
    return f"{value.day} {value.strftime('%B %Y')}"


def policy_text(today, *, approved=True, dated=None):
    """An information security policy that passes every rule for A.5.1's first slot when approved."""
    dated = dated or today - timedelta(days=30)
    lines = [
        "Acme Financial Services",
        "Information Security Policy",
        "Version 3.0",
        "Document owner: Sana Malik",
    ]
    if approved:
        lines.append(f"Approved by: Tariq Qureshi, Chief Executive. Approval date: {long_date(dated)}")
    else:
        lines.append(f"Dated {long_date(dated)}")
    lines += [
        f"Next review: {long_date(today + timedelta(days=330))}",
        "Objectives: protect the confidentiality, integrity and availability of information.",
        "Responsibilities: every employee follows this information security policy.",
    ]
    return "\n".join(lines)
```

`backend/tests/test_engine.py`:
```python
from datetime import timedelta

from sqlalchemy import func, select

from assayr.audit.models import AuditLog
from assayr.catalogue.models import Control
from assayr.jobs import JobEnv
from assayr.scoring.models import StatusTransition
from assayr.verification import engine
from assayr.verification.av import AvResult
from assayr.verification.engine import verify_link
from assayr.verification.rules import run_order
from tests.evidence_helpers import add_link, policy_text
from tests.fixtures import PNG_BYTES, make_pdf


def env_for(app):
    return JobEnv(settings=app.state.settings, store=app.state.store, now=app.state.clock)


def first_slot(db, code):
    control = db.scalar(select(Control).where(Control.code == code))
    return control, control.slots[0]


def upload(db, app, seeded, code, content, *, filename="policy.pdf", mime="application/pdf", artefact=None):
    control, slot = first_slot(db, code)
    link = add_link(db, app.state.store, slot, scope_id=seeded.id, state="verifying", content=content,
                    filename=filename, mime=mime, artefact=artefact)
    db.commit()
    return control, slot, link


def results(run):
    return {r.code: r.status for r in run.results}


def test_approved_policy_is_accepted_and_the_control_moves_on(app, db, seeded, clock):
    today = clock().date()
    control, slot, link = upload(db, app, seeded, "A.5.1", make_pdf(policy_text(today).split("\n")))
    run = verify_link(db, link.id, env_for(app))
    db.refresh(link)
    assert run.verdict == "accept" and link.state == "accepted" and link.confidence == 1.0
    assert len(run.results) == len(run_order(slot.rules))
    assert results(run)["V-RELEVANCE"] == "skipped"
    assert link.evidence_date == today - timedelta(days=30)
    assert link.expires_on == link.evidence_date + timedelta(days=slot.freshness_days)
    transition = db.scalar(select(StatusTransition).where(StatusTransition.control_id == control.id))
    assert (transition.to_status, "policy.pdf" in transition.trigger) == ("in_progress", True)
    assert db.scalar(select(AuditLog).where(AuditLog.action == "evidence.verdict")).diff["verdict"] == "accept"


def test_draft_without_approval_goes_to_review(app, db, seeded, clock):
    today = clock().date()
    _, _, link = upload(db, app, seeded, "A.5.1", make_pdf(policy_text(today, approved=False).split("\n")))
    run = verify_link(db, link.id, env_for(app))
    assert results(run)["V-APPROVAL"] == "fail"
    assert run.verdict == "review" and db.get(type(link), link.id).state == "in_review"


def test_stale_evidence_is_rejected(app, db, seeded, clock):
    old = clock().date() - timedelta(days=200)
    text = f"Acme Financial Services quarterly access review. Approved by Sana Malik on {old.isoformat()}."
    _, _, link = upload(db, app, seeded, "A.5.18", make_pdf([text]))
    run = verify_link(db, link.id, env_for(app))
    assert results(run)["V-FRESH"] == "fail" and run.verdict == "reject"


def test_images_go_to_review_because_nothing_can_be_read(app, db, seeded):
    _, _, link = upload(db, app, seeded, "A.5.1", PNG_BYTES, filename="shot.png", mime="image/png")
    run = verify_link(db, link.id, env_for(app))
    assert results(run)["V-FMT"] == "pass" and results(run)["V-APPROVAL"] == "skipped"
    assert run.verdict == "review"


def test_unreadable_file_is_rejected(app, db, seeded):
    _, _, link = upload(db, app, seeded, "A.5.1", b"%PDF-1.4\nbroken")
    run = verify_link(db, link.id, env_for(app))
    assert results(run)["V-FMT"] == "fail" and run.verdict == "reject"


def test_infected_file_is_rejected(app, db, seeded, clock, monkeypatch):
    app.state.settings = app.state.settings.model_copy(update={"clamav_host": "clamav"})
    monkeypatch.setattr(engine, "scan_file", lambda *a, **k: AvResult("infected", signature="Eicar-Signature"))
    _, _, link = upload(db, app, seeded, "A.5.1", make_pdf(policy_text(clock().date()).split("\n")))
    run = verify_link(db, link.id, env_for(app))
    assert results(run)["V-AV"] == "fail" and run.verdict == "reject"


def test_only_links_awaiting_verification_are_processed(app, db, seeded, clock):
    _, _, link = upload(db, app, seeded, "A.5.1", make_pdf(policy_text(clock().date()).split("\n")))
    verify_link(db, link.id, env_for(app))
    assert verify_link(db, link.id, env_for(app)) is None


def test_reverification_after_a_crash_completes(app, db, seeded, clock, monkeypatch):
    """A worker that died mid-run leaves a partial run behind; the retry finishes cleanly."""
    _, _, link = upload(db, app, seeded, "A.5.1", make_pdf(policy_text(clock().date()).split("\n")))
    real_decide = engine.decide

    def crash(*args, **kwargs):
        raise RuntimeError("worker killed")

    monkeypatch.setattr(engine, "decide", crash)
    try:
        verify_link(db, link.id, env_for(app))
    except RuntimeError:
        db.rollback()
    monkeypatch.setattr(engine, "decide", real_decide)
    assert db.get(type(link), link.id).state == "verifying"
    run = verify_link(db, link.id, env_for(app))
    assert run.verdict == "accept"


def test_a_newer_accepted_version_supersedes_the_older_one(app, db, seeded, clock):
    today = clock().date()
    _, _, first = upload(db, app, seeded, "A.5.1", make_pdf(policy_text(today).split("\n")))
    verify_link(db, first.id, env_for(app))
    newer = policy_text(today, dated=today - timedelta(days=1)).split("\n")
    _, _, second = upload(db, app, seeded, "A.5.1", make_pdf(newer), artefact=first.version.artefact)
    verify_link(db, second.id, env_for(app))
    db.expire_all()
    assert db.get(type(first), first.id).state == "superseded"
    assert db.get(type(second), second.id).state == "accepted"


def test_verify_job_runs_through_the_queue(app, db, seeded, clock):
    from assayr.jobs import enqueue
    from tests.evidence_helpers import run_jobs

    _, _, link = upload(db, app, seeded, "A.5.1", make_pdf(policy_text(clock().date()).split("\n")))
    enqueue(db, "verify_link", {"link_id": str(link.id)}, now=clock())
    db.commit()
    assert run_jobs(app) == 1
    assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "evidence.verdict")) == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_engine.py`
Expected: FAIL — `ImportError: cannot import name 'engine' from 'assayr.verification'`.

- [ ] **Step 3: Implement**

`backend/src/assayr/verification/engine.py`:
```python
"""Run the verification rules for one evidence link and apply the verdict (vault: Evidence Verification Engine Design)."""

import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from assayr.audit.service import SYSTEM, record
from assayr.evidence.extract import Extracted, extract
from assayr.evidence.models import ArtefactLink, ArtefactVersion, RuleResult, VerificationRun
from assayr.identity.models import Organization, Scope
from assayr.jobs import JobEnv, handler
from assayr.scoring.service import recompute_control
from assayr.verification.av import scan_file
from assayr.verification.dates import best_evidence_date, find_dates
from assayr.verification.rules import RULES, RULES_VERSION, RuleContext, decide, run_order

VERDICT_STATE = {"accept": "accepted", "review": "in_review", "reject": "rejected"}
VERDICT_WORD = {"accept": "accepted", "review": "sent to review", "reject": "rejected"}


@handler("verify_link")
def verify_link_job(db: Session, payload: dict, env: JobEnv) -> None:
    verify_link(db, uuid.UUID(payload["link_id"]), env)


def supersede_older(db: Session, link: ArtefactLink) -> None:
    older = db.scalars(
        select(ArtefactLink)
        .join(ArtefactVersion, ArtefactLink.version_id == ArtefactVersion.id)
        .where(
            ArtefactLink.slot_id == link.slot_id,
            ArtefactLink.id != link.id,
            ArtefactLink.state == "accepted",
            ArtefactVersion.artefact_id == link.version.artefact_id,
            ArtefactVersion.version_no < link.version.version_no,
        )
    ).unique()
    for other in older:
        other.state = "superseded"


def _extracted(env: JobEnv, version: ArtefactVersion) -> Extracted:
    if version.extracted_text is None and version.extract_error is None:
        result = extract(env.store.path_for(version.sha256), version.mime)
        version.extracted_text = result.text
        version.extract_error = result.error
        version.page_count = result.pages
        version.doc_metadata = result.metadata
    return Extracted(text=version.extracted_text or "", pages=version.page_count,
                     metadata=version.doc_metadata or {}, error=version.extract_error)


def verify_link(db: Session, link_id: uuid.UUID, env: JobEnv) -> VerificationRun | None:
    link = db.get(ArtefactLink, link_id)
    if link is None or link.state != "verifying":
        return None
    settings = env.settings
    version, slot = link.version, link.slot
    control = slot.control
    now = env.now()
    today = now.date()

    extracted = _extracted(env, version)
    scope = db.get(Scope, control.scope_id)
    org = db.get(Organization, scope.organization_id)
    av = (scan_file(env.store.path_for(version.sha256), settings.clamav_host, settings.clamav_port)
          if settings.clamav_host else None)
    duplicates = db.scalar(
        select(func.count()).select_from(ArtefactLink)
        .join(ArtefactVersion, ArtefactLink.version_id == ArtefactVersion.id)
        .where(ArtefactLink.slot_id == slot.id, ArtefactVersion.sha256 == version.sha256,
               ArtefactLink.id != link.id, ArtefactLink.state != "superseded")
    )
    found = find_dates(extracted.text)
    best = best_evidence_date(found, today)
    evidence_date = version.evidence_date or (best.value if best else None)
    ctx = RuleContext(
        filename=version.filename, mime=version.mime, extracted=extracted,
        org_names=[org.name, *(org.aliases or [])], freshness_days=slot.freshness_days,
        required_concepts=list(slot.required_concepts or []), today=today, supplied_date=version.evidence_date,
        evidence_date=evidence_date, found_dates=found, duplicate_in_slot=bool(duplicates), av_result=av,
    )

    run = VerificationRun(link_id=link.id, started_at=now, rules_version=RULES_VERSION)
    db.add(run)
    db.commit()
    outcomes = []
    for seq, code in enumerate(run_order(list(slot.rules or [])), start=1):
        rule = RULES[code]
        outcome = rule.check(ctx)
        db.add(RuleResult(run_id=run.id, seq=seq, code=code, name=rule.name, status=outcome.status,
                          weight=rule.weight, reason=outcome.reason, fix_hint=outcome.fix_hint,
                          excerpt=outcome.excerpt))
        db.commit()  # each result becomes visible to the polling UI straight away
        outcomes.append((rule, outcome))

    decision = decide(outcomes, settings.accept_threshold, settings.reject_threshold)
    run.finished_at = env.now()
    run.confidence = decision.confidence
    run.verdict = decision.verdict
    link.confidence = decision.confidence
    link.state = VERDICT_STATE[decision.verdict]
    link.evidence_date = evidence_date
    link.expires_on = (evidence_date + timedelta(days=slot.freshness_days)
                       if evidence_date and slot.freshness_days else None)
    if link.state == "accepted":
        supersede_older(db, link)
    record(db, SYSTEM, "evidence.verdict", "artefact_link", str(link.id),
           diff={"verdict": decision.verdict, "confidence": decision.confidence,
                 "control": control.code, "slot": slot.name})
    recompute_control(db, control, now, settings,
                      trigger=f"Evidence {version.filename} {VERDICT_WORD[decision.verdict]}")
    db.commit()
    return run
```

Replace `backend/src/assayr/job_handlers.py`:
```python
"""Import every module that registers a job handler (used by the worker and tests)."""

import assayr.scoring.jobs  # noqa: F401
import assayr.verification.engine  # noqa: F401
```

- [ ] **Step 4: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest -W error`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(verification): engine that runs rules, records results and applies the verdict" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Evidence upload, status and download API

**Files:**
- Create: `backend/src/assayr/catalogue/access.py`, `backend/src/assayr/evidence/schemas.py`, `backend/src/assayr/evidence/router.py`
- Modify: `backend/src/assayr/catalogue/router.py` (use `edit_rights`), `backend/src/assayr/main.py`
- Test: `backend/tests/test_evidence_api.py`

**Interfaces:**
- Consumes: `resolve_scope`, `_get_control` (`assayr.catalogue.router`), `current_user`, `require`, `actor_for`, `get_clock` (Phase 0), `BlobStore`, `TooLargeError`, `safe_filename` (Task 1), `sniff` (Task 2), `run_order` (Task 3), `recompute_control` (Task 5), `enqueue` (Task 6).
- Produces: `EditRights(all: bool, own: bool)` with `.any`; `edit_rights(user, scope_id, owner_id) -> EditRights`; schemas `RuleResultOut`, `LinkOut`, `link_out(db, link) -> LinkOut`; routes `POST /api/v1/controls/{code}/slots/{slot_id}/artefacts` (multipart fields `file`, optional `title`, `evidence_date`, `artefact_id`; 202 → `LinkOut`), `GET /api/v1/artefact-links/{link_id}` → `LinkOut`, `GET /api/v1/artefact-versions/{version_id}/download`. `LinkOut` = `{id, state, confidence, evidence_date, expires_on, slot_id, slot_name, control_code, control_title, artefact_id, version_id, version_no, filename, size, mime, uploaded_at, uploaded_by, decided_by, decision_reason, rules_planned, rules: [{seq, code, name, status, reason, fix_hint, excerpt}], text_preview}`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_evidence_api.py`:
```python
from datetime import timedelta

from sqlalchemy import select

from assayr.audit.models import AuditLog
from assayr.catalogue.models import Control
from tests.conftest import create_user, sign_in
from tests.evidence_helpers import policy_text, run_jobs
from tests.fixtures import make_pdf


def slot_url(db, code="A.5.1", index=0):
    control = db.scalar(select(Control).where(Control.code == code))
    return control, f"/api/v1/controls/{code}/slots/{control.slots[index].id}/artefacts"


def pdf_file(clock, name="policy.pdf"):
    return {"file": (name, make_pdf(policy_text(clock().date()).split("\n")), "application/pdf")}


def manager(client, db):
    user = create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")
    return user


def test_upload_then_verification_result(client, db, seeded, clock, app):
    manager(client, db)
    _, url = slot_url(db)
    response = client.post(url, files=pdf_file(clock))
    assert response.status_code == 202
    link = response.json()
    assert (link["state"], link["filename"], link["version_no"], link["uploaded_by"]) == (
        "verifying", "policy.pdf", 1, "Sana Malik")
    assert link["rules"] == [] and link["rules_planned"] > 0
    assert run_jobs(app) == 1
    done = client.get(f"/api/v1/artefact-links/{link['id']}").json()
    assert done["state"] == "accepted" and len(done["rules"]) == done["rules_planned"]
    assert "Information Security Policy" in done["text_preview"]
    assert db.scalar(select(AuditLog).where(AuditLog.action == "evidence.upload")).diff["filename"] == "policy.pdf"


def test_upload_filename_is_sanitised(client, db, seeded, clock):
    manager(client, db)
    _, url = slot_url(db)
    response = client.post(url, files=pdf_file(clock, name="..\\..\\evil<1>.pdf"))
    assert response.json()["filename"] == "evil1.pdf"


def test_upload_of_disguised_executable_is_rejected(client, db, seeded, app):
    manager(client, db)
    _, url = slot_url(db)
    link = client.post(url, files={"file": ("invoice.pdf", b"MZ\x90\x00 not a pdf", "application/pdf")}).json()
    assert link["mime"] is None
    run_jobs(app)
    done = client.get(f"/api/v1/artefact-links/{link['id']}").json()
    assert done["state"] == "rejected"
    assert done["rules"][0]["code"] == "V-FMT" and done["rules"][0]["status"] == "fail"


def test_upload_over_the_size_limit_is_refused(app, client, db, seeded, clock):
    app.state.settings = app.state.settings.model_copy(update={"max_upload_mb": 0})
    manager(client, db)
    _, url = slot_url(db)
    response = client.post(url, files=pdf_file(clock))
    assert response.status_code == 413
    assert response.json() == {"detail": "The file is larger than the 0 MB limit."}
    assert [p for p in app.state.store.root.rglob("*") if p.is_file()] == []


def test_future_evidence_date_is_refused(client, db, seeded, clock):
    manager(client, db)
    _, url = slot_url(db)
    response = client.post(
        url, files=pdf_file(clock), data={"evidence_date": (clock().date() + timedelta(days=1)).isoformat()}
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "The evidence date can't be in the future."}


def test_control_owner_uploads_only_to_their_own_controls(client, db, seeded, clock):
    owner = create_user(db, "bilal@acme.com", roles=(("control_owner", None),))
    control, url = slot_url(db, "A.8.13")
    control.owner_id = owner.id
    db.commit()
    sign_in(client, "bilal@acme.com")
    assert client.post(url, files=pdf_file(clock)).status_code == 202
    _, other = slot_url(db, "A.5.1")
    assert client.post(other, files=pdf_file(clock)).status_code == 403


def test_slot_must_belong_to_the_control(client, db, seeded, clock):
    manager(client, db)
    a51, _ = slot_url(db, "A.5.1")
    wrong = f"/api/v1/controls/A.8.13/slots/{a51.slots[0].id}/artefacts"
    response = client.post(wrong, files=pdf_file(clock))
    assert response.status_code == 404 and response.json() == {"detail": "Evidence slot not found."}


def test_viewer_cannot_upload(client, db, seeded, clock):
    create_user(db, "viewer@acme.com", roles=(("viewer", None),))
    sign_in(client, "viewer@acme.com")
    _, url = slot_url(db)
    assert client.post(url, files=pdf_file(clock)).status_code == 403


def test_new_version_of_an_artefact(client, db, seeded, clock, app):
    manager(client, db)
    _, url = slot_url(db)
    first = client.post(url, files=pdf_file(clock)).json()
    second = client.post(url, files=pdf_file(clock, "policy-v2.pdf"), data={"artefact_id": first["artefact_id"]}).json()
    assert (second["artefact_id"], second["version_no"]) == (first["artefact_id"], 2)


def test_download_is_an_attachment_and_is_audited(client, db, seeded, clock):
    manager(client, db)
    _, url = slot_url(db)
    link = client.post(url, files=pdf_file(clock)).json()
    response = client.get(f"/api/v1/artefact-versions/{link['version_id']}/download")
    assert response.status_code == 200 and response.content.startswith(b"%PDF-")
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-disposition"].startswith("attachment")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert db.scalar(select(AuditLog).where(AuditLog.action == "evidence.download")) is not None


def test_upload_requires_csrf(client, db, seeded, clock):
    manager(client, db)
    client.headers.pop("X-CSRF-Token")
    _, url = slot_url(db)
    assert client.post(url, files=pdf_file(clock)).status_code == 403
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_evidence_api.py`
Expected: FAIL — 404/405 responses (routes don't exist).

- [ ] **Step 3: Implement shared edit rights and refactor the control PATCH**

`backend/src/assayr/catalogue/access.py`:
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


def edit_rights(user: User, scope_id: uuid.UUID, owner_id: uuid.UUID | None) -> EditRights:
    """`all`: may edit any control in the scope. `own`: may edit this control because they own it."""
    pairs = [(a.role, a.scope_id) for a in user.role_assignments]
    return EditRights(
        all=grant_for(pairs, Perm.CONTROLS_WRITE).allows(scope_id),
        own=grant_for(pairs, Perm.CONTROLS_WRITE_OWN).allows(scope_id) and owner_id == user.id,
    )
```

In `backend/src/assayr/catalogue/router.py` `update_control`, replace the block computing `pairs`, `can_write_all`, `can_write_own` and the two permission checks with:
```python
    rights = edit_rights(user, scope.id, control.owner_id)
    if not rights.any:
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    fields = body.model_fields_set
    if "owner_id" in fields and not rights.all:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an ISMS manager can change the owner.")
```
and import `from assayr.catalogue.access import edit_rights` (remove the now-unused `grant_for` import if ruff reports it).

- [ ] **Step 4: Implement schemas and routes**

`backend/src/assayr/evidence/schemas.py`:
```python
import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.evidence.models import ArtefactLink, VerificationRun
from assayr.identity.models import User
from assayr.verification.rules import run_order

TEXT_PREVIEW_CHARS = 4000


class RuleResultOut(BaseModel):
    seq: int
    code: str
    name: str
    status: str
    reason: str
    fix_hint: str | None
    excerpt: str | None


class LinkOut(BaseModel):
    id: uuid.UUID
    state: str
    confidence: float | None
    evidence_date: date | None
    expires_on: date | None
    slot_id: uuid.UUID
    slot_name: str
    control_code: str
    control_title: str
    artefact_id: uuid.UUID
    version_id: uuid.UUID
    version_no: int
    filename: str
    size: int
    mime: str | None
    uploaded_at: datetime
    uploaded_by: str | None
    decided_by: str | None
    decision_reason: str | None
    rules_planned: int
    rules: list[RuleResultOut]
    text_preview: str | None


class ReviewItemOut(BaseModel):
    link_id: uuid.UUID
    control_code: str
    control_title: str
    slot_name: str
    filename: str
    confidence: float | None
    uploaded_by: str | None
    uploaded_at: datetime


class DecisionIn(BaseModel):
    decision: Literal["accept", "reject"]
    reason: str | None = Field(default=None, max_length=2000)


def latest_run(db: Session, link: ArtefactLink) -> VerificationRun | None:
    return db.scalar(
        select(VerificationRun).where(VerificationRun.link_id == link.id)
        .order_by(VerificationRun.started_at.desc()).limit(1)
    )


def _name(db: Session, user_id: uuid.UUID | None) -> str | None:
    user = db.get(User, user_id) if user_id else None
    return user.full_name if user else None


def link_out(db: Session, link: ArtefactLink) -> LinkOut:
    version, slot = link.version, link.slot
    run = latest_run(db, link)
    text = version.extracted_text
    return LinkOut(
        id=link.id, state=link.state, confidence=link.confidence, evidence_date=link.evidence_date,
        expires_on=link.expires_on, slot_id=slot.id, slot_name=slot.name, control_code=slot.control.code,
        control_title=slot.control.title, artefact_id=version.artefact_id, version_id=version.id,
        version_no=version.version_no, filename=version.filename, size=version.size, mime=version.mime,
        uploaded_at=version.created_at, uploaded_by=_name(db, version.uploaded_by_id),
        decided_by=_name(db, link.decided_by_id), decision_reason=link.decision_reason,
        rules_planned=len(run_order(list(slot.rules or []))),
        rules=[RuleResultOut.model_validate(r, from_attributes=True) for r in (run.results if run else [])],
        text_preview=text[:TEXT_PREVIEW_CHARS] if text else None,
    )


def review_item(db: Session, link: ArtefactLink) -> ReviewItemOut:
    return ReviewItemOut(
        link_id=link.id, control_code=link.slot.control.code, control_title=link.slot.control.title,
        slot_name=link.slot.name, filename=link.version.filename, confidence=link.confidence,
        uploaded_by=_name(db, link.version.uploaded_by_id), uploaded_at=link.version.created_at,
    )
```

`backend/src/assayr/evidence/router.py`:
```python
import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.catalogue.access import edit_rights
from assayr.catalogue.models import EvidenceSlot
from assayr.catalogue.router import FORBIDDEN, _get_control, resolve_scope
from assayr.db import get_session
from assayr.evidence.extract import sniff
from assayr.evidence.models import Artefact, ArtefactLink, ArtefactVersion
from assayr.evidence.schemas import LinkOut, link_out
from assayr.identity.deps import actor_for, current_user, get_clock, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm
from assayr.jobs import enqueue
from assayr.scoring.service import recompute_control
from assayr.storage import TooLargeError, safe_filename

router = APIRouter(tags=["evidence"])
NOT_FOUND = "Evidence not found."
HEAD_BYTES = 8192


@router.post("/controls/{code}/slots/{slot_id}/artefacts", response_model=LinkOut, status_code=202)
def upload_evidence(
    code: str,
    slot_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    title: str | None = Form(None, max_length=300),
    evidence_date: date | None = Form(None),
    artefact_id: uuid.UUID | None = Form(None),
    scope_id: uuid.UUID | None = None,
    user: User = Depends(current_user),
    read_grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> LinkOut:
    settings = request.app.state.settings
    store = request.app.state.store
    now = get_clock(request)()
    scope = resolve_scope(db, scope_id, read_grant)
    control = _get_control(db, scope, code)
    if not edit_rights(user, scope.id, control.owner_id).any:
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    slot = db.get(EvidenceSlot, slot_id)
    if slot is None or slot.control_id != control.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence slot not found.")
    if evidence_date and evidence_date > now.date():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The evidence date can't be in the future.")
    if artefact_id is not None:
        artefact = db.get(Artefact, artefact_id)
        if artefact is None or artefact.scope_id != scope.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Artefact not found.")
    head = file.file.read(HEAD_BYTES)
    file.file.seek(0)
    try:
        blob = store.put(file.file, settings.max_upload_mb * 1024 * 1024)
    except TooLargeError as exc:
        raise HTTPException(413, f"The file is larger than the {settings.max_upload_mb} MB limit.") from exc
    filename = safe_filename(file.filename or "")
    if artefact_id is None:
        artefact = Artefact(scope_id=scope.id, title=(title or filename)[:300], uploaded_by_id=user.id)
        db.add(artefact)
    version = ArtefactVersion(
        version_no=max((v.version_no for v in artefact.versions), default=0) + 1,
        sha256=blob.sha256, size=blob.size, filename=filename, mime=sniff(head, filename),
        evidence_date=evidence_date, uploaded_by_id=user.id, created_at=now,
    )
    artefact.versions.append(version)
    db.flush()
    link = ArtefactLink(version_id=version.id, slot_id=slot.id, state="verifying", created_at=now)
    db.add(link)
    db.flush()
    enqueue(db, "verify_link", {"link_id": str(link.id)}, now)
    record(db, actor_for(request, user), "evidence.upload", "artefact_link", str(link.id),
           diff={"control": control.code, "slot": slot.name, "filename": filename,
                 "sha256": blob.sha256, "size": blob.size})
    recompute_control(db, control, now, settings, trigger=f"Evidence uploaded: {filename}")
    db.commit()
    db.refresh(link)
    return link_out(db, link)


@router.get("/artefact-links/{link_id}", response_model=LinkOut)
def get_link(
    link_id: uuid.UUID,
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> LinkOut:
    link = db.get(ArtefactLink, link_id)
    if link is None or not grant.allows(link.slot.control.scope_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return link_out(db, link)


@router.get("/artefact-versions/{version_id}/download")
def download_version(
    version_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> FileResponse:
    version = db.get(ArtefactVersion, version_id)
    if version is None or not grant.allows(version.artefact.scope_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    path = request.app.state.store.path_for(version.sha256)
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "The stored file is missing. Ask an administrator to check the evidence store.")
    record(db, actor_for(request, user), "evidence.download", "artefact_version", str(version.id),
           diff={"filename": version.filename})
    db.commit()
    return FileResponse(path, filename=version.filename, media_type="application/octet-stream",
                        content_disposition_type="attachment", headers={"X-Content-Type-Options": "nosniff"})
```

In `backend/src/assayr/main.py` add `from assayr.evidence.router import router as evidence_router` and `app.include_router(evidence_router, prefix="/api/v1")`.

- [ ] **Step 5: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest -W error`
Expected: all pass (existing `test_controls_api.py` still passes after the `edit_rights` refactor).

- [ ] **Step 6: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(evidence): upload, verification status and download API" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Review queue and reviewer decisions

**Files:**
- Modify: `backend/src/assayr/identity/rbac.py`, `backend/tests/test_rbac.py`, `backend/src/assayr/evidence/router.py`
- Test: `backend/tests/test_review_api.py`

**Interfaces:**
- Consumes: `link_out`, `review_item`, `latest_run`, `DecisionIn`, `ReviewItemOut` (Task 8), `supersede_older` (Task 7), `recompute_control` (Task 5).
- Produces: `Perm.EVIDENCE_REVIEW = "evidence:review"` (granted to `isms_manager`); `GET /api/v1/review-queue` → `ReviewItemOut[]`; `POST /api/v1/artefact-links/{link_id}/decision` (`{decision, reason}`) → `LinkOut`.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_rbac.py` replace the expected list in `test_permissions_are_a_sorted_union` with:
```python
        "audit_log:read",
        "controls:read",
        "controls:write",
        "evidence:review",
        "settings:manage",
        "users:manage",
```

`backend/tests/test_review_api.py`:
```python
from fastapi.testclient import TestClient
from sqlalchemy import select

from assayr.audit.models import AuditLog
from assayr.catalogue.models import Control
from tests.conftest import create_user, sign_in
from tests.evidence_helpers import policy_text, run_jobs
from tests.fixtures import PNG_BYTES, make_pdf


def screenshot_in_review(app, db, uploader_email="bilal@acme.com", file=("shot.png", PNG_BYTES, "image/png")):
    """Upload a file (a screenshot always lands in review) as a manager and return the link id."""
    create_user(db, uploader_email, full_name="Bilal Khan")
    control = db.scalar(select(Control).where(Control.code == "A.5.1"))
    with TestClient(app) as uploader:
        sign_in(uploader, uploader_email)
        url = f"/api/v1/controls/A.5.1/slots/{control.slots[0].id}/artefacts"
        link = uploader.post(url, files={"file": file}).json()
    run_jobs(app)
    return link["id"]


def reviewer(client, db):
    create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")


def test_queue_lists_items_waiting_for_review(app, client, db, seeded):
    link_id = screenshot_in_review(app, db)
    reviewer(client, db)
    queue = client.get("/api/v1/review-queue").json()
    assert [(i["link_id"], i["control_code"], i["uploaded_by"]) for i in queue] == [(link_id, "A.5.1", "Bilal Khan")]


def test_accepting_with_a_reason_updates_the_control(app, client, db, seeded):
    link_id = screenshot_in_review(app, db)
    reviewer(client, db)
    response = client.post(f"/api/v1/artefact-links/{link_id}/decision",
                           json={"decision": "accept", "reason": "Screenshot shows the approved policy page."})
    assert response.status_code == 200
    body = response.json()
    assert (body["state"], body["decided_by"]) == ("accepted", "Sana Malik")
    assert client.get("/api/v1/review-queue").json() == []
    entry = db.scalar(select(AuditLog).where(AuditLog.action == "evidence.decision"))
    assert entry.diff["state"] == ["in_review", "accepted"]


def test_uploader_cannot_review_their_own_evidence(app, client, db, seeded):
    link_id = screenshot_in_review(app, db, uploader_email="sana@acme.com")
    sign_in(client, "sana@acme.com")
    response = client.post(f"/api/v1/artefact-links/{link_id}/decision", json={"decision": "accept", "reason": "ok"})
    assert response.status_code == 403
    assert response.json() == {"detail": "You can't review evidence you uploaded. Ask another reviewer."}


def test_reject_needs_a_reason(app, client, db, seeded):
    link_id = screenshot_in_review(app, db)
    reviewer(client, db)
    response = client.post(f"/api/v1/artefact-links/{link_id}/decision", json={"decision": "reject"})
    assert response.status_code == 422
    assert response.json() == {"detail": "Give a reason so the uploader knows what to fix."}


def test_accepting_evidence_no_check_could_read_needs_a_reason(app, client, db, seeded):
    link_id = screenshot_in_review(app, db)
    reviewer(client, db)
    response = client.post(f"/api/v1/artefact-links/{link_id}/decision", json={"decision": "accept"})
    assert response.status_code == 422
    assert response.json() == {"detail": "None of the content checks could run on this file. Say what you checked."}


def test_accepting_evidence_with_failed_checks_needs_a_reason(app, client, db, seeded, clock):
    draft = make_pdf(policy_text(clock().date(), approved=False).split("
"))
    link_id = screenshot_in_review(app, db, file=("draft.pdf", draft, "application/pdf"))
    reviewer(client, db)
    response = client.post(f"/api/v1/artefact-links/{link_id}/decision", json={"decision": "accept"})
    assert response.status_code == 422
    assert response.json() == {"detail": "Some checks failed or raised warnings. Give a reason for accepting anyway."}


def test_final_decisions_cannot_be_repeated(app, client, db, seeded):
    link_id = screenshot_in_review(app, db)
    reviewer(client, db)
    url = f"/api/v1/artefact-links/{link_id}/decision"
    client.post(url, json={"decision": "accept", "reason": "ok"})
    response = client.post(url, json={"decision": "reject", "reason": "changed my mind"})
    assert response.status_code == 409


def test_reviewing_needs_the_reviewer_permission(app, client, db, seeded):
    link_id = screenshot_in_review(app, db)
    create_user(db, "viewer@acme.com", roles=(("viewer", None),))
    sign_in(client, "viewer@acme.com")
    assert client.get("/api/v1/review-queue").status_code == 403
    url = f"/api/v1/artefact-links/{link_id}/decision"
    assert client.post(url, json={"decision": "accept", "reason": "x"}).status_code == 403
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_review_api.py tests/test_rbac.py`
Expected: FAIL — 404s and the rbac union mismatch.

- [ ] **Step 3: Implement**

In `backend/src/assayr/identity/rbac.py` add `EVIDENCE_REVIEW = "evidence:review"` to `Perm`, and change the ISMS manager entry to:
```python
    Role.ISMS_MANAGER: frozenset({Perm.CONTROLS_READ, Perm.CONTROLS_WRITE, Perm.AUDIT_LOG_READ, Perm.EVIDENCE_REVIEW}),
```

Append to `backend/src/assayr/evidence/router.py` (imports: `from sqlalchemy import select`, `from assayr.catalogue.models import Control`, `from assayr.evidence.schemas import DecisionIn, ReviewItemOut, latest_run, review_item`, `from assayr.verification.engine import supersede_older`):
```python
@router.get("/review-queue", response_model=list[ReviewItemOut])
def review_queue(
    grant: Grant = Depends(require(Perm.EVIDENCE_REVIEW)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> list[ReviewItemOut]:
    scope = resolve_scope(db, scope_id, grant)
    links = db.scalars(
        select(ArtefactLink)
        .join(EvidenceSlot, ArtefactLink.slot_id == EvidenceSlot.id)
        .join(Control, EvidenceSlot.control_id == Control.id)
        .where(Control.scope_id == scope.id, ArtefactLink.state == "in_review")
        .order_by(ArtefactLink.created_at)
    ).unique()
    return [review_item(db, link) for link in links]


_DECISION_FROM = {"accept": {"in_review", "rejected"}, "reject": {"in_review"}}


@router.post("/artefact-links/{link_id}/decision", response_model=LinkOut)
def decide_link(
    link_id: uuid.UUID,
    body: DecisionIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.EVIDENCE_REVIEW)),
    db: Session = Depends(get_session),
) -> LinkOut:
    link = db.get(ArtefactLink, link_id)
    if link is None or not grant.allows(link.slot.control.scope_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    if link.version.uploaded_by_id == user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can't review evidence you uploaded. Ask another reviewer.")
    if link.state not in _DECISION_FROM[body.decision]:
        raise HTTPException(status.HTTP_409_CONFLICT, "This evidence already has a final decision.")
    reason = (body.reason or "").strip()
    run = latest_run(db, link)
    flagged = run is not None and any(r.status in ("fail", "warn") for r in run.results)
    unchecked = run is None or run.confidence is None
    if body.decision == "reject" and not reason:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Give a reason so the uploader knows what to fix.")
    if body.decision == "accept" and not reason:
        if flagged or link.state == "rejected":
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                                "Some checks failed or raised warnings. Give a reason for accepting anyway.")
        if unchecked:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                                "None of the content checks could run on this file. Say what you checked.")
    now = get_clock(request)()
    before = link.state
    link.state = "accepted" if body.decision == "accept" else "rejected"
    link.decided_by_id = user.id
    link.decided_at = now
    link.decision_reason = reason or None
    if link.state == "accepted":
        supersede_older(db, link)
    record(db, actor_for(request, user), "evidence.decision", "artefact_link", str(link.id),
           diff={"state": [before, link.state]}, reason=reason or None)
    verb = "accepted" if link.state == "accepted" else "rejected"
    recompute_control(db, link.slot.control, now, request.app.state.settings,
                      trigger=f"Reviewer {verb} {link.version.filename}")
    db.commit()
    return link_out(db, link)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest -W error`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(evidence): review queue and reviewer decisions with separation of duties" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Slot states on control detail, attestation and readiness API

**Files:**
- Modify: `backend/src/assayr/catalogue/schemas.py`, `backend/src/assayr/catalogue/router.py`, `backend/src/assayr/main.py`
- Create: `backend/src/assayr/scoring/router.py`
- Test: `backend/tests/test_scoring_api.py`

**Interfaces:**
- Consumes: `slot_views`, `latest_attestation`, `attestation_days`, `recompute_control`, `weighted_readiness`, `scope_has_evidence`, `SlotView` (Task 5), `edit_rights` (Task 8).
- Produces: `SlotOut` gains `state: str`, `artefact: SlotArtefactOut | None` (`{link_id, version_id, filename, state, confidence, evidence_date, expires_on}`); `ControlSummaryOut` gains `score: float | None`; `ControlDetailOut` gains `attestation: AttestationOut | None` (`{attested_at, valid_until, by, statement}`); `control_detail(db, control, settings, now) -> ControlDetailOut` in `catalogue.router`; `POST /api/v1/controls/{code}/attest` (`{statement}`) → `ControlDetailOut`; `GET /api/v1/readiness` → `{scope_id, readiness: float | None, status_counts: {status: n}, by_theme: {theme: float | None}, trend: [{date, readiness}]}`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_scoring_api.py`:
```python
from sqlalchemy import select

from assayr.catalogue.models import Control
from assayr.db import utcnow
from assayr.scoring.service import recompute_scope
from tests.conftest import create_user, sign_in
from tests.evidence_helpers import add_link


def a813(db):
    return db.scalar(select(Control).where(Control.code == "A.8.13"))


def manager(client, db):
    create_user(db, "sana@acme.com", full_name="Sana Malik")
    sign_in(client, "sana@acme.com")


def test_detail_shows_slot_states_and_latest_evidence(app, client, db, seeded):
    manager(client, db)
    detail = client.get("/api/v1/controls/A.8.13").json()
    assert [s["state"] for s in detail["slots"]] == ["missing", "missing", "missing"]
    assert detail["attestation"] is None and detail["score"] is None
    control = a813(db)
    add_link(db, app.state.store, control.slots[0], scope_id=seeded.id, evidence_date=utcnow().date(),
             filename="backup-policy.pdf")
    db.commit()
    slot = client.get("/api/v1/controls/A.8.13").json()["slots"][0]
    assert slot["state"] == "verified" and slot["artefact"]["filename"] == "backup-policy.pdf"


def test_owner_attests_and_full_evidence_makes_the_control_compliant(app, client, db, seeded):
    owner = create_user(db, "bilal@acme.com", roles=(("control_owner", None),), full_name="Bilal Khan")
    control = a813(db)
    control.owner_id = owner.id
    for slot in control.slots:
        add_link(db, app.state.store, slot, scope_id=seeded.id, evidence_date=utcnow().date())
    db.commit()
    sign_in(client, "bilal@acme.com")
    response = client.post("/api/v1/controls/A.8.13/attest", json={"statement": "Backups run nightly as described."})
    assert response.status_code == 200
    detail = response.json()
    assert (detail["status"], detail["score"]) == ("compliant", 100.0)
    assert detail["attestation"]["by"] == "Bilal Khan"


def test_only_the_owner_or_a_manager_can_attest(app, client, db, seeded):
    create_user(db, "other@acme.com", roles=(("control_owner", None),))
    sign_in(client, "other@acme.com")
    response = client.post("/api/v1/controls/A.8.13/attest", json={"statement": "Not mine."})
    assert response.status_code == 403
    assert response.json() == {"detail": "Only the control owner or an ISMS manager can attest."}


def test_readiness_appears_once_evidence_exists(app, client, db, seeded):
    manager(client, db)
    empty = client.get("/api/v1/readiness").json()
    assert empty["readiness"] is None and empty["status_counts"] == {"not_started": 93}
    control = a813(db)
    add_link(db, app.state.store, control.slots[0], scope_id=seeded.id, evidence_date=utcnow().date())
    recompute_scope(db, seeded.id, utcnow(), app.state.settings)
    db.commit()
    body = client.get("/api/v1/readiness").json()
    assert body["readiness"] == round(30.0 / 93, 1)
    assert body["by_theme"]["Technological"] == round(30.0 / 34, 1)
    assert body["by_theme"]["People"] == 0.0
    assert len(body["trend"]) == 1 and body["status_counts"]["in_progress"] == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest tests/test_scoring_api.py`
Expected: FAIL — `KeyError: 'state'` / 404 on new routes.

- [ ] **Step 3: Implement schemas**

In `backend/src/assayr/catalogue/schemas.py`:
- add `from datetime import date, datetime` and `from assayr.scoring.models import Attestation` and `from assayr.scoring.service import SlotView`;
- add before `SlotOut`:
```python
class SlotArtefactOut(BaseModel):
    link_id: uuid.UUID
    version_id: uuid.UUID
    filename: str
    state: str
    confidence: float | None
    evidence_date: date | None
    expires_on: date | None


class AttestationOut(BaseModel):
    attested_at: datetime
    valid_until: datetime
    by: str | None
    statement: str
```
- add to `SlotOut`: `state: str = "missing"` and `artefact: SlotArtefactOut | None = None`;
- add to `ControlSummaryOut`: `score: float | None`;
- add to `ControlDetailOut`: `attestation: AttestationOut | None = None`;
- in `summary_out(...)` pass `score=control.score`;
- replace `detail_out` with:
```python
def detail_out(
    control: Control,
    views: list[SlotView] | None = None,
    attestation: Attestation | None = None,
    attested_by: str | None = None,
) -> ControlDetailOut:
    by_slot = {v.slot_id: v for v in (views or [])}

    def slot_out(s) -> SlotOut:
        view = by_slot.get(s.id)
        link = view.link if view else None
        return SlotOut(
            id=s.id, name=s.name, evidence_type=s.evidence_type, required=s.required,
            freshness_days=s.freshness_days, rules=s.rules, state=view.state if view else "missing",
            artefact=SlotArtefactOut(
                link_id=link.id, version_id=link.version_id, filename=link.version.filename, state=link.state,
                confidence=link.confidence, evidence_date=link.evidence_date, expires_on=link.expires_on,
            ) if link else None,
        )

    return ControlDetailOut(
        **summary_out(control).model_dump(),
        description=control.description,
        review_frequency=control.review_frequency,
        default_owner_role=control.default_owner_role,
        implementation_text=control.implementation_text,
        slots=[slot_out(s) for s in control.slots],
        requirements=[RequirementRefOut(ref=r.ref, title=r.title) for r in control.requirements],
        attestation=AttestationOut(attested_at=attestation.attested_at, valid_until=attestation.valid_until,
                                   by=attested_by, statement=attestation.statement) if attestation else None,
    )
```

- [ ] **Step 4: Implement routes**

In `backend/src/assayr/catalogue/router.py` add (imports `from datetime import datetime`, `from assayr.config import Settings`, `from assayr.identity.deps import get_clock`, `from assayr.scoring.service import latest_attestation, slot_views`):
```python
def control_detail(db: Session, control: Control, settings: Settings, now: datetime) -> ControlDetailOut:
    attestation = latest_attestation(db, control)
    attested_by = db.get(User, attestation.user_id) if attestation and attestation.user_id else None
    return detail_out(control, slot_views(db, control, now.date(), settings), attestation,
                      attested_by.full_name if attested_by else None)
```
Change `get_control` to take `request: Request` and return `control_detail(db, control, request.app.state.settings, get_clock(request)())`; change the final `return detail_out(control)` in `update_control` to `return control_detail(db, control, request.app.state.settings, get_clock(request)())`.

`backend/src/assayr/scoring/router.py`:
```python
import uuid
from collections import Counter
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.catalogue.access import edit_rights
from assayr.catalogue.models import Control
from assayr.catalogue.router import _get_control, control_detail, resolve_scope
from assayr.catalogue.schemas import ControlDetailOut
from assayr.db import get_session
from assayr.identity.deps import actor_for, current_user, get_clock, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm
from assayr.scoring.models import Attestation, ScoreSnapshot
from assayr.scoring.service import attestation_days, recompute_control, scope_has_evidence, weighted_readiness

router = APIRouter(tags=["scoring"])
TREND_DAYS = 90


class AttestIn(BaseModel):
    statement: str = Field(min_length=1, max_length=2000)


class TrendPoint(BaseModel):
    date: date
    readiness: float


class ReadinessOut(BaseModel):
    scope_id: uuid.UUID
    readiness: float | None
    status_counts: dict[str, int]
    by_theme: dict[str, float | None]
    trend: list[TrendPoint]


@router.get("/readiness", response_model=ReadinessOut)
def readiness(
    request: Request,
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> ReadinessOut:
    scope = resolve_scope(db, scope_id, grant)
    controls = list(db.scalars(select(Control).where(Control.scope_id == scope.id)))
    has_evidence = scope_has_evidence(db, scope.id)
    themes: dict[str, list[Control]] = {}
    for control in controls:
        themes.setdefault(control.theme or "Other", []).append(control)
    since = get_clock(request)() - timedelta(days=TREND_DAYS)
    snapshots = db.scalars(
        select(ScoreSnapshot).where(ScoreSnapshot.scope_id == scope.id, ScoreSnapshot.taken_at >= since)
        .order_by(ScoreSnapshot.taken_at)
    )
    return ReadinessOut(
        scope_id=scope.id,
        readiness=weighted_readiness(controls) if has_evidence else None,
        status_counts=dict(Counter(c.status for c in controls)),
        by_theme={theme: weighted_readiness(group) if has_evidence else None for theme, group in themes.items()},
        trend=[TrendPoint(date=s.taken_at.date(), readiness=s.readiness) for s in snapshots],
    )


@router.post("/controls/{code}/attest", response_model=ControlDetailOut)
def attest(
    code: str,
    body: AttestIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> ControlDetailOut:
    scope = resolve_scope(db, scope_id, grant)
    control = _get_control(db, scope, code)
    if not (edit_rights(user, scope.id, control.owner_id).all or control.owner_id == user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the control owner or an ISMS manager can attest.")
    settings = request.app.state.settings
    now = get_clock(request)()
    valid_until = now + timedelta(days=attestation_days(control))
    db.add(Attestation(control_id=control.id, user_id=user.id, statement=body.statement.strip(),
                       attested_at=now, valid_until=valid_until))
    db.flush()
    record(db, actor_for(request, user), "control.attest", "control", control.code,
           diff={"valid_until": [None, valid_until.isoformat()]})
    recompute_control(db, control, now, settings, trigger="Owner attested")
    db.commit()
    return control_detail(db, control, settings, now)
```

In `backend/src/assayr/main.py` add `from assayr.scoring.router import router as scoring_router` and `app.include_router(scoring_router, prefix="/api/v1")`.

- [ ] **Step 5: Run to verify pass**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd backend && uv run pytest -W error`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff format . && uv run ruff check --fix .) && git add -A && git commit -m "feat(scoring): slot states on control detail, attestation and readiness API" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Frontend — upload with live verification on the control page

**Files:**
- Modify: `frontend/src/api/client.ts`, `frontend/src/api/client.test.ts`, `frontend/src/api/types.ts`, `frontend/src/components/StatusPill.tsx`, `frontend/src/components/icons.tsx`, `frontend/src/pages/ControlDetail.tsx`, `frontend/src/pages/ControlDetail.test.tsx`, `frontend/src/pages/Controls.test.tsx`
- Create: `frontend/src/api/evidence.ts`, `frontend/src/lib/format.ts`, `frontend/src/lib/format.test.ts`, `frontend/src/components/SlotStatePill.tsx`, `frontend/src/components/VerificationPanel.tsx`
- Test: `frontend/src/pages/ControlDetail.test.tsx` (new upload test), `frontend/src/lib/format.test.ts`

**Interfaces:**
- Consumes: backend Task 8 and Task 10 shapes.
- Produces: types `SlotState`, `SlotArtefact`, `RuleResult`, `ArtefactLink`, `ReviewItem`, `Readiness`, `Attestation`; `EvidenceSlot` gains `state`, `artefact`; `ControlSummary` gains `score`; `ControlDetail` gains `attestation`; `uploadEvidence(code, slotId, file)`, `useLink(linkId)`, `useUploadEvidence(code)`, `useReviewQueue()`, `useDecision()`, `useAttest(code)`, `useReadiness()`; `formatDate(iso: string) -> string`; `StatusPill({ status, label? })`; `SlotStatePill({ state, artefactState? })`; `VerificationPanel({ linkId, onDone })`.

- [ ] **Step 1: Write the failing tests**

Append to `frontend/src/api/client.test.ts`:
```ts
test("FormData bodies keep the browser's multipart content type", async () => {
  const calls = mockApi({ "POST /controls/A.5.1/slots/s1/artefacts": () => json(202, { id: "l1" }) })
  const form = new FormData()
  form.set("file", new File(["x"], "a.pdf"))
  await api("/controls/A.5.1/slots/s1/artefacts", { method: "POST", body: form })
  expect(new Headers(calls[0].init.headers).has("Content-Type")).toBe(false)
})
```

`frontend/src/lib/format.test.ts`:
```ts
import { formatDate } from "./format"

test("dates read as day, short month, year", () => {
  expect(formatDate("2026-02-04")).toBe("4 Feb 2026")
  expect(formatDate("2026-10-07T09:30:00Z")).toBe("7 Oct 2026")
})
```

In `frontend/src/pages/Controls.test.tsx`, add `score: null` to the `row(...)` object. In `frontend/src/pages/ControlDetail.test.tsx`, make the `DETAIL` constant include `score: null, attestation: null` and give its slot `state: "missing", artefact: null`. Then append:
```tsx
test("uploading evidence shows the checks as they run and the verdict", async () => {
  document.cookie = "assayr_csrf=token-xyz; path=/"
  let linkPolls = 0
  let uploaded = false
  const rule = (seq: number, name: string) => ({
    seq, code: `V-${seq}`, name, status: "pass", reason: `${name} ok.`, fix_hint: null, excerpt: null,
  })
  const link = (state: string, rules: unknown[]) => ({
    id: "l1", state, confidence: state === "accepted" ? 1 : null, evidence_date: "2026-09-07",
    expires_on: "2026-10-08", slot_id: "s1", slot_name: "Backup policy", control_code: "A.8.13",
    control_title: "Information backup", artefact_id: "a1", version_id: "v1", version_no: 1,
    filename: "backup.pdf", size: 10, mime: "application/pdf", uploaded_at: "2026-10-07T09:00:00Z",
    uploaded_by: "Sana Malik", decided_by: null, decision_reason: null, rules_planned: 2, rules,
    text_preview: null,
  })
  const calls = mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /controls/A.8.13": () =>
      json(200, uploaded
        ? { ...DETAIL, slots: [{ ...DETAIL.slots[0], state: "verified", artefact: {
            link_id: "l1", version_id: "v1", filename: "backup.pdf", state: "accepted", confidence: 1,
            evidence_date: "2026-09-07", expires_on: "2026-10-08" } }] }
        : DETAIL),
    "POST /controls/A.8.13/slots/s1/artefacts": () => {
      uploaded = true
      return json(202, link("verifying", []))
    },
    "GET /artefact-links/l1": () => {
      linkPolls += 1
      return linkPolls === 1
        ? json(200, link("verifying", [rule(1, "File readable")]))
        : json(200, link("accepted", [rule(1, "File readable"), rule(2, "Document date")]))
    },
  })
  renderApp("/controls/A.8.13")
  const input = await screen.findByLabelText("Upload evidence for Backup policy")
  await userEvent.upload(input, new File(["%PDF-1.4"], "backup.pdf", { type: "application/pdf" }))
  expect(await screen.findByText("File readable")).toBeInTheDocument()
  expect(await screen.findByText(/Accepted\./, {}, { timeout: 3000 })).toBeInTheDocument()
  expect(await screen.findByText("Verified")).toBeInTheDocument()
  const post = calls.find((c) => c.method === "POST")!
  expect(post.init.body).toBeInstanceOf(FormData)
  expect(new Headers(post.init.headers).get("X-CSRF-Token")).toBe("token-xyz")
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd frontend && npx vitest run --testTimeout=10000`
Expected: FAIL — format module missing, FormData content-type test fails, upload control not found.

- [ ] **Step 3: Implement API helpers, types and format**

In `frontend/src/api/client.ts`, change the content-type line to:
```ts
  if (typeof init.body === "string" && !headers.has("Content-Type")) headers.set("Content-Type", "application/json")
```

Append to `frontend/src/api/types.ts` and extend existing interfaces:
```ts
export type SlotState = "verified" | "expiring" | "expired_grace" | "expired" | "pending" | "rejected" | "missing"
export interface SlotArtefact {
  link_id: string
  version_id: string
  filename: string
  state: string
  confidence: number | null
  evidence_date: string | null
  expires_on: string | null
}
export interface Attestation { attested_at: string; valid_until: string; by: string | null; statement: string }
export interface RuleResult {
  seq: number
  code: string
  name: string
  status: "pass" | "warn" | "fail" | "skipped"
  reason: string
  fix_hint: string | null
  excerpt: string | null
}
export interface ArtefactLink {
  id: string
  state: string
  confidence: number | null
  evidence_date: string | null
  expires_on: string | null
  slot_id: string
  slot_name: string
  control_code: string
  control_title: string
  artefact_id: string
  version_id: string
  version_no: number
  filename: string
  size: number
  mime: string | null
  uploaded_at: string
  uploaded_by: string | null
  decided_by: string | null
  decision_reason: string | null
  rules_planned: number
  rules: RuleResult[]
  text_preview: string | null
}
export interface ReviewItem {
  link_id: string
  control_code: string
  control_title: string
  slot_name: string
  filename: string
  confidence: number | null
  uploaded_by: string | null
  uploaded_at: string
}
export interface Readiness {
  scope_id: string
  readiness: number | null
  status_counts: Record<string, number>
  by_theme: Record<string, number | null>
  trend: { date: string; readiness: number }[]
}
```
and add `score: number | null` to `ControlSummary`, `state: SlotState; artefact: SlotArtefact | null` to `EvidenceSlot`, `attestation: Attestation | null` to `ControlDetail`.

`frontend/src/api/evidence.ts`:
```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"
import type { ArtefactLink, ControlDetail, Readiness, ReviewItem } from "./types"

export function uploadEvidence(code: string, slotId: string, file: File): Promise<ArtefactLink> {
  const form = new FormData()
  form.set("file", file)
  return api<ArtefactLink>(`/controls/${encodeURIComponent(code)}/slots/${slotId}/artefacts`, {
    method: "POST",
    body: form,
  })
}

export function useUploadEvidence(code: string) {
  return useMutation({ mutationFn: ({ slotId, file }: { slotId: string; file: File }) => uploadEvidence(code, slotId, file) })
}

export function useLink(linkId: string) {
  return useQuery({
    queryKey: ["link", linkId],
    queryFn: () => api<ArtefactLink>(`/artefact-links/${linkId}`),
    refetchInterval: (query) => (query.state.data?.state === "verifying" ? 800 : false),
  })
}

export function useReviewQueue() {
  return useQuery({ queryKey: ["review-queue"], queryFn: () => api<ReviewItem[]>("/review-queue") })
}

export function useDecision() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ linkId, decision, reason }: { linkId: string; decision: "accept" | "reject"; reason: string }) =>
      api<ArtefactLink>(`/artefact-links/${linkId}/decision`, {
        method: "POST",
        body: JSON.stringify({ decision, reason: reason.trim() || null }),
      }),
    onSuccess: (link) => {
      queryClient.setQueryData(["link", link.id], link)
      queryClient.invalidateQueries({ queryKey: ["review-queue"] })
      queryClient.invalidateQueries({ queryKey: ["control", link.control_code] })
      queryClient.invalidateQueries({ queryKey: ["readiness"] })
    },
  })
}

export function useAttest(code: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (statement: string) =>
      api<ControlDetail>(`/controls/${encodeURIComponent(code)}/attest`, {
        method: "POST",
        body: JSON.stringify({ statement }),
      }),
    onSuccess: (detail) => {
      queryClient.setQueryData(["control", code], detail)
      queryClient.invalidateQueries({ queryKey: ["readiness"] })
    },
  })
}

export function useReadiness() {
  return useQuery({ queryKey: ["readiness"], queryFn: () => api<Readiness>("/readiness") })
}
```

`frontend/src/lib/format.ts`:
```ts
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

/** "2026-02-04" or an ISO timestamp → "4 Feb 2026" (the calendar date as written, no timezone shift). */
export function formatDate(iso: string): string {
  const [year, month, day] = iso.slice(0, 10).split("-").map(Number)
  return `${day} ${MONTHS[month - 1]} ${year}`
}
```

- [ ] **Step 4: Implement components**

`frontend/src/components/StatusPill.tsx` — change the signature and label line:
```tsx
export function StatusPill({ status, label: override }: { status: string; label?: string }) {
  const known = status in STATUS_LABEL ? (status as ControlStatus) : null
  const label = override ?? (known ? STATUS_LABEL[known] : humanize(status))
```

Add to `PATHS` in `frontend/src/components/icons.tsx`:
```ts
  pass: "M5 12.5 9.5 17 19 7.5",
  warn: "M12 4 2.8 19.5h18.4zM12 10v4m0 3h.01",
  fail: "M6 6l12 12M18 6 6 18",
  skipped: "M5 12h14",
  upload: "M12 16V4m0 0-4.5 4.5M12 4l4.5 4.5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3",
```

`frontend/src/components/SlotStatePill.tsx`:
```tsx
import { StatusPill } from "./StatusPill"

const MAP: Record<string, [string, string]> = {
  verified: ["compliant", "Verified"],
  expiring: ["at_risk", "Expiring"],
  expired_grace: ["at_risk", "Expired, in grace period"],
  expired: ["non_compliant", "Expired"],
  rejected: ["non_compliant", "Rejected"],
  missing: ["not_started", "Missing"],
}

export function SlotStatePill({ state, artefactState }: { state: string; artefactState?: string }) {
  if (state === "pending") {
    return <StatusPill status="in_review" label={artefactState === "verifying" ? "Verifying" : "Needs review"} />
  }
  const [status, label] = MAP[state] ?? ["not_started", state]
  return <StatusPill status={status} label={label} />
}
```

`frontend/src/components/VerificationPanel.tsx`:
```tsx
import { useEffect } from "react"
import { useLink } from "../api/evidence"
import type { ArtefactLink } from "../api/types"
import { formatDate } from "../lib/format"
import { Icon } from "./icons"

const TONE: Record<string, string> = { pass: "text-ok", warn: "text-warn", fail: "text-bad", skipped: "text-fg-3" }

function Verdict({ link }: { link: ArtefactLink }) {
  if (link.state === "accepted") {
    const until = link.expires_on ? ` until ${formatDate(link.expires_on)}` : ""
    return <p className="rounded-lg bg-ok-soft px-3 py-2"><b>Accepted.</b> {link.slot_name} is verified{until}.</p>
  }
  if (link.state === "in_review") {
    return (
      <p className="rounded-lg bg-review-soft px-3 py-2">
        <b>Needs review.</b> The checks weren't conclusive, so a reviewer will decide. You'll see the decision here.
      </p>
    )
  }
  return (
    <p className="rounded-lg bg-bad-soft px-3 py-2">
      <b>Rejected.</b> Fix the failed checks above and upload a new version.
    </p>
  )
}

export function VerificationPanel({ linkId, onDone }: { linkId: string; onDone: () => void }) {
  const query = useLink(linkId)
  const link = query.data
  const done = link !== undefined && link.state !== "verifying"
  useEffect(() => {
    if (done) onDone()
  }, [done, onDone])

  if (!link) return <p role="status" className="px-5 pb-4 text-[13px] text-fg-3">Uploading…</p>
  return (
    <div className="mx-5 mb-4 grid gap-2 rounded-lg border border-line bg-canvas p-3 text-[13px]" aria-live="polite">
      <div className="flex items-center justify-between gap-3">
        <span className="truncate font-mono font-medium">{link.filename}</span>
        <span className="text-fg-3 tabular-nums">
          {done ? "Checks complete" : `Checking ${link.rules.length} of ${link.rules_planned}`}
        </span>
      </div>
      <ul className="grid gap-1.5">
        {link.rules.map((rule) => (
          <li key={rule.seq} className="grid grid-cols-[18px_minmax(0,1fr)_auto] items-start gap-2">
            <span className={TONE[rule.status]}><Icon name={rule.status} /></span>
            <div className="min-w-0">
              <span className="font-medium">{rule.name}</span>
              <span className="text-fg-2"> — {rule.reason}</span>
              {rule.fix_hint && <p className="text-fg-2">{rule.fix_hint}</p>}
            </div>
            <code className="font-mono text-[11px] text-fg-3">{rule.code}</code>
          </li>
        ))}
      </ul>
      {link.confidence !== null && (
        <p className="text-fg-2">Confidence <b className="tabular-nums">{link.confidence.toFixed(2)}</b></p>
      )}
      {done && <Verdict link={link} />}
    </div>
  )
}
```

- [ ] **Step 5: Wire the evidence section into the control page**

In `frontend/src/pages/ControlDetail.tsx`, replace the evidence `<section>` (the one rendering `c.slots.map(...)`) with `<EvidenceSlots control={c} canEdit={canEdit} />`, and add these components to the file (imports: `useQueryClient` from `@tanstack/react-query`; `useCallback`, `useState`, `type DragEvent` from `react`; `useUploadEvidence` from `../api/evidence`; `SlotStatePill`; `VerificationPanel`; `formatDate`; `Icon`; types `EvidenceSlot as Slot`):
```tsx
function EvidenceSlots({ control, canEdit }: { control: Detail; canEdit: boolean }) {
  const upload = useUploadEvidence(control.code)
  const queryClient = useQueryClient()
  const [active, setActive] = useState<Record<string, string>>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const refresh = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["control", control.code] })
    queryClient.invalidateQueries({ queryKey: ["readiness"] })
  }, [queryClient, control.code])

  async function send(slotId: string, file: File) {
    setErrors((e) => ({ ...e, [slotId]: "" }))
    try {
      const link = await upload.mutateAsync({ slotId, file })
      setActive((a) => ({ ...a, [slotId]: link.id }))
    } catch (err) {
      setErrors((e) => ({ ...e, [slotId]: err instanceof Error ? err.message : "Upload failed." }))
    }
  }

  return (
    <section className="rounded-xl border border-line bg-surface">
      <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
        <h2 className="text-[15px] font-semibold">Evidence</h2>
        {canEdit && <span className="text-[12.5px] text-fg-3">Drop a file on a slot, or use Upload</span>}
      </div>
      <ul>
        {control.slots.map((slot) => (
          <SlotRow key={slot.id} slot={slot} canEdit={canEdit} onFile={(f) => send(slot.id, f)}
            activeLinkId={active[slot.id]} error={errors[slot.id]} onDone={refresh} />
        ))}
      </ul>
    </section>
  )
}

function SlotRow({ slot, canEdit, onFile, activeLinkId, error, onDone }: {
  slot: Slot
  canEdit: boolean
  onFile: (file: File) => void
  activeLinkId?: string
  error?: string
  onDone: () => void
}) {
  const [over, setOver] = useState(false)
  const meta = [
    slot.evidence_type,
    slot.freshness_days ? `Refresh every ${slot.freshness_days} days` : null,
    slot.artefact?.filename,
    slot.artefact?.expires_on ? `expires ${formatDate(slot.artefact.expires_on)}` : null,
  ].filter(Boolean)

  function onDrop(event: DragEvent) {
    event.preventDefault()
    setOver(false)
    const file = event.dataTransfer.files[0]
    if (file && canEdit) onFile(file)
  }

  return (
    <li
      className={`border-b border-line last:border-0 ${over ? "bg-primary-soft" : ""}`}
      onDragOver={(e) => { if (canEdit) { e.preventDefault(); setOver(true) } }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
    >
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5">
        <div className="min-w-0">
          <p className="font-semibold">{slot.name}</p>
          <p className="text-[12.5px] text-fg-3">
            {meta.map((m, i) => <span key={i}>{i > 0 && <span aria-hidden="true"> · </span>}{m}</span>)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <SlotStatePill state={slot.state} artefactState={slot.artefact?.state} />
          {canEdit && (
            <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-line-2 bg-surface px-2.5 py-1 text-[13px] font-medium hover:border-fg-3">
              <Icon name="upload" size={14} />
              {slot.artefact ? "New version" : "Upload"}
              <input type="file" className="sr-only" aria-label={`Upload evidence for ${slot.name}`}
                onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = "" }} />
            </label>
          )}
        </div>
      </div>
      {activeLinkId && <VerificationPanel linkId={activeLinkId} onDone={onDone} />}
      {error && <p role="alert" className="px-5 pb-3 text-[13px] text-bad">{error}</p>}
    </li>
  )
}
```
Note: the existing test `a manager saves the implementation description` asserts `screen.getByText("Refresh every 31 days")` — the new meta rendering keeps that text in its own `<span>`, so it still passes.

- [ ] **Step 6: Run tests and build**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd frontend && npx vitest run --testTimeout=10000 && npm run build`
Expected: all tests pass; build succeeds.

- [ ] **Step 7: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && git add -A && git commit -m "feat(web): evidence upload with live verification on the control page" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Frontend — review queue page

**Files:**
- Create: `frontend/src/pages/ReviewQueue.tsx`, `frontend/src/pages/ReviewQueue.test.tsx`
- Modify: `frontend/src/router.tsx`, `frontend/src/components/AppShell.tsx`

**Interfaces:**
- Consumes: `useReviewQueue`, `useLink`, `useDecision` (Task 11).
- Produces: route `/evidence` (`ReviewQueuePage`); Evidence nav item enabled.

- [ ] **Step 1: Write the failing test**

`frontend/src/pages/ReviewQueue.test.tsx`:
```tsx
import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { json, ME, mockApi, renderApp } from "../test/render"

const ITEM = {
  link_id: "l1", control_code: "A.7.4", control_title: "Physical security monitoring",
  slot_name: "CCTV system status", filename: "cctv.png", confidence: null, uploaded_by: "Bilal Khan",
  uploaded_at: "2026-10-07T09:00:00Z",
}
const LINK = {
  id: "l1", state: "in_review", confidence: null, evidence_date: null, expires_on: null, slot_id: "s1",
  slot_name: "CCTV system status", control_code: "A.7.4", control_title: "Physical security monitoring",
  artefact_id: "a1", version_id: "v1", version_no: 1, filename: "cctv.png", size: 10, mime: "image/png",
  uploaded_at: "2026-10-07T09:00:00Z", uploaded_by: "Bilal Khan", decided_by: null, decision_reason: null,
  rules_planned: 1,
  rules: [{ seq: 1, code: "V-SCREENSHOT", name: "Screenshot provenance", status: "skipped",
            reason: "Needs text recognition (OCR), which isn't enabled yet.", fix_hint: null, excerpt: null }],
  text_preview: null,
}

test("a reviewer accepts an item with a reason", async () => {
  let decided = false
  const calls = mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /review-queue": () => json(200, decided ? [] : [ITEM]),
    "GET /artefact-links/l1": () => json(200, LINK),
    "POST /artefact-links/l1/decision": () => {
      decided = true
      return json(200, { ...LINK, state: "accepted", decided_by: "Sana Malik" })
    },
  })
  renderApp("/evidence")
  expect(await screen.findByText("Screenshot provenance")).toBeInTheDocument()
  expect(screen.getByRole("link", { name: "Download cctv.png" })).toHaveAttribute(
    "href", "/api/v1/artefact-versions/v1/download")
  await userEvent.type(screen.getByLabelText("Reason"), "Timestamp visible in the photo.")
  await userEvent.click(screen.getByRole("button", { name: "Accept" }))
  expect(await screen.findByText("The review queue is clear.")).toBeInTheDocument()
  const post = calls.find((c) => c.method === "POST")!
  expect(JSON.parse(String(post.init.body))).toEqual({ decision: "accept", reason: "Timestamp visible in the photo." })
})

test("the server's refusal is shown", async () => {
  mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /review-queue": () => json(200, [ITEM]),
    "GET /artefact-links/l1": () => json(200, LINK),
    "POST /artefact-links/l1/decision": () =>
      json(403, { detail: "You can't review evidence you uploaded. Ask another reviewer." }),
  })
  renderApp("/evidence")
  await userEvent.click(await screen.findByRole("button", { name: "Accept" }))
  expect(await screen.findByRole("alert")).toHaveTextContent("You can't review evidence you uploaded.")
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd frontend && npx vitest run src/pages/ReviewQueue.test.tsx --testTimeout=10000`
Expected: FAIL — `Failed to resolve import "./ReviewQueue"` (and no `/evidence` route).

- [ ] **Step 3: Implement**

`frontend/src/pages/ReviewQueue.tsx`:
```tsx
import { useState } from "react"
import { useDecision, useLink, useReviewQueue } from "../api/evidence"
import { Button } from "../components/Button"
import { ControlId } from "../components/ControlId"
import { Icon } from "../components/icons"
import { formatDate } from "../lib/format"

const TONE: Record<string, string> = { pass: "text-ok", warn: "text-warn", fail: "text-bad", skipped: "text-fg-3" }

export function ReviewQueuePage() {
  const queue = useReviewQueue()
  const [selected, setSelected] = useState<string | null>(null)
  const items = queue.data ?? []
  const current = items.find((i) => i.link_id === selected)?.link_id ?? items[0]?.link_id

  return (
    <div className="mx-auto grid max-w-6xl gap-4">
      <header>
        <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Evidence</p>
        <h1 className="font-display text-[26px] font-extrabold tracking-tight">Review queue</h1>
      </header>
      {queue.isError && <p role="alert">{queue.error.message}</p>}
      {queue.isSuccess && items.length === 0 && (
        <section className="rounded-xl border border-line bg-surface p-10 text-center">
          <p className="font-semibold">The review queue is clear.</p>
          <p className="text-[13px] text-fg-3">Evidence the checks can't decide on will appear here.</p>
        </section>
      )}
      {items.length > 0 && (
        <section className="grid overflow-hidden rounded-xl border border-line bg-surface md:grid-cols-[300px_minmax(0,1fr)]">
          <ul className="border-b border-line md:border-b-0 md:border-r">
            {items.map((item) => (
              <li key={item.link_id}>
                <button type="button" onClick={() => setSelected(item.link_id)} aria-current={item.link_id === current}
                  className="block w-full border-b border-line px-4 py-3 text-left hover:bg-subtle aria-[current=true]:bg-primary-soft">
                  <span className="block truncate font-mono text-[12.5px] font-medium">{item.filename}</span>
                  <span className="block text-[12px] text-fg-3"><ControlId code={item.control_code} /> · {item.slot_name}</span>
                  <span className="block text-[12px] text-fg-3">
                    {item.uploaded_by ?? "Unknown"} · {formatDate(item.uploaded_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {current && <ReviewDetail key={current} linkId={current} />}
        </section>
      )}
    </div>
  )
}

function ReviewDetail({ linkId }: { linkId: string }) {
  const link = useLink(linkId)
  const decision = useDecision()
  const [reason, setReason] = useState("")
  if (!link.data) return <p role="status" className="p-5 text-fg-3">Loading…</p>
  const l = link.data

  function decide(choice: "accept" | "reject") {
    decision.mutate({ linkId, decision: choice, reason })
  }

  return (
    <div className="grid content-start gap-4 p-5">
      <div>
        <p className="font-mono text-[13px] text-fg-3">{l.control_code} · {l.control_title}</p>
        <h2 className="text-[17px] font-semibold">{l.slot_name}</h2>
        <a className="text-[13px] text-primary underline" href={`/api/v1/artefact-versions/${l.version_id}/download`}>
          Download {l.filename}
        </a>
      </div>
      <ul className="grid gap-1.5 text-[13px]">
        {l.rules.map((rule) => (
          <li key={rule.seq} className="grid grid-cols-[18px_minmax(0,1fr)] gap-2">
            <span className={TONE[rule.status]}><Icon name={rule.status} /></span>
            <div><span className="font-medium">{rule.name}</span><span className="text-fg-2"> — {rule.reason}</span></div>
          </li>
        ))}
      </ul>
      {l.text_preview && (
        <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-subtle p-3 font-mono text-[12px]">
          {l.text_preview}
        </pre>
      )}
      <label htmlFor="review-reason" className="text-[13px] font-medium">Reason</label>
      <textarea id="review-reason" rows={2} value={reason} onChange={(e) => setReason(e.target.value)}
        className="rounded-lg border border-line-2 bg-surface px-3 py-2 text-sm"
        placeholder="Required when rejecting, or when accepting despite failed checks" />
      {decision.isError && <p role="alert" className="text-[13px] text-bad">{decision.error.message}</p>}
      <div className="flex gap-2">
        <Button onClick={() => decide("accept")} disabled={decision.isPending}>Accept</Button>
        <Button variant="secondary" onClick={() => decide("reject")} disabled={decision.isPending}>Reject</Button>
      </div>
    </div>
  )
}
```

In `frontend/src/router.tsx` import `ReviewQueuePage` and add:
```tsx
const evidenceRoute = createRoute({ getParentRoute: () => appRoute, path: "/evidence", component: ReviewQueuePage })
```
and include `evidenceRoute` in `appRoute.addChildren([...])`.

In `frontend/src/components/AppShell.tsx`, widen `NavItem.to` to `"/" | "/controls" | "/evidence"` and change the Evidence item to `{ label: "Evidence", icon: "evidence", to: "/evidence" }`.

- [ ] **Step 4: Run tests and build**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd frontend && npx vitest run --testTimeout=10000 && npm run build`
Expected: all pass; build succeeds.

- [ ] **Step 5: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && git add -A && git commit -m "feat(web): evidence review queue" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: Frontend — readiness dashboard, control score and attestation

**Files:**
- Create: `frontend/src/components/ReadinessRing.tsx`
- Modify: `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/Dashboard.test.tsx`, `frontend/src/components/AppShell.test.tsx`, `frontend/src/pages/ControlDetail.tsx`, `frontend/src/pages/ControlDetail.test.tsx`, `frontend/src/pages/Controls.tsx`
- Test: `frontend/src/pages/Dashboard.test.tsx`, `frontend/src/pages/ControlDetail.test.tsx` (attest test)

**Interfaces:**
- Consumes: `useReadiness`, `useAttest` (Task 11).
- Produces: `ReadinessRing({ value })`.

- [ ] **Step 1: Write the failing tests**

Replace `frontend/src/pages/Dashboard.test.tsx`:
```tsx
import { screen } from "@testing-library/react"
import { json, ME, mockApi, renderApp } from "../test/render"

const readiness = (value: number | null) => ({
  scope_id: "s",
  readiness: value,
  status_counts: { not_started: 90, in_progress: 2, compliant: 1 },
  by_theme: { Organizational: value === null ? null : 4.1, People: value === null ? null : 0 },
  trend: [],
})

test("shows readiness, status counts and theme readiness", async () => {
  mockApi({ "GET /auth/me": () => json(200, ME), "GET /readiness": () => json(200, readiness(2.4)) })
  renderApp("/")
  expect(await screen.findByRole("img", { name: "Readiness 2 percent" })).toBeInTheDocument()
  expect(screen.getByText("Organizational").closest("tr")).toHaveTextContent("4%")
  expect(screen.getByText("Compliant").closest("span")?.parentElement).toHaveTextContent("1")
})

test("explains where readiness will appear before any evidence exists", async () => {
  mockApi({ "GET /auth/me": () => json(200, ME), "GET /readiness": () => json(200, readiness(null)) })
  renderApp("/")
  expect(await screen.findByText(/Readiness appears once the first evidence is verified/)).toBeInTheDocument()
})
```

In `frontend/src/components/AppShell.test.tsx`, replace the `"GET /controls/summary"` mock in the sign-out test with `"GET /readiness": () => json(200, { scope_id: "s", readiness: null, status_counts: {}, by_theme: {}, trend: [] }),`.

Append to `frontend/src/pages/ControlDetail.test.tsx`:
```tsx
test("the owner attests that the control operates as described", async () => {
  document.cookie = "assayr_csrf=token-xyz; path=/"
  const calls = mockApi({
    "GET /auth/me": () => json(200, ME),
    "GET /controls/A.8.13": () => json(200, DETAIL),
    "POST /controls/A.8.13/attest": () =>
      json(200, { ...DETAIL, attestation: { attested_at: "2026-10-07T09:00:00Z", valid_until: "2026-11-07T09:00:00Z",
                                            by: "Sana Malik", statement: "Operates as described." } }),
  })
  renderApp("/controls/A.8.13")
  expect(await screen.findByText("Not attested yet")).toBeInTheDocument()
  await userEvent.click(screen.getByRole("button", { name: "Attest" }))
  await userEvent.click(screen.getByRole("button", { name: "Confirm attestation" }))
  expect(await screen.findByText("Attested by Sana Malik on 7 Oct 2026, valid until 7 Nov 2026")).toBeInTheDocument()
  const post = calls.find((c) => c.method === "POST")!
  expect(JSON.parse(String(post.init.body))).toEqual({ statement: "This control operates as described." })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd frontend && npx vitest run --testTimeout=10000`
Expected: FAIL — readiness ring and attestation text not found.

- [ ] **Step 3: Implement**

`frontend/src/components/ReadinessRing.tsx`:
```tsx
export function ReadinessRing({ value }: { value: number }) {
  const radius = 46
  const circumference = 2 * Math.PI * radius
  const offset = circumference * (1 - Math.min(Math.max(value, 0), 100) / 100)
  return (
    <svg width="108" height="108" viewBox="0 0 108 108" role="img" aria-label={`Readiness ${Math.round(value)} percent`}>
      <circle cx="54" cy="54" r={radius} fill="none" stroke="var(--subtle)" strokeWidth="10" />
      <circle cx="54" cy="54" r={radius} fill="none" stroke="var(--primary)" strokeWidth="10" strokeLinecap="round"
        strokeDasharray={circumference} strokeDashoffset={offset} transform="rotate(-90 54 54)" />
      <text x="54" y="60" textAnchor="middle" fill="var(--text)"
        style={{ font: "800 24px var(--f-display)" }}>{Math.round(value)}%</text>
    </svg>
  )
}
```

Replace `frontend/src/pages/Dashboard.tsx`:
```tsx
import { useReadiness } from "../api/evidence"
import { useMe } from "../auth/session"
import { ReadinessRing } from "../components/ReadinessRing"
import { StatusPill } from "../components/StatusPill"

const ORDER = ["compliant", "at_risk", "in_review", "in_progress", "non_compliant", "not_started", "excluded"]

export function DashboardPage() {
  const me = useMe()
  const readiness = useReadiness()
  const firstName = me.data?.full_name.split(" ")[0] ?? ""
  const data = readiness.data

  return (
    <div className="mx-auto grid max-w-5xl gap-4">
      <header className="mb-2">
        <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">ISO/IEC 27001:2022</p>
        <h1 className="font-display text-[26px] font-extrabold tracking-tight">Welcome, {firstName}</h1>
      </header>
      {readiness.isError && <p role="alert">{readiness.error.message}</p>}
      {data && (
        <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
          <section className="grid content-start gap-4 rounded-xl border border-line bg-surface p-5">
            <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-fg-3">Readiness</p>
            {data.readiness === null ? (
              <p className="text-[13px] text-fg-2">
                Readiness appears once the first evidence is verified. Open a control and upload its evidence to
                start.
              </p>
            ) : (
              <ReadinessRing value={data.readiness} />
            )}
            <div className="flex flex-wrap gap-2">
              {ORDER.filter((s) => data.status_counts[s]).map((status) => (
                <span key={status} className="inline-flex items-center gap-1.5 text-[13px]">
                  <StatusPill status={status} /> <b className="tabular-nums">{data.status_counts[status]}</b>
                </span>
              ))}
            </div>
          </section>
          <section className="rounded-xl border border-line bg-surface">
            <h2 className="border-b border-line px-5 py-3.5 text-[15px] font-semibold">Readiness by Annex A theme</h2>
            <table className="w-full text-[13.5px]">
              <tbody>
                {Object.entries(data.by_theme).map(([theme, value]) => (
                  <tr key={theme} className="border-b border-line last:border-0">
                    <td className="px-5 py-2.5">{theme}</td>
                    <td className="px-5 py-2.5 text-right font-medium tabular-nums">
                      {value === null ? "—" : `${Math.round(value)}%`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </div>
      )}
    </div>
  )
}
```

In `frontend/src/pages/ControlDetail.tsx`, inside the header block under the owner line, add `<AttestationLine control={c} canEdit={canEdit} />`, add a score next to the status pill (`{c.score !== null && <span className="text-[13px] text-fg-2 tabular-nums">Score {Math.round(c.score)}</span>}`), and add (import `useAttest` from `../api/evidence`):
```tsx
function AttestationLine({ control, canEdit }: { control: Detail; canEdit: boolean }) {
  const attest = useAttest(control.code)
  const [open, setOpen] = useState(false)
  const [statement, setStatement] = useState("This control operates as described.")
  const a = control.attestation

  async function confirm() {
    await attest.mutateAsync(statement.trim())
    setOpen(false)
  }

  return (
    <div className="mt-2 grid gap-2 text-[13px] text-fg-2">
      <p>
        {a ? `Attested by ${a.by ?? "unknown"} on ${formatDate(a.attested_at)}, valid until ${formatDate(a.valid_until)}`
           : "Not attested yet"}
        {canEdit && !open && (
          <Button variant="ghost" size="sm" className="ml-2" onClick={() => setOpen(true)}>Attest</Button>
        )}
      </p>
      {open && (
        <div className="grid max-w-xl gap-2">
          <label htmlFor="attest-statement" className="font-medium text-fg">Statement</label>
          <textarea id="attest-statement" rows={2} value={statement} onChange={(e) => setStatement(e.target.value)}
            className="rounded-lg border border-line-2 bg-surface px-3 py-2 text-sm" />
          {attest.isError && <p role="alert" className="text-bad">{attest.error.message}</p>}
          <div className="flex gap-2">
            <Button size="sm" onClick={confirm} disabled={attest.isPending || !statement.trim()}>Confirm attestation</Button>
            <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
          </div>
        </div>
      )}
    </div>
  )
}
```

In `frontend/src/pages/Controls.tsx`, rename the "Evidence" column header to "Score" and replace the evidence cell content with `{c.score === null ? "—" : `${Math.round(c.score)}%`}`.

- [ ] **Step 4: Run tests and build**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && cd frontend && npx vitest run --testTimeout=10000 && npm run build`
Expected: all pass; build succeeds.

- [ ] **Step 5: Commit**

```bash
cd "E:/Work/GRC Tool/assayr" && git add -A && git commit -m "feat(web): readiness dashboard, control score and attestation" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: Deployment (worker, storage, optional ClamAV) and docs

**Files:**
- Modify: `deploy/compose.yaml`, `deploy/assayr.env.example`, `deploy/smoke.sh`, `backend/Dockerfile`, `frontend/Caddyfile`, `README.md`, `backend/.env.example`
- Create: `E:/Work/GRC Tool/Assayr-Vault/06-Architecture/ADRs/ADR-010 Database job queue.md`
- Modify: `E:/Work/GRC Tool/Assayr-Vault/06-Architecture/Tech Stack.md` (Jobs row)

**Interfaces:**
- Consumes: `assayr worker` (Task 6), evidence API (Task 8).
- Produces: compose services `worker` and optional `clamav` (profile `av`); `blobs` volume; smoke test now uploads evidence and waits for a verdict.

- [ ] **Step 1: Extend the smoke test (the failing check)**

In `deploy/smoke.sh`, insert before `compose exec -T api assayr audit-verify`:
```bash
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
```
Run (Docker available): `cd "E:/Work/GRC Tool/assayr" && deploy/smoke.sh` → FAIL with "Evidence was never verified (is the worker running?)". Without Docker, record the ruling and rely on CI.

- [ ] **Step 2: Add the worker, storage and ClamAV to compose**

In `backend/Dockerfile`, before `USER assayr` add:
```dockerfile
RUN mkdir -p /data/blobs && chown assayr /data/blobs
```

Replace `deploy/compose.yaml`:
```yaml
name: assayr

x-assayr-env: &assayr-env
  ASSAYR_DATABASE_URL: postgresql+pg8000://assayr:${POSTGRES_PASSWORD}@db:5432/assayr
  ASSAYR_ORG_NAME: ${ASSAYR_ORG_NAME:-My Organization}
  ASSAYR_SECURE_COOKIES: ${ASSAYR_SECURE_COOKIES:-false}
  ASSAYR_STORAGE_DIR: /data/blobs
  ASSAYR_MAX_UPLOAD_MB: ${ASSAYR_MAX_UPLOAD_MB:-100}
  ASSAYR_CLAMAV_HOST: ${ASSAYR_CLAMAV_HOST:-}

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
    build: ../backend
    environment: *assayr-env
    volumes:
      - blobs:/data/blobs
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  worker:
    build: ../backend
    entrypoint: ["assayr"]
    command: ["worker"]
    environment: *assayr-env
    volumes:
      - blobs:/data/blobs
    depends_on:
      api:
        condition: service_healthy
    restart: unless-stopped

  web:
    build: ../frontend
    ports:
      - "${ASSAYR_HTTP_PORT:-8080}:8080"
    depends_on:
      api:
        condition: service_healthy
    restart: unless-stopped

  clamav:
    image: clamav/clamav:stable
    profiles: ["av"]
    restart: unless-stopped

volumes:
  dbdata:
  blobs:
```
(The worker waits for the API to be healthy, which means migrations and the seed have run.)

Append to `deploy/assayr.env.example`:
```dotenv
# Largest evidence file accepted, in MB.
ASSAYR_MAX_UPLOAD_MB=100
# Malware scanning: start with `docker compose --profile av ...` and set this to clamav.
ASSAYR_CLAMAV_HOST=
```

In `frontend/Caddyfile`, inside `handle /api/* { … }` before `reverse_proxy`, add:
```caddyfile
		request_body {
			max_size 110MB
		}
```

Append to `backend/.env.example`:
```dotenv
ASSAYR_STORAGE_DIR=./data/blobs
```

- [ ] **Step 3: Validate**

Run: `cd "E:/Work/GRC Tool/assayr/deploy" && cp -n assayr.env.example assayr.env; docker compose --env-file assayr.env config --quiet && echo "compose file valid" && docker compose --env-file assayr.env --profile av config --services`
Expected: `compose file valid`, then the service list including `worker` and `clamav`. With Docker running, `deploy/smoke.sh` ends with `Smoke test passed …` after printing `Evidence verified by the worker: …`.

- [ ] **Step 4: Update README and the vault**

In `README.md`, under "Backend", after the `uvicorn` line add:
```bash
uv run assayr worker               # in a second terminal: verifies uploaded evidence
```
and add a row to the Administration table: `| \`assayr worker [--once]\` | Run background jobs (evidence verification, scheduled status checks) |`.

Create `E:/Work/GRC Tool/Assayr-Vault/06-Architecture/ADRs/ADR-010 Database job queue.md`:
```markdown
---
adr: 10
status: Accepted
date: 2026-10-07
tags: [adr]
---

# ADR-010 Database job queue

**Context.** Evidence verification and scheduled status checks run in the background. The [[Tech Stack]] proposed Celery with Valkey. For an on-prem product every extra service is one more thing to install, secure, back up and upgrade ([[ADR-001 On-prem first containerised deployment]], [[ADR-003 PostgreSQL as the single datastore]]).

**Decision.** Jobs live in a `job` table in PostgreSQL. `assayr worker` claims them with `SELECT … FOR UPDATE SKIP LOCKED`, retries failures up to three times with back-off, and reclaims jobs whose worker died (locked for more than 10 minutes). Several workers can run side by side. Verification progress reaches the browser by polling; each rule result is committed as soon as it runs.

**Consequences.** + No extra container; jobs are covered by the normal database backup; a crashed worker never loses work. − Polling the table adds a little database load (one indexed query every 2 s per idle worker); very high job volumes would justify moving to a dedicated queue behind the same `enqueue`/`handler` interface. Live progress over SSE remains a later improvement (FR-04.5).
```
In `E:/Work/GRC Tool/Assayr-Vault/03-Product/Compliance Scoring Model.md`, change the two slot-state rows to:
```markdown
| Verified | Best linked artefact accepted, age < freshness − warning window | 1.0 |
| Verified – expiring | Accepted, within the warning window: 30 days or a quarter of the freshness window, whichever is shorter | 0.8 |
```
In `E:/Work/GRC Tool/Assayr-Vault/06-Architecture/Tech Stack.md`, change the `| Jobs |` row's choice to: `PostgreSQL job table + \`assayr worker\` ([[ADR-010 Database job queue]]); Celery + Valkey only if volumes demand it`.

- [ ] **Step 5: Verify everything and commit**

Run: `cd "E:/Work/GRC Tool/assayr" && source scripts/dev-env.sh && (cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest -W error) && (cd frontend && npm run typecheck && npx vitest run --testTimeout=10000 && npm run build)`
Expected: every command succeeds.

```bash
cd "E:/Work/GRC Tool/assayr" && git add -A && git commit -m "feat(deploy): worker service, evidence storage volume and optional ClamAV" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Self-Review Notes

- **Spec coverage:** FR-03.1 (single upload + drag-drop), 03.2 (types minus ZIP/EML), 03.4 (one link per slot; multi-slot linking deferred), 03.5 versions, 03.6 metadata (evidence date), 03.7 freshness/expiry via slot states + periodic recompute (reminder notifications → 1c), 03.8 preview as text excerpt (rendered preview → 1c), 03.9 library (review queue + control pages; full library view → 1b), FR-04.1–04.4, 04.6 (OCR → 1c), 04.7 rules-only mode, 04.10 overrides at verdict level, 04.14 on-prem; FR-05.1–05.5; WF-04, WF-05, WF-06 (minus reminders); Screen specs for control detail, upload, review, dashboard. Deferred items are listed in the header.
- **Type consistency checked:** `SlotView`, `slot_views`, `recompute_control(db, control, now, settings, trigger)`, `JobEnv(settings, store, now)`, `enqueue(db, kind, payload, now)`, `run_order`, `decide(results, accept, reject)`, `link_out`, `edit_rights`, `control_detail`, frontend `ArtefactLink`/`useLink`/`useDecision`/`useAttest`/`useReadiness` used with the same names everywhere.
- **Placeholder scan:** no TBDs; every code step carries full code; corrected test snippets are inline.
