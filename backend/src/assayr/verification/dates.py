"""Find dates in document text and work out which one dates the evidence."""

import re
from dataclasses import dataclass
from datetime import date, timedelta

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
_MONTH = (
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
    r"sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_PATTERNS = [
    (re.compile(r"(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)"), "ymd"),
    (re.compile(r"(?<!\d)(\d{1,2})[/.](\d{1,2})[/.](\d{4})(?!\d)"), "dmy"),
    (
        re.compile(r"(?<!\d)(\d{1,2})(?:st|nd|rd|th)?[\s-]+" + _MONTH + r"\.?,?[\s-]+(\d{4})(?!\d)", re.I),
        "d_mon_y",
    ),
    (re.compile(r"\b" + _MONTH + r"\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})(?!\d)", re.I), "mon_d_y"),
]
# (keyword, label). The keyword ending closest before a date labels it; specific beats the generic "date".
_LABELS = [
    ("next review date", "next_review"),
    ("next review", "next_review"),
    ("review due", "next_review"),
    ("last reviewed", "review"),
    ("reviewed", "review"),
    ("review date", "review"),
    ("approved", "approval"),
    ("approval", "approval"),
    ("signed", "approval"),
    ("effective", "effective"),
    ("issued", "issue"),
    ("issue date", "issue"),
    ("as of", "as_of"),
    ("as at", "as_of"),
    ("period", "period"),
    ("dated", "date"),
    ("date", "date"),
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
