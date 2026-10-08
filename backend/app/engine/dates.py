"""Publication dates for changed rows (engine_spec §1.4).

IAC: the newest DIN present in S2 but absent from S1 (the DIN's leading 8
digits are YYYYMMDD).  CFR: Federal Register date looked up through the
amendment source id.  Anything else is None; dates are never guessed.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Tolerates the stray whitespace the source text sometimes carries around "IR-".
_DIN_RE = re.compile(r"\b(\d{8})-\s*IR-\s*(\d+[A-Z]*)\b")

DIN_BASIS = "din_publication"
FR_EFFECTIVE = "fr_effective"
FR_PUBLISHED = "fr_published"


def _find_dins(raw: str | None) -> dict[str, date]:
    """Map normalized DIN -> date for every parseable DIN in ``raw``."""
    out: dict[str, date] = {}
    for m in _DIN_RE.finditer(raw or ""):
        try:
            d = datetime.strptime(m.group(1), "%Y%m%d").date()
        except ValueError:
            continue
        out[f"{m.group(1)}-IR-{m.group(2)}"] = d
    return out


def extract_new_dins(s1_raw: str | None, s2_raw: str | None) -> tuple[str, date] | None:
    """Return (din, published_date) of the newest DIN in S2 absent from S1."""
    old = _find_dins(s1_raw)
    new = {k: v for k, v in _find_dins(s2_raw).items() if k not in old}
    if not new:
        return None
    din = max(new, key=lambda k: (new[k], k))
    return din, new[din]


def _pick(date_effective: date | None, date_published: date | None) -> tuple[date, str] | None:
    if date_effective is not None:
        return date_effective, FR_EFFECTIVE
    if date_published is not None:
        return date_published, FR_PUBLISHED
    return None


async def lookup_fr_dates_batch(
    session: AsyncSession, ids: Iterable[str]
) -> dict[str, tuple[date, str]]:
    """One query for many Federal Register ids; ids not found are omitted."""
    uniq = sorted({i for i in ids if i})
    if not uniq:
        return {}
    rows = (
        await session.execute(
            text(
                """
                SELECT source_id, date_effective, date_published
                FROM public.regulatory_actions
                WHERE source_system = 'federal_register'
                  AND source_id = ANY(:ids)
                """
            ),
            {"ids": uniq},
        )
    ).all()
    out: dict[str, tuple[date, str]] = {}
    for source_id, d_eff, d_pub in rows:
        picked = _pick(d_eff, d_pub)
        # Keep the best basis if a source_id repeats (effective beats published).
        if picked and (source_id not in out or picked[1] == FR_EFFECTIVE):
            out[source_id] = picked
    return out


async def lookup_fr_dates(
    session: AsyncSession, amendment_source: str | None
) -> tuple[date, str] | None:
    if not amendment_source:
        return None
    return (await lookup_fr_dates_batch(session, [amendment_source])).get(amendment_source)


def compute_publication(
    source_system: str,
    s1_raw: str | None,
    s2_raw: str | None,
    amendment_source: str | None,
    fr_lookup: dict[str, tuple[date, str]] | None,
) -> dict:
    """Pure wrapper: {published_date, date_basis, din}, all None when unknown."""
    res: dict = {"published_date": None, "date_basis": None, "din": None}
    sys = (source_system or "").lower()
    if sys == "iac":
        hit = extract_new_dins(s1_raw, s2_raw)
        if hit:
            res.update(din=hit[0], published_date=hit[1], date_basis=DIN_BASIS)
    elif sys == "cfr" and amendment_source and fr_lookup:
        hit = fr_lookup.get(amendment_source)
        if hit:
            res.update(published_date=hit[0], date_basis=hit[1])
    return res
