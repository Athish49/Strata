"""What-if scenarios (engine_spec.md section 8): scenario CRUD, editable sections, run wrapper, preset helpers.

A what-if run is an ordinary engine run with kind='whatif' (origin 'whatif' changes); it is never
exported or scored. Pure helpers (number words, value replacement, preset selection) live here so
scripts/make_whatif_presets.py and the tests share them.
"""
from __future__ import annotations

import re
import uuid
from typing import Any, Iterable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.config import engine_settings
from app.engine.footprint import load_footprint, rule_key

EDIT_KINDS = ("text_edit", "repeal")


# ---------------------------------------------------------------- sections

_S1_ROWS_SQL = """
    SELECT cs.id AS s1_section_id, cs.citation, cs.heading
    FROM public.code_sections cs
    JOIN (SELECT source_system, MIN(snapshot_date) AS d FROM public.code_sections GROUP BY source_system) s1
      ON s1.source_system = cs.source_system AND s1.d = cs.snapshot_date
    WHERE cs.id = ANY(:ids)
"""


async def list_editable_sections(session: AsyncSession) -> list[dict]:
    """S1 sections cited by the company's eligible clauses, most-cited first."""
    fp = await load_footprint(session, engine_settings.ENGINE_COMPANY_ID)
    if not fp.cited_section_ids:
        return []
    rows = (await session.execute(text(_S1_ROWS_SQL), {"ids": sorted(fp.cited_section_ids)})).mappings().all()
    counts = fp.clause_count_by_section
    out = [{"citation": r["citation"], "s1_section_id": r["s1_section_id"], "heading": r["heading"],
            "cited_clause_count": counts.get(r["s1_section_id"], 0)} for r in rows]
    out.sort(key=lambda s: (-s["cited_clause_count"], s["citation"]))
    return out


async def get_section(session: AsyncSession, s1_section_id: int) -> dict | None:
    row = (await session.execute(text(
        "SELECT citation, heading, body_text FROM public.code_sections WHERE id = :id"
    ), {"id": s1_section_id})).mappings().first()
    if row is None:
        return None
    return {"citation": row["citation"], "heading": row["heading"], "s1_text": row["body_text"] or ""}


# ---------------------------------------------------------------- scenarios

_SCENARIO_COLS = """s.scenario_id, s.title, s.source_system, s.citation, s.s1_section_id, s.edit_kind,
                    s.edited_text, s.is_preset, s.last_run_id, s.created_at, r.status AS status"""
_SCENARIO_FROM = """FROM engine.whatif_scenarios s
                    LEFT JOIN engine.runs r ON r.run_id = s.last_run_id"""


def _scenario_dict(r: Any) -> dict:
    d = dict(r)
    d["scenario_id"] = str(d["scenario_id"])
    d["last_run_id"] = str(d["last_run_id"]) if d.get("last_run_id") else None
    return d


async def list_scenarios(session: AsyncSession) -> list[dict]:
    rows = (await session.execute(text(
        f"SELECT {_SCENARIO_COLS} {_SCENARIO_FROM} ORDER BY s.is_preset DESC, s.created_at DESC, s.title"
    ))).mappings().all()
    return [_scenario_dict(r) for r in rows]


async def get_scenario(session: AsyncSession, scenario_id: str) -> dict | None:
    try:
        sid = str(uuid.UUID(str(scenario_id)))
    except ValueError:
        return None
    row = (await session.execute(text(
        f"SELECT {_SCENARIO_COLS} {_SCENARIO_FROM} WHERE s.scenario_id = CAST(:sid AS uuid)"
    ), {"sid": sid})).mappings().first()
    return _scenario_dict(row) if row else None


def validate_scenario(edit_kind: str, edited_text: str | None) -> str | None:
    """Error message when the scenario body is invalid, else None."""
    if edit_kind not in EDIT_KINDS:
        return f"unknown edit_kind: {edit_kind!r}"
    if edit_kind == "text_edit" and not (edited_text and edited_text.strip()):
        return "edited_text is required for text_edit"
    return None


