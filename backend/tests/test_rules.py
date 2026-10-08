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


def ctx(
    text="",
    *,
    mime=PDF,
    filename="evidence.pdf",
    freshness=365,
    concepts=(),
    supplied=None,
    duplicate=False,
    av=None,
    error=None,
    pages=1,
    metadata=None,
):
    found = find_dates(text)
    best = best_evidence_date(found, TODAY)
    return RuleContext(
        filename=filename,
        mime=mime,
        extracted=Extracted(text=text, pages=pages, metadata=metadata or {}, error=error),
        org_names=["Acme Financial Services"],
        freshness_days=freshness,
        required_concepts=list(concepts),
        today=TODAY,
        supplied_date=supplied,
        evidence_date=supplied or (best.value if best else None),
        found_dates=found,
        duplicate_in_slot=duplicate,
        av_result=av,
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
    assert (
        check("V-KEYWORDS", ctx("Multi-factor authentication; password length 14", concepts=concepts)).status
        == "pass"
    )
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
        "V-FMT",
        "V-AV",
        "V-HASH",
        "V-SCOPE",
        "V-DATE",
        "V-APPROVAL",
        "V-PII",
    ]


def outcome(code, status):
    from assayr.verification.rules import Outcome

    return RULES[code], Outcome(status, "r")


def test_decide():
    assert decide([outcome("V-FMT", "fail"), outcome("V-APPROVAL", "pass")], 0.85, 0.6).verdict == "reject"
    accept = decide([outcome("V-SCOPE", "pass"), outcome("V-APPROVAL", "pass")], 0.85, 0.6)
    assert (accept.verdict, accept.confidence) == ("accept", 1.0)
    review = decide(
        [
            outcome("V-DATE", "pass"),
            outcome("V-OWNER", "pass"),
            outcome("V-APPROVAL", "fail"),
            outcome("V-REVIEW", "pass"),
            outcome("V-KEYWORDS", "pass"),
            outcome("V-SCOPE", "pass"),
        ],
        0.85,
        0.6,
    )
    assert (review.verdict, review.confidence) == ("review", 0.73)
    assert decide([outcome("V-APPROVAL", "fail"), outcome("V-DATE", "pass")], 0.85, 0.6).verdict == "reject"
    nothing = decide([outcome("V-FMT", "pass"), outcome("V-RELEVANCE", "skipped")], 0.85, 0.6)
    assert (nothing.verdict, nothing.confidence) == ("review", None)
