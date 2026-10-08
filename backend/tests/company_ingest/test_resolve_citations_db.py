"""Unit tests for resolve_all_citations using a fake DB connection."""

from datetime import date

from app.company_ingest.enrich.resolve_citations_db import resolve_all_citations


class _Cur:
    def __init__(self, rows, sections):
        self.rows, self.sections = rows, sections
        self._res = []
        self.updates = None

    def execute(self, sql, params=None):
        if "SELECT DISTINCT source_system, title_number" in sql:
            self._res = [("iac", 327), ("iac", 326)]
        elif "MIN(law_as_of)" in sql:
            self._res = [(date(2024, 12, 31),)]
        elif "FROM company.clause_citations cc" in sql:
            self._res = self.rows
        elif "SELECT id FROM public.code_sections" in sql:
            self._res = [("sec-1",)] if params[0] in self.sections else []
        elif "SELECT EXISTS" in sql:
            pre = params[0].rstrip("%")
            self._res = [(any(c.startswith(pre) for c in self.sections),)]

    def executemany(self, sql, updates):
        self.updates = updates

    def fetchall(self):
        return self._res

    def fetchone(self):
        return self._res[0]

    def close(self):
        pass


class _Conn:
    def __init__(self, cur):
        self.c, self.commits = cur, 0

    def cursor(self):
        return self.c

    def commit(self):
        self.commits += 1


def _row(pk, ss, title, art, sec, gran, raw):
    return (pk, ss, title, art, None, sec, gran, raw, None, date(2024, 12, 31))


ROWS = [
    _row("a", "external_standard", None, None, None, "rule", "NFPA 70E"),
    _row("b", "iac", 327, "15-5", 3, "section", "327 IAC 15-5-3"),
    _row("c", "iac", 327, "15-5", None, "rule", "327 IAC 15-5"),
    _row("d", "iac", 327, "2-6.1", None, "rule", "327 IAC 2-6.1"),
]
SECTIONS = {"327 IAC 15-5-3"}


def test_external_standard_gets_status_and_all_statuses_resolve():
    cur = _Cur(ROWS, SECTIONS | {"327 IAC 15-5-3"})
    conn = _Conn(cur)
    counts = resolve_all_citations(conn)
    assert counts == {"external": 1, "resolved": 1, "resolved_rule": 1, "not_in_kb": 1}
    by_pk = {u[3]: u for u in cur.updates}
    assert by_pk["a"][:3] == ("external", False, None)
    assert by_pk["b"][:3] == ("resolved", True, "sec-1")
    assert conn.commits == 1


def test_dry_run_writes_nothing():
    cur = _Cur(ROWS, SECTIONS)
    conn = _Conn(cur)
    counts = resolve_all_citations(conn, dry_run=True)
    assert sum(counts.values()) == len(ROWS)
    assert cur.updates is None and conn.commits == 0
