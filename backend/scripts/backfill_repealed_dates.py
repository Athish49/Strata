"""
Backfill repealed_date for IAC code_sections with status='repealed'.

Extracts the filing date from the section's own leading repeal note in body_text
using an anchored regex. Does NOT fall back to effective_date because that column
is contaminated by body-bleed on ~55 rows (iac.py concatenates a following active
section's text into body_text, causing effective_date to reflect the neighbour, not
the repealed section itself).

superseded_by is left NULL: body_text contains no successor citations.

Dry-run by default. Pass --commit to write changes.
"""

import asyncio
import re
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Matches the leading repeal note, capturing everything inside the parens.
# Handles optional "Sec. N." prefix.
NOTE = re.compile(r"^\s*(?:Sec\.\s*[\d.]+\s*)?\(Repealed\b([^)]*)\)", re.IGNORECASE)
# Matches "filed Mon DD, YYYY" (month name >= 3 chars)
FILED = re.compile(r"filed\s+([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),\s+(\d{4})", re.IGNORECASE)

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def extract_repeal_date(body_text: str):
    """Return (date, error_str) from the leading repeal note in body_text."""
    if not body_text:
        return None, "empty body"
    note_m = NOTE.match(body_text)
    if not note_m:
        return None, "no leading repeal note"
    filed_m = FILED.search(note_m.group(1))
    if not filed_m:
        return None, "no filed date in note"
    mon_key = filed_m.group(1).lower()[:3]
    if mon_key not in MONTH_MAP:
        return None, f"unknown month: {filed_m.group(1)}"
    try:
        d = datetime(int(filed_m.group(3)), MONTH_MAP[mon_key], int(filed_m.group(2))).date()
    except ValueError as e:
        return None, str(e)
    return d, None


async def main(commit: bool):
    from app.db import AsyncSessionLocal
    from sqlalchemy import text

    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                text(
                    "SELECT id, citation, body_text, effective_date "
                    "FROM code_sections "
                    "WHERE source_system = 'iac' AND status = 'repealed'"
                )
            )
        ).fetchall()

    print(f"Loaded {len(rows)} repealed IAC sections.")

    updates = []          # (id, repealed_date)
    skipped = []          # (id, citation, reason)
    differs_from_eff = [] # rows where body date != effective_date (body-bleed indicator)

    for row in rows:
        row_id, citation, body, eff = row
        date, err = extract_repeal_date(body)
        if date is None:
            skipped.append((row_id, citation, err))
        else:
            updates.append((row_id, date))
            if date != eff:
                differs_from_eff.append((citation, date, eff))

    print(f"\nResults:")
    print(f"  Body-extracted (would set repealed_date): {len(updates)}")
    print(f"  Skipped (left NULL):                     {len(skipped)}")
    print(f"  Rows where body date != effective_date:  {len(differs_from_eff)}")
    print(f"  superseded_by:                           0 (no data in body_text)")

    if differs_from_eff:
        print(f"\n  -- First 10 body-bleed rows (body_date vs effective_date) --")
        for cit, bd, ed in differs_from_eff[:10]:
            print(f"    {cit}: body={bd}  effective_date={ed}")

    if skipped:
        print(f"\n  -- Skipped rows (first 10) --")
        for rid, cit, reason in skipped[:10]:
            print(f"    id={rid} {cit}: {reason}")

    if not commit:
        print("\nDRY RUN — pass --commit to apply changes.")
        return

    if not updates:
        print("\nNothing to update.")
        return

    async with AsyncSessionLocal() as db:
        for row_id, repealed_date in updates:
            await db.execute(
                text(
                    "UPDATE code_sections "
                    "SET repealed_date = :rd "
                    "WHERE id = :id"
                ),
                {"rd": repealed_date, "id": row_id},
            )
        await db.commit()

    print(f"\nCommitted {len(updates)} rows updated with repealed_date.")
    print("superseded_by left NULL for all rows (no successor citations in body_text).")

    # Bug report for downstream awareness
    print(
        f"\nBUG NOTE: {len(differs_from_eff)} repealed rows have effective_date != "
        "body-extracted repeal date, caused by iac.py bleeding following section text "
        "into body_text. effective_date on repealed rows is unreliable; "
        "report to the iac.py / pipeline.py owner."
    )


if __name__ == "__main__":
    commit = "--commit" in sys.argv
    asyncio.run(main(commit))
