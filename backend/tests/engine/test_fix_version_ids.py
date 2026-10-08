import importlib.util
import pathlib

_p = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "fix_current_version_ids.py"
_spec = importlib.util.spec_from_file_location("fix_current_version_ids", _p)
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)
choose_target = _m.choose_target


def _s(vid, n, dv=False, scope=False, prose=True):
    return {"version_id": vid, "n": n, "has_dv": dv, "has_scope": scope, "prose": prose}


def test_current_has_clauses_no_change():
    assert choose_target("a", [_s("a", 5, dv=True), _s("b", 3)])[0] is None


def test_picks_prose_set_without_dv():
    sets = [_s("b", 85, scope=True), _s("c", 70, prose=False)]
    assert choose_target("a", sets)[0] == "b"


def test_ambiguous_skipped():
    assert choose_target("a", [_s("b", 5), _s("c", 4)])[0] is None
