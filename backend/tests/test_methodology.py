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
    assert authority_allows("isms_manager", "isms_manager") and not authority_allows(
        "isms_manager", "executive"
    )
    assert not authority_allows("risk_owner", "isms_manager") and not authority_allows(None, "risk_owner")


def test_acceptance_days():
    assert acceptance_days(M, "critical") == 90 and acceptance_days(M, "high") == 365


def test_rating_errors():
    assert rating_error(M, likelihood=6) == "Likelihood must be between 1 and 5."
    assert rating_error(M, consequence={"financial": 0}) == "Financial must be between 1 and 5."
    assert rating_error(M, consequence={"weather": 2}) == "Unknown consequence area: weather."
    assert rating_error(M, current=(3, 9)) == "The current level is outside the scale."
    assert rating_error(M, likelihood=3, consequence={"data": 5}, target=(1, 1)) is None
