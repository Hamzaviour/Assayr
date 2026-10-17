import json
from pathlib import Path

import pytest

from assayr.catalogue.iso27001_clauses import CLAUSES

DATA = Path(__file__).resolve().parents[1] / "src" / "assayr" / "catalogue" / "data"
ISO = {c["ref"] for c in json.loads((DATA / "iso27001_2022_annex_a.json").read_text("utf-8"))["controls"]}
ISO |= {ref for ref, _title, _parent in CLAUSES}
AUTO = {"ai_register", "aiia_all", "aiia_fresh", "ai_owner", "ai_risks", None}


def load(name):
    return json.loads((DATA / name).read_text("utf-8"))


def test_iso42001_shape():
    d = load("iso42001_2023.json")
    assert len(d["controls"]) == 38 and len(d["objectives"]) == 9
    refs = [c["ref"] for c in d["controls"]]
    assert len(set(refs)) == 38
    assert {c["objective"] for c in d["controls"]} == {o["ref"] for o in d["objectives"]}
    leaves = [c for c in d["clauses"] if c.get("summary")]
    assert len(leaves) == 32 and {"6.1.4", "8.4"} <= {c["ref"] for c in leaves}
    groups = {c["ref"] for c in d["clauses"] if not c.get("summary")}
    assert all(c["parent"] in groups for c in d["clauses"] if c["parent"])


def test_soc2_shape():
    d = load("soc2_tsc_security.json")
    assert len(d["series"]) == 9 and len(d["criteria"]) == 33
    assert [c["ref"] for c in d["criteria"]][:2] == ["CC1.1", "CC1.2"]
    assert {c["series"] for c in d["criteria"]} == {s["ref"] for s in d["series"]}


@pytest.mark.parametrize("name", ["iso42001_2023.json", "soc2_tsc_security.json"])
def test_mappings_exist_and_summaries_are_short(name):
    d = load(name)
    items = d.get("controls", []) + d.get("criteria", []) + [c for c in d.get("clauses", []) if c.get("summary")]
    for item in items:
        assert 20 <= len(item["summary"]) <= 400, item["ref"]
        assert 10 <= len(item["evidence_hint"]) <= 300, item["ref"]
        assert set(item["iso27001"]) <= ISO, item["ref"]
        assert item.get("auto") in AUTO, item["ref"]
