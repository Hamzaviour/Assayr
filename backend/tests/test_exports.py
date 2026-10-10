import pytest

from assayr.exports import safe_cell


@pytest.mark.parametrize(
    "value,expected",
    [
        ('=HYPERLINK("http://evil","click")', '\'=HYPERLINK("http://evil","click")'),
        ("+1+1", "'+1+1"),
        ("-2+3", "'-2+3"),
        ("@SUM(A1)", "'@SUM(A1)"),
        ("\tcmd", "'\tcmd"),
        ("Ransomware", "Ransomware"),
        (12, 12),
        (None, None),
    ],
)
def test_safe_cell(value, expected):
    assert safe_cell(value) == expected
