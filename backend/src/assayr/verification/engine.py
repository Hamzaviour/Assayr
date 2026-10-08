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
    return Extracted(
        text=version.extracted_text or "",
        pages=version.page_count,
        metadata=version.doc_metadata or {},
        error=version.extract_error,
    )


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
    av = (
        scan_file(env.store.path_for(version.sha256), settings.clamav_host, settings.clamav_port)
        if settings.clamav_host
        else None
    )
    duplicates = db.scalar(
        select(func.count())
        .select_from(ArtefactLink)
        .join(ArtefactVersion, ArtefactLink.version_id == ArtefactVersion.id)
        .where(
            ArtefactLink.slot_id == slot.id,
            ArtefactVersion.sha256 == version.sha256,
            ArtefactLink.id != link.id,
            ArtefactLink.state != "superseded",
        )
    )
    found = find_dates(extracted.text)
    best = best_evidence_date(found, today)
    evidence_date = version.evidence_date or (best.value if best else None)
    ctx = RuleContext(
        filename=version.filename,
        mime=version.mime,
        extracted=extracted,
        org_names=[org.name, *(org.aliases or [])],
        freshness_days=slot.freshness_days,
        required_concepts=list(slot.required_concepts or []),
        today=today,
        supplied_date=version.evidence_date,
        evidence_date=evidence_date,
        found_dates=found,
        duplicate_in_slot=bool(duplicates),
        av_result=av,
    )

    run = VerificationRun(link_id=link.id, started_at=now, rules_version=RULES_VERSION)
    db.add(run)
    db.commit()
    outcomes = []
    for seq, code in enumerate(run_order(list(slot.rules or [])), start=1):
        rule = RULES[code]
        outcome = rule.check(ctx)
        db.add(
            RuleResult(
                run_id=run.id,
                seq=seq,
                code=code,
                name=rule.name,
                status=outcome.status,
                weight=rule.weight,
                reason=outcome.reason,
                fix_hint=outcome.fix_hint,
                excerpt=outcome.excerpt,
            )
        )
        db.commit()  # each result becomes visible to the polling UI straight away
        outcomes.append((rule, outcome))

    decision = decide(outcomes, settings.accept_threshold, settings.reject_threshold)
    run.finished_at = env.now()
    run.confidence = decision.confidence
    run.verdict = decision.verdict
    link.confidence = decision.confidence
    link.state = VERDICT_STATE[decision.verdict]
    link.evidence_date = evidence_date
    link.expires_on = (
        evidence_date + timedelta(days=slot.freshness_days) if evidence_date and slot.freshness_days else None
    )
    if link.state == "accepted":
        supersede_older(db, link)
    record(
        db,
        SYSTEM,
        "evidence.verdict",
        "artefact_link",
        str(link.id),
        diff={
            "verdict": decision.verdict,
            "confidence": decision.confidence,
            "control": control.code,
            "slot": slot.name,
        },
    )
    recompute_control(
        db, control, now, settings, trigger=f"Evidence {version.filename} {VERDICT_WORD[decision.verdict]}"
    )
    db.commit()
    return run
