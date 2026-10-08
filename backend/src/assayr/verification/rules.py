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
    "approval": "approval date",
    "effective": "effective date",
    "issue": "issue date",
    "as_of": "as-of date",
    "period": "period",
    "date": "dated",
}
_APPROVAL = re.compile(
    r"\b(approved\s+by|approval|approver|signed\s+off|sign-off|signed\s+by|authori[sz]ed\s+by)\b", re.I
)
_VERSION = re.compile(
    r"\b(version\s*\d+(\.\d+)*|v\d+(\.\d+)+|revision\s+history|document\s+control|rev\.?\s*\d+)\b", re.I
)
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
        return Outcome(
            "fail",
            "This file type isn't accepted as evidence.",
            "Upload a PDF, Word, Excel, CSV, text, PNG or JPEG file.",
        )
    if ctx.extracted.error:
        return Outcome(
            "fail",
            ctx.extracted.error,
            "Save or export the document again (for example as PDF) without a password, then upload it.",
        )
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
        return Outcome(
            "fail",
            f"Flagged by the malware scanner: {result.signature}.",
            "Don't use this file. Contact your administrator.",
        )
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
    return Outcome(
        "fail",
        "Your organization's name doesn't appear in the document.",
        "Is this a template or another company's document? Upload your own version.",
    )


def check_date(ctx: RuleContext) -> Outcome:
    if ctx.supplied_date:
        return Outcome("pass", f"Evidence date given at upload: {format_day(ctx.supplied_date)}.")
    best = best_evidence_date(ctx.found_dates, ctx.today)
    if best:
        label = _DATE_LABEL_TEXT.get(best.label or "")
        return Outcome(
            "pass",
            f"Document date {format_day(best.value)}{f' ({label})' if label else ''}.",
            excerpt=best.excerpt,
        )
    if _no_text(ctx):
        return Outcome(
            "skipped", "There's no readable text to find a date in.", "Add the evidence date when you upload."
        )
    return Outcome(
        "fail", "No document date found.", "Add the evidence date when you upload, or upload a dated version."
    )


def check_fresh(ctx: RuleContext) -> Outcome:
    if not ctx.freshness_days:
        return Outcome("skipped", "This evidence has no freshness window.")
    if ctx.evidence_date is None:
        if _no_text(ctx):
            return Outcome(
                "warn",
                "Couldn't read a date from this file, so a reviewer will confirm it's recent.",
                "Add the evidence date when you upload.",
            )
        return Outcome(
            "fail",
            "Couldn't confirm the evidence is recent: no date found.",
            "Add the evidence date when you upload, or upload a dated version.",
        )
    age = (ctx.today - ctx.evidence_date).days
    when = format_day(ctx.evidence_date)
    if age > ctx.freshness_days:
        return Outcome(
            "fail",
            f"Dated {when}, which is outside the {ctx.freshness_days}-day window.",
            "Upload the latest version of this evidence.",
        )
    return Outcome("pass", f"Dated {when}, within the {ctx.freshness_days}-day window.")


def _pattern_rule(
    pattern: re.Pattern, found: str, missing: str, hint: str
) -> Callable[[RuleContext], Outcome]:
    def check(ctx: RuleContext) -> Outcome:
        if _no_text(ctx):
            return Outcome("skipped", "There's no readable text to check.")
        match = pattern.search(ctx.extracted.text)
        if match:
            return Outcome("pass", found, excerpt=_line_at(ctx.extracted.text, match.start()))
        return Outcome("fail", missing, hint)

    return check


check_approval = _pattern_rule(
    _APPROVAL,
    "Approval or sign-off found.",
    "No approval or sign-off found. This looks like a draft.",
    "Upload the approved version, or add an approval record to the document.",
)
check_version = _pattern_rule(
    _VERSION,
    "Version number or revision history found.",
    "No version number or revision history found.",
    "Add a version number and a revision history table.",
)
_owner_in_text = _pattern_rule(
    _OWNER,
    "Document owner named.",
    "No document owner named.",
    "Name the document owner in the document control table.",
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
        return Outcome(
            "fail",
            f"The next review date ({format_day(latest)}) has passed.",
            "Review the document and upload the updated version.",
        )
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
    return Outcome(
        "warn" if ratio >= 0.5 else "fail",
        f"{summary}; missing: {', '.join(missing)}.",
        "Check the document covers the points under “What auditors look for”.",
    )


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
    return Outcome(
        "warn",
        f"Possible sensitive data: {', '.join(findings)}.",
        "Redact it before keeping this as evidence, and rotate any exposed credentials.",
    )


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
        Rule(
            "V-RELEVANCE",
            "Relevance to the control",
            "soft",
            3,
            _unavailable("Needs the local AI model, which isn't enabled yet."),
        ),
        Rule(
            "V-SCREENSHOT",
            "Screenshot provenance",
            "soft",
            2,
            _unavailable("Needs text recognition (OCR), which isn't enabled yet."),
        ),
        Rule(
            "V-COMPLETENESS",
            "Population coverage",
            "soft",
            3,
            _unavailable("Needs the people directory, which isn't connected yet."),
        ),
        Rule(
            "V-SIGNATURE",
            "Digital signature",
            "soft",
            2,
            _unavailable("Digital signature checks aren't available yet."),
        ),
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
    confidence = (
        round(sum(rule.weight * _SCORE[o.status] for rule, o in soft) / weight, 2) if weight else None
    )
    if hard_fail:
        return Decision("reject", confidence)
    if confidence is None:
        return Decision("review", None)
    if confidence < reject:
        return Decision("reject", confidence)
    if confidence < accept:
        return Decision("review", confidence)
    return Decision("accept", confidence)
