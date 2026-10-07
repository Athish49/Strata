"""
Backfill affected_entities for regulatory_actions rows.

Extraction sources (high-precision rules only, NULL when confidence is low):

  iurc_investigations: company/utility names extracted from the leading span of
    the title up to (and including) the FIRST corporate designator suffix.
    Trailing legal suffixes (LLC, Inc., etc.) are stripped so the stored value
    matches the canonical short name used in searches.

  federal_register (EPA, 40 CFR 52 and 40 CFR 81): state name extracted from
    the second semicolon-separated segment of the title, validated against a
    closed list of US state and territory names/abbreviations.

  All other source systems: skipped.

Values are stored lowercase to match impact.py:204 exact-element lookup.

Run (dry-run first):
    cd /Users/athish/Documents/Strata/backend
    .venv/bin/python scripts/backfill_affected_entities.py --dry-run
    .venv/bin/python scripts/backfill_affected_entities.py

The script is idempotent: it re-computes every in-scope row and only writes
rows whose value has changed (using IS DISTINCT FROM).
"""
import argparse
import asyncio
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from sqlalchemy import text

from app.db import AsyncSessionLocal

# ---------------------------------------------------------------------------
# IURC investigation extraction
# ---------------------------------------------------------------------------

# Corporate designators that terminate a utility/company name.
# Uses (?=[\s,;]|$) instead of \b because \b does not fire after a literal
# period followed by whitespace.
_CORP_DESIGNATOR_RE = re.compile(
    r"""
    (?:
        LLC | L\.L\.C\.? |
        L\.P\.? | \bLP\b |
        Inc\.? | Incorporated |
        Company | Companies |
        Corporation | Corp\.? |
        Co\. |
        Limited
    )
    (?=[\s,;]|$)
    """,
    re.VERBOSE,
)

# Suffixes to strip from the RIGHT of the captured entity (repeated until stable).
# Company and Corporation are kept — they are part of the proper name.
_STRIP_SUFFIX_RE = re.compile(
    r",?\s*(LLC|L\.L\.C\.?|L\.P\.?|LP|Inc\.?|Corp\.?|Incorporated|Limited)\s*$",
    re.IGNORECASE,
)

