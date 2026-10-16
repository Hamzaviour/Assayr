from sqlalchemy import func, select

from assayr.catalogue.models import Control, ControlRequirement, Framework, Requirement
from assayr.nia.seed import NIA_CODE, seed_nia
from tests.test_cli import cli_db, run  # noqa: F401  (fixture and helper)


def nia(db):
    fw = db.scalar(select(Framework).where(Framework.code == NIA_CODE))
    reqs = db.scalars(select(Requirement).where(Requirement.framework_id == fw.id)).all()
    return fw, [r for r in reqs if r.kind == "domain"], [r for r in reqs if r.kind == "control"]


def link_count(db, fw):
    return db.scalar(
        select(func.count())
        .select_from(ControlRequirement)
        .join(Requirement, ControlRequirement.requirement_id == Requirement.id)
        .where(Requirement.framework_id == fw.id)
    )


def test_seed_creates_framework_domains_controls_and_links(db, seeded):
    result = seed_nia(db, seeded)
    db.commit()
    fw, domains, controls = nia(db)
    assert (fw.name, fw.version) == ("NIA", "2.1") and len(domains) == 26
    assert len(controls) == result.controls_created == 355
    ps7 = next(c for c in controls if c.ref == "PS 7")
    assert ps7.title == "PS 7 · Personnel Security" and ps7.parent_id == next(
        d.id for d in domains if d.ref == "PS"
    )
    assert "mandatory" in ps7.attributes
    assert link_count(db, fw) == result.links_created > 355
    own = db.scalars(select(Control).where(Control.code.like("NIA %"))).all()
    assert len(own) == result.own_controls_created == 9
    assert all(c.slots and c.theme for c in own)


def test_seed_is_idempotent_and_keeps_iso_data(db, seeded):
    seed_nia(db, seeded)
    db.commit()
    iso_before = db.scalar(select(func.count()).select_from(Control).where(~Control.code.like("NIA %")))
    again = seed_nia(db, seeded)
    db.commit()
    assert (
        again.domains_created,
        again.controls_created,
        again.links_created,
        again.own_controls_created,
    ) == (
        0,
        0,
        0,
        0,
    )
    assert (
        db.scalar(select(func.count()).select_from(Control).where(~Control.code.like("NIA %"))) == iso_before
    )


def test_cli_seed_also_seeds_nia(cli_db):  # noqa: F811
    run("migrate")
    out = run("seed")
    assert out.exit_code == 0 and "NIA: 355 controls" in out.output
