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
            select(Task)
            .where(Task.entity_type == "risk", Task.entity_id == str(risk.id))
            .order_by(Task.created_at)
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
            RiskControlOut(
                code=link.control.code, title=link.control.title, status=link.control.status, axis=link.axis
            )
            for link in links
        ],
        draft=assessment_out(db, risk, draft) if draft else None,
        latest=assessment_out(db, risk, latest) if latest else None,
        history=[assessment_out(db, risk, a) for a in finalized_assessments(db, risk)],
        treatment=TreatmentOut(
            option=risk.treatment_option,
            note=risk.treatment_note,
            budget=risk.treatment_budget,
            due=risk.treatment_due,
        ),
        actions=[task_out(t) for t in actions],
        acceptance=_acceptance_out(db, acceptance) if accepted_latest else None,
        required_authority=required,
        can_accept=can_accept,
        can_edit=rights.any and risk.closed_at is None,
        closed_at=risk.closed_at,
        close_reason=risk.close_reason,
    )
