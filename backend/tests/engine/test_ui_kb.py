from datetime import date, datetime

import app.api.engine.routes  # noqa: F401  (load aggregate router first; avoids circular import)
from app.api.engine import routes_ui_kb as k


def test_agency_rank_federal_first():
    a = [{"agency_id": x, "level": l} for x, l in
         [("ifpbsc", "state"), ("iurc", "state"), ("epa", "federal"), ("ferc", "federal"), ("idem", "state")]]
    assert [x["agency_id"] for x in sorted(a, key=k._agency_rank)] == ["ferc", "epa", "iurc", "idem", "ifpbsc"]


def test_iso():
    assert k._iso(None) == ""
    assert k._iso(date(2025, 1, 2)) == "2025-01-02"
    assert k._iso(datetime(2025, 1, 2, 3)) == "2025-01-02T03:00:00"


def test_section_light_and_full():
    row = {"citation": "170 IAC 4-1-16", "source_system": "iac", "title_number": "170", "part": "4",
           "section_number": "16", "heading": "170 IAC 4-1-16 Reports", "status": "approved",
           "snapshot_date": date(2025, 12, 31), "agency_id": "iurc", "amendment_source": None,
           "federal_refs": None, "iac_cross_refs": ["x"], "body_text": "BODY"}
    lite = k._section(row, False)
    assert lite["body_text"] == "" and lite["heading"] == "Reports" and lite["rule_key"] == "170 IAC 4-1"
    assert lite["federal_refs"] == [] and lite["owning_agency"] == "iurc" and lite["part_or_article"] == "4"
    assert k._section(row, True)["body_text"] == "BODY"


def test_versions_route_declared_before_plain():
    paths = [r.path for r in k.router.routes]
    assert paths.index("/ui/kb/sections/{source_system}/{citation:path}/versions") < \
        paths.index("/ui/kb/sections/{source_system}/{citation:path}")
