"""The risk methodology (vault: 03-Product/Risk Methodology.md). Every rating decision is a pure function of it."""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.risk.models import MethodologyVersion

AUTHORITY_ORDER = ("risk_owner", "isms_manager", "executive")
AUTHORITY_LABEL = {
    "risk_owner": "the risk owner",
    "isms_manager": "an ISMS manager",
    "executive": "top management",
}
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
                "guidance": [
                    "None",
                    "Local, short-lived",
                    "Regional media",
                    "National media",
                    "Lasting brand damage",
                ],
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
