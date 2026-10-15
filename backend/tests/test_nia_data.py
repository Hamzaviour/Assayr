import json
import re
from pathlib import Path

DATA = Path(__file__).parents[1] / "src/assayr/catalogue/data"
NIA = json.loads((DATA / "nia_v2_1.json").read_text(encoding="utf-8"))
ISO = {
    c["ref"]
    for c in json.loads((DATA / "iso27001_2022_annex_a.json").read_text(encoding="utf-8"))["controls"]
}
DOMAINS = "IG RM TM DL CM PS SA IM BC SM DR DC AC CS NS IE GS PR SS SU MS AM CY OS PH VL".split()


def test_domains_are_the_26_nia_domains_in_order():
    assert [d["code"] for d in sorted(NIA["domains"], key=lambda d: d["order"])] == DOMAINS
    assert all(d["name"] and d["summary"] for d in NIA["domains"])


def test_control_refs_are_unique_and_belong_to_a_domain():
    refs = [c["ref"] for c in NIA["controls"]]
    assert len(refs) == len(set(refs)) and len(refs) == 355
    assert all(re.fullmatch(r"[A-Z]{2} \d{1,3}", r) and r.split()[0] in DOMAINS for r in refs)
    assert {"IM 4", "PH 2", "AC 1", "AM 41", "NS 66"} <= set(refs)


def test_mapping_covers_every_control_once_with_real_iso_codes():
    mapped = [m["ref"] for m in NIA["mapping"]]
    assert sorted(mapped) == sorted(c["ref"] for c in NIA["controls"])
    for m in NIA["mapping"]:
        assert set(m["iso"]) <= ISO, m
        assert m["coverage"] in ("full", "partial")


def test_no_ncsa_prose_is_shipped():
    # Summaries are ours and short; controls carry only facts (ID, domain, order, mandatory flag).
    assert all(len(d["summary"]) <= 160 for d in NIA["domains"])
    assert all(set(c) == {"ref", "domain", "order", "mandatory"} for c in NIA["controls"])
    assert sum(c["mandatory"] for c in NIA["controls"]) > 100
