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


def test_document_control_table_columns_label_their_dates():
    """Dates in a table row take their meaning from the column header, not from the nearest header word."""
    text = "Version | Effective date | Next review date\n3.0 | 01/03/2026 | 01/03/2027"
    assert [(f.value, f.label) for f in find_dates(text)] == [
        (date(2026, 3, 1), "effective"),
        (date(2027, 3, 1), "next_review"),
    ]
    assert best_evidence_date(find_dates(text), TODAY).value == date(2026, 3, 1)


def test_markdown_tables_skip_the_separator_row():
    text = "| Approval date | Next review |\n|---|---|\n| 2026-02-01 | 2027-02-01 |"
    assert [f.label for f in find_dates(text)] == ["approval", "next_review"]
