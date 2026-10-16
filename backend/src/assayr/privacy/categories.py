"""Shared vocabulary: CIA levels in words and personal-data categories (Qatar PDPPL, ISO 27001 A.5.34)."""

LEVELS = {1: "Very low", 2: "Low", 3: "Medium", 4: "High", 5: "Very high"}

PII_CATEGORIES = {
    "contact": "Contact details",
    "national_id": "National ID / QID / passport",
    "financial": "Financial",
    "health": "Health",
    "biometric": "Biometric",
    "hr": "Employee / HR records",
    "children": "Children's data",
    "location": "Location",
    "online": "Online identifiers",
    "religion": "Religious beliefs",
    "criminal": "Criminal records",
    "ethnic": "Ethnic origin",
    "other": "Other",
}
# Special-category ("sensitive") personal data.
SENSITIVE = frozenset({"health", "biometric", "children", "religion", "criminal", "ethnic"})
PII_VOLUMES = ("lt100", "100_1k", "1k_10k", "gt10k")


def level_label(level: int) -> str:
    return LEVELS.get(level, str(level))


def unknown_categories(categories: list[str]) -> list[str]:
    return [c for c in categories if c not in PII_CATEGORIES]


def normalise_pii(
    holds: bool, categories: list[str] | None, sensitive: bool, volume: str | None
) -> tuple[bool, list[str], bool, str | None]:
    """No personal data means no details; a sensitive category always makes the record sensitive."""
    if not holds:
        return False, [], False, None
    unique = list(dict.fromkeys(categories or []))
    return True, unique, sensitive or bool(SENSITIVE & set(unique)), volume