async def create_scenario(
    session: AsyncSession,
    *,
    s1_section_id: int,
    edit_kind: str,
    edited_text: str | None,
    title: str,
    is_preset: bool = False,
    scenario_id: str | None = None,
) -> str:
    """Insert a scenario (commits). Raises ValueError on invalid input or an unknown S1 section."""
    err = validate_scenario(edit_kind, edited_text)
    if err:
        raise ValueError(err)
    sec = (await session.execute(text(
        "SELECT source_system, citation FROM public.code_sections WHERE id = :id"
    ), {"id": s1_section_id})).mappings().first()
    if sec is None:
        raise ValueError(f"S1 section not found: {s1_section_id}")
    sid = scenario_id or str(uuid.uuid4())
    await session.execute(text("""
        INSERT INTO engine.whatif_scenarios
            (scenario_id, title, source_system, citation, s1_section_id, edit_kind, edited_text, is_preset)
        VALUES (CAST(:sid AS uuid), :title, :ss, :cit, :s1, :kind, :txt, :preset)
    """), {"sid": sid, "title": title, "ss": sec["source_system"], "cit": sec["citation"],
           "s1": s1_section_id, "kind": edit_kind,
           "txt": edited_text if edit_kind == "text_edit" else None, "preset": is_preset})
    await session.commit()
    return sid


async def upsert_preset(
    session: AsyncSession, *, title: str, s1_section_id: int, edit_kind: str, edited_text: str | None
) -> str:
    """Idempotent by title among presets; updates the existing row, else inserts. Commits."""
    err = validate_scenario(edit_kind, edited_text)
    if err:
        raise ValueError(err)
    existing = (await session.execute(text(
        "SELECT scenario_id::text AS sid FROM engine.whatif_scenarios WHERE is_preset AND title = :t"
    ), {"t": title})).mappings().first()
    if existing is None:
        return await create_scenario(session, s1_section_id=s1_section_id, edit_kind=edit_kind,
                                     edited_text=edited_text, title=title, is_preset=True)
    sec = (await session.execute(text(
        "SELECT source_system, citation FROM public.code_sections WHERE id = :id"
    ), {"id": s1_section_id})).mappings().first()
    if sec is None:
        raise ValueError(f"S1 section not found: {s1_section_id}")
    await session.execute(text("""
        UPDATE engine.whatif_scenarios
        SET source_system = :ss, citation = :cit, s1_section_id = :s1, edit_kind = :kind, edited_text = :txt
        WHERE scenario_id = CAST(:sid AS uuid)
    """), {"sid": existing["sid"], "ss": sec["source_system"], "cit": sec["citation"], "s1": s1_section_id,
           "kind": edit_kind, "txt": edited_text if edit_kind == "text_edit" else None})
    await session.commit()
    return existing["sid"]


async def set_last_run(session: AsyncSession, scenario_id: str, run_id: str) -> None:
    await session.execute(text(
        "UPDATE engine.whatif_scenarios SET last_run_id = CAST(:rid AS uuid) WHERE scenario_id = CAST(:sid AS uuid)"
    ), {"rid": run_id, "sid": scenario_id})
    await session.commit()


async def run_whatif(scenario_id: str, run_id: str | None = None) -> str:
    """Run the engine for a scenario (run.py records scenario_id and last_run_id); returns run_id."""
    from app.engine.run import run_engine  # lazy: keeps this module light for scripts/tests
    return await run_engine(kind="whatif", scenario_id=scenario_id, run_id=run_id)


# ---------------------------------------------------------------- number words / replacement

_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
         "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def number_to_words(n: int) -> str | None:
    """English word for 1..999 (hyphenated tens: 'twenty-one'); None outside the range."""
    if not 1 <= n <= 999:
        return None
    if n < 20:
        return _ONES[n]
    if n < 100:
        t, o = divmod(n, 10)
        return _TENS[t] + (f"-{_ONES[o]}" if o else "")
    h, rest = divmod(n, 100)
    return f"{_ONES[h]} hundred" + (f" {number_to_words(rest)}" if rest else "")