# Titles that start with these are administrative/procedural parties, not
# affected entities.  All comparisons are case-insensitive.
_IURC_DENYLIST = re.compile(
    r"""
    ^ (
        Office \s+ of \s+ the \s+ Utility \s+ Consumer \s+ Counselor |
        Indiana \s+ Utility \s+ Regulatory \s+ Commission |
        Citizens \s+ Action \s+ Coalition |
        IURC |
        -\s*\d                  # lines like "- 30 Exhibit..."
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _strip_legal_suffix(entity: str) -> str:
    """Repeatedly strip trailing legal suffixes until stable."""
    prev = None
    while prev != entity:
        prev = entity
        entity = _STRIP_SUFFIX_RE.sub("", entity).strip().rstrip(",").strip()
    return entity


def _extract_iurc_investigation(title: str) -> list[str] | None:
    """Return [entity_lowercase] or None if no confident match."""
    if not title:
        return None

    # Strip leading junk like "- 3 Indiana Utility Regulatory Commission..."
    title = re.sub(r"^\s*-\s*\d+\s+", "", title).strip()

    if _IURC_DENYLIST.match(title):
        return None

    # Find the FIRST corporate designator in the title.
    # Using first (not last) prevents absorbing words from the filing description
    # after the company name (e.g., "Macrotech Corporation CTA Application for
    # Macrotech Corporation" should yield "Macrotech Corporation", not the whole title).
    match = _CORP_DESIGNATOR_RE.search(title)
    if match is None:
        return None

    # Capture up to and including the designator
    end = match.end()
    entity = title[:end].strip().rstrip(",").strip()

    # Strip trailing disposable legal suffixes (e.g., ", LLC" or ", Inc.")
    entity = _strip_legal_suffix(entity)

    # Sanity: entity should not be empty or excessively long (> 80 chars)
    if not entity or len(entity) > 80:
        return None

    return [entity.lower()]


# ---------------------------------------------------------------------------
# EPA state extraction from Air Plan titles
# ---------------------------------------------------------------------------

# Full state names and common abbreviations used by EPA in title segments
_STATE_MAP: dict[str, str] = {
    # Two-letter abbreviations → full name (lowercase)
    "AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas",
    "CA": "california", "CO": "colorado", "CT": "connecticut", "DE": "delaware",
    "FL": "florida", "GA": "georgia", "HI": "hawaii", "ID": "idaho",
    "IL": "illinois", "IN": "indiana", "IA": "iowa", "KS": "kansas",
    "KY": "kentucky", "LA": "louisiana", "ME": "maine", "MD": "maryland",
    "MA": "massachusetts", "MI": "michigan", "MN": "minnesota", "MS": "mississippi",
    "MO": "missouri", "MT": "montana", "NE": "nebraska", "NV": "nevada",
    "NH": "new hampshire", "NJ": "new jersey", "NM": "new mexico", "NY": "new york",
    "NC": "north carolina", "ND": "north dakota", "OH": "ohio", "OK": "oklahoma",
    "OR": "oregon", "PA": "pennsylvania", "RI": "rhode island", "SC": "south carolina",
    "SD": "south dakota", "TN": "tennessee", "TX": "texas", "UT": "utah",
    "VT": "vermont", "VA": "virginia", "WA": "washington", "WV": "west virginia",
    "WI": "wisconsin", "WY": "wyoming",
    # Territories
    "DC": "district of columbia", "PR": "puerto rico", "VI": "u.s. virgin islands",
    "GU": "guam",
}

# Full names as keys → themselves (lowercase)
_STATE_FULL: dict[str, str] = {v: v for v in _STATE_MAP.values()}
# Also Title Case variants
_STATE_FULL.update({v.title(): v for v in _STATE_MAP.values()})
# Explicit multi-word variants that title() doesn't handle correctly
_STATE_FULL["New York"] = "new york"
_STATE_FULL["New Jersey"] = "new jersey"
_STATE_FULL["New Mexico"] = "new mexico"
_STATE_FULL["New Hampshire"] = "new hampshire"
_STATE_FULL["North Carolina"] = "north carolina"
_STATE_FULL["North Dakota"] = "north dakota"
_STATE_FULL["South Carolina"] = "south carolina"
_STATE_FULL["South Dakota"] = "south dakota"
_STATE_FULL["West Virginia"] = "west virginia"
_STATE_FULL["Rhode Island"] = "rhode island"
_STATE_FULL["District Of Columbia"] = "district of columbia"

_CFR_AIR_PLAN_PARTS = {"40 CFR 52", "40 CFR 81"}


def _extract_epa_air_plan(title: str, cfr_references: list[str] | None) -> list[str] | None:
    """Extract state name from EPA Air Plan Approval/Revision titles.

    Only fires when cfr_references includes 40 CFR 52 or 81 and the title
    matches the '; STATE; ...' pattern.
    """
    if not cfr_references:
        return None
    if not any(ref in _CFR_AIR_PLAN_PARTS for ref in cfr_references):
        return None

    # Titles like: "Air Plan Approval; California; ..." or "...; SC; ..."
    segments = [s.strip() for s in title.split(";")]
    if len(segments) < 2:
        return None

    state_seg = segments[1].strip()

    # Try two-letter abbreviation (exact, uppercase)
    abbr = state_seg.upper()
    if abbr in _STATE_MAP:
        return [_STATE_MAP[abbr]]

    # Try full name (case-insensitive)
    lower_seg = state_seg.lower()
    if lower_seg in _STATE_FULL:
        return [_STATE_FULL[lower_seg]]

    # Some titles have "AK, Fairbanks North Star Borough" — parse abbreviation
    # before first comma
    comma_part = state_seg.split(",")[0].strip().upper()
    if comma_part in _STATE_MAP:
        return [_STATE_MAP[comma_part]]

    return None


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def extract_entities(
    source_system: str,
    title: str,
    agency: str | None,
    cfr_references: list[str] | None,
) -> list[str] | None:
    """Return extracted entities (lowercase) or None when extraction is not confident."""
    if source_system == "iurc_investigations":
        return _extract_iurc_investigation(title)

    if source_system == "federal_register" and agency == "epa":
        return _extract_epa_air_plan(title, cfr_references)

    return None


# ---------------------------------------------------------------------------
# Main backfill
# ---------------------------------------------------------------------------

async def _backfill(dry_run: bool) -> None:
    # Fetch all in-scope rows (not just NULL ones) so the script is idempotent
    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            text(
                """
                SELECT id, source_id, source_system, title, agency, cfr_references,
                       affected_entities
                FROM regulatory_actions
                WHERE source_system IN (
                    'iurc_investigations',
                    'federal_register'
                )
                ORDER BY id
                """
            )
        )
        records = rows.mappings().all()

    print(f"Scanning {len(records)} in-scope rows")

    updates: list[tuple[int, list[str] | None, list[str] | None]] = []
    entity_counter: Counter = Counter()

    for rec in records:
        new_entities = extract_entities(
            source_system=rec["source_system"],
            title=rec["title"] or "",
            agency=rec["agency"],
            cfr_references=rec["cfr_references"],
        )
        old_entities = rec["affected_entities"]

        # Only queue rows where the value actually changes
        if new_entities == old_entities:
            continue
        if new_entities is None and old_entities is None:
            continue

        updates.append((rec["id"], old_entities, new_entities))
        if new_entities:
            for e in new_entities:
                entity_counter[e] += 1

        if dry_run:
            print(
                f"  [{rec['source_system']}] {rec['source_id']!r:30s} "
                f"{(rec['title'] or '')[:60]!r:62s} "
                f"{old_entities!r} → {new_entities!r}"
            )

    print(f"\nTotal rows to update: {len(updates)}")
    print(f"\nEntity frequency (top 40):")
    for entity, count in entity_counter.most_common(40):
        print(f"  {count:4d}  {entity!r}")

    if dry_run:
        print("\n[DRY RUN] No changes written.")
        return

    if not updates:
        print("Nothing to update — all in-scope rows already have correct values.")
        return

    async with AsyncSessionLocal() as db:
        for row_id, _old, new_val in updates:
            await db.execute(
                text(
                    "UPDATE regulatory_actions "
                    "SET affected_entities = :entities "
                    "WHERE id = :id"
                ),
                {"entities": new_val, "id": row_id},
            )
        await db.commit()

    print(f"\nWrote {len(updates)} rows.")

    # Verification
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            text(
                """
                SELECT source_system,
                       COUNT(*) AS n,
                       COUNT(CASE WHEN affected_entities IS NOT NULL THEN 1 END) AS has_entities,
                       COUNT(CASE WHEN related_actions::text <> 'null'
                                       AND related_actions IS NOT NULL THEN 1 END) AS has_related_nonnull
                FROM regulatory_actions
                GROUP BY source_system
                ORDER BY source_system
                """
            )
        )
        print("\nPost-backfill coverage:")
        print(f"  {'source_system':<25} {'n':>6} {'has_entities':>12} {'has_related_src':>15}")
        for row in r.mappings():
            print(
                f"  {row['source_system']:<25} "
                f"{row['n']:>6} "
                f"{row['has_entities']:>12} "
                f"{row['has_related_nonnull']:>15}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill affected_entities column")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written without updating the DB",
    )
    args = parser.parse_args()
    asyncio.run(_backfill(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
