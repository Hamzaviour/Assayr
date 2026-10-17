"""Data protection impact assessments: when one is recommended, and how privacy risks are scored."""

SCREENING = {
    "sensitive": "Sensitive personal data",
    "large_scale": "Large scale",
    "monitoring": "Systematic monitoring",
    "new_tech": "New technology",
    "children": "Children's data",
    "cross_border": "Transfer outside Qatar",
    "automated": "Automated decisions with significant effect",
    "combining": "Combining datasets",
}
# Any one of these alone calls for a DPIA; otherwise two "yes" answers do.
DECISIVE = frozenset({"sensitive", "children", "automated"})


def dpia_recommended(answers: dict[str, bool]) -> bool:
    yes = {k for k, v in (answers or {}).items() if v}
    return bool(yes & DECISIVE) or len(yes) >= 2


def score_level(score: int) -> int:
    """Likelihood × impact (1–25) banded to the shared five levels."""
    if score >= 20:
        return 5
    if score >= 15:
        return 4
    if score >= 8:
        return 3
    if score >= 4:
        return 2
    return 1