def words_to_number(word: str) -> int | None:
    """Inverse of number_to_words (case-insensitive); None when not a number word."""
    w = word.strip().lower().replace(" and ", " ")
    for n in range(1, 1000):
        if number_to_words(n) == w:
            return n
    return None


def changed_value(n: int) -> int:
    """round(n * 1.5), at least n + 1 (spec section 8)."""
    return max(round(n * 1.5), n + 1)


def _match_case(template: str, word: str) -> str:
    if template.isupper() and len(template) > 1:
        return word.upper()
    if template[:1].isupper():
        return word[:1].upper() + word[1:]
    return word


def _numeral_pat(n: int) -> str:
    return rf"(?<![\d.,\-§])\b{n}\b(?![\d\-]|[.,]\d)"


def replace_value(text_: str, old: int, new: int, near: int | None = None) -> tuple[str, str, str] | None:
    """Replace one integer value token, keeping its surface form.

    Handles 'ten (10)' (word + numeral), a bare numeral, and a bare number word. Picks the
    occurrence nearest to `near` (character offset) when given, else the first. Returns
    (new_text, old_surface, new_surface) or None when the token is not found.
    """
    new_word = number_to_words(new)
    old_word = number_to_words(old)
    forms: list[tuple[re.Pattern, Any]] = []
    if old_word and new_word:
        pat = re.compile(rf"\b({re.escape(old_word)})(\s*\(\s*){old}(\s*\))", re.IGNORECASE)
        forms.append((pat, lambda m: f"{_match_case(m.group(1), new_word)}{m.group(2)}{new}{m.group(3)}"))
    forms.append((re.compile(_numeral_pat(old)), lambda m: str(new)))
    if old_word and new_word:
        forms.append((re.compile(rf"\b{re.escape(old_word)}\b", re.IGNORECASE),
                      lambda m: _match_case(m.group(0), new_word)))
    for pat, repl in forms:
        ms = list(pat.finditer(text_))
        if not ms:
            continue
        m = min(ms, key=lambda x: abs(x.start() - near)) if near is not None else ms[0]
        new_surface = repl(m)
        return text_[:m.start()] + new_surface + text_[m.end():], m.group(0), new_surface
    return None


# ---------------------------------------------------------------- preset selection

def pick_value_presets(candidates: Iterable[dict], limit: int = 3) -> list[dict]:
    """Choose up to `limit` sections (distinct rules) with the most clauses citing a parameter token.

    Each candidate: {s1_section_id, citation, value_num, unit, clause_pk} (one row per clause/param);
    only integer values replaceable by replace_value are usable and are filtered by the caller.
    Ranking: distinct clause count desc, then citation. One token (value_num, unit) per section.
    """
    per_token: dict[tuple, dict] = {}
    for c in candidates:
        k = (c["s1_section_id"], c["value_num"], c.get("unit"))
        e = per_token.setdefault(k, {**c, "clauses": set()})
        e["clauses"].add(c["clause_pk"])
    ranked = sorted(per_token.values(), key=lambda e: (-len(e["clauses"]), e["citation"], e["value_num"]))
    chosen: list[dict] = []
    seen_sections: set = set()
    seen_rules: set = set()
    for e in ranked:
        rk = rule_key(e["citation"]) or e["citation"]
        if e["s1_section_id"] in seen_sections or rk in seen_rules:
            continue
        seen_sections.add(e["s1_section_id"])
        seen_rules.add(rk)
        chosen.append({**e, "clause_count": len(e["clauses"])})
        if len(chosen) == limit:
            break
    return chosen


def preset_title(citation: str, subject: str, old: str, new: str) -> str:
    return f"{citation}: {subject} {old}→{new}"
