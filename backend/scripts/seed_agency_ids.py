"""
seed_agency_ids.py — T6: Populate code_sections.agency_id for IAC and CFR rows.

- Adds new agency rows for IAC title 610 (Indiana Department of Labor) and
  675 (Indiana Fire Prevention and Building Safety Commission), both of which
  have jurisdiction_geo='IN' and source URLs from iar.iga.in.gov, clearly
  identifying them as Indiana state agencies.
- Idempotently UPDATEs agency_id on code_sections rows that still have NULL.
- Does NOT touch owning_agency.
"""

from dotenv import load_dotenv
import os
import psycopg2

load_dotenv()

url = os.environ["DATABASE_URL"].replace("+asyncpg", "").split("?")[0]
conn = psycopg2.connect(url, sslmode="require")
conn.autocommit = False
cur = conn.cursor()

# ---------------------------------------------------------------------------
# Step 1: Insert new agency rows for titles 610 and 675 (idempotent).
#
# Both titles have jurisdiction_geo='IN' and source_url from iar.iga.in.gov,
# which is the Indiana General Assembly's administrative register — confirming
# these are Indiana state agencies.  The agency_ids follow the same pattern
# as iurc and idem (leading 'i' for Indiana + abbreviation from owning_agency).
# ---------------------------------------------------------------------------

new_agencies = [
    (
        "idol",
        "Indiana Department of Labor",
        ["IDOL"],
        "state",
        "IN",
        "610",
        ["labor", "workplace safety"],
    ),
    (
        "ifpbsc",
        "Indiana Fire Prevention and Building Safety Commission",
        ["IFPBSC"],
        "state",
        "IN",
        "675",
        ["fire prevention", "building safety"],
    ),
]

for row in new_agencies:
    cur.execute(
        """
        INSERT INTO agencies
            (agency_id, name, aliases, jurisdiction_level,
             jurisdiction_geo, codebook_title, domain)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (agency_id) DO NOTHING
        """,
        row,
    )

conn.commit()
print("Agency rows inserted (or already existed) for idol, ifpbsc.")

# ---------------------------------------------------------------------------
# Step 2: Idempotent UPDATEs — only touch rows where agency_id IS NULL.
# ---------------------------------------------------------------------------

updates = [
    ("iurc", "iac", ("170",)),
    ("idem", "iac", ("326", "327")),
    ("ferc", "cfr", ("18",)),
    ("epa",  "cfr", ("40",)),
    ("idol", "iac", ("610",)),
    ("ifpbsc", "iac", ("675",)),
]

total_updated = 0

for agency_id, source_system, titles in updates:
    placeholders = ",".join(["%s"] * len(titles))
    cur.execute(
        f"""
        UPDATE code_sections
        SET agency_id = %s
        WHERE source_system = %s
          AND title_number IN ({placeholders})
          AND agency_id IS NULL
        """,
        (agency_id, source_system, *titles),
    )
    n = cur.rowcount
    total_updated += n
    label = "/".join(titles)
    print(f"  {source_system.upper()} {label} → {agency_id}: {n} rows updated")

conn.commit()
print(f"\nTotal rows updated: {total_updated}")

# ---------------------------------------------------------------------------
# Step 3: Final verification.
# ---------------------------------------------------------------------------
print("\n--- Final state ---")
cur.execute(
    """
    SELECT source_system, title_number, agency_id, COUNT(*)
    FROM code_sections
    GROUP BY 1, 2, 3
    ORDER BY 1, 2
    """
)
for row in cur.fetchall():
    print(row)

cur.execute(
    """
    SELECT COUNT(*) FROM code_sections WHERE agency_id IS NULL
    """
)
nulls = cur.fetchone()[0]
print(f"\nRows still NULL after update: {nulls}")

conn.close()
