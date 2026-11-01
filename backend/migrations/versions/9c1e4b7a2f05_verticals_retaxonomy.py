"""Verticals re-taxonomy: 14 new verticals, FK-constrain company_documents.vertical
and approval_policies.applies_to_vertical, backfill all live data.

Implements plan.md / table_schemas.md (§1-§3, §6, §7). See those two files at the
repo root for the full taxonomy evaluation, per-document sign-off table, and
rationale — this migration is the literal, mechanical execution of what they
specify; it does not re-derive any classification decision.

Schema change is minimal: no new column is added to either table. `vertical` and
`applies_to_vertical` stay plain `text` columns; a new `company.verticals(name,
slug, description)` lookup table is created and both existing columns gain a
nullable FK to it (`ON UPDATE CASCADE`), keyed on the existing text values. No
reader/writer code path needs to change for this part of the schema.

Backfill: every live `vertical`/`applies_to_vertical` value is remapped from the
old 14-name taxonomy to the new 14-name taxonomy, using an explicit per-doc_number
override for the 15 live `company.company_documents` rows (table_schemas.md §7 —
the authoritative source for those docs) and a default old-name -> new-name table
for everything else (table_schemas.md §6 — covers `approval_policies` and any
future/CI-seeded document not in the override list). If any non-NULL value has no
mapping entry in either table, the migration aborts (raises) rather than silently
nulling or skipping a row.

Rollback source is two point-in-time backup tables (table_schemas.md §3),
snapshotted before the UPDATE runs. They are NOT dropped by downgrade() or by this
migration — retain for 30 days post-cutover per plan.md, then drop in a separate,
later migration.

The backfill UPDATE lists only `vertical` (resp. `applies_to_vertical`) in its SET
clause. There is no DB trigger on either table (confirmed via pg_trigger), but the
app layer bumps `company_documents.updated_at` on writes through its own code path
(doc_admin.py) — this raw SQL backfill must not mimic that, so a pure
re-classification does not make all 15 documents look freshly edited.

Revision ID: 9c1e4b7a2f05
Revises: f7b2c91d4a08
Create Date: 2026-10-31 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '9c1e4b7a2f05'
down_revision: Union[str, None] = 'f7b2c91d4a08'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ---------------------------------------------------------------------------
# table_schemas.md §5 — 14 new verticals (name, slug, description verbatim
# from "Strata Verticals — Final Reference.md"'s "What It Covers" column).
# ---------------------------------------------------------------------------
NEW_VERTICALS = [
    ("Corporate Governance & Board", "corporate-governance-board",
     "Board structure, bylaws, charters, fiduciary duties, shareholder rights, "
     "entity management, annual filings, regulatory disclosure obligations"),
    ("Compliance & Ethics", "compliance-ethics",
     "Code of conduct, anti-corruption (FCPA), anti-bribery, whistleblower "
     "protections, compliance training, conflicts of interest, FTC "
     "consumer/advertising compliance"),
    ("Legal & Contractual", "legal-contractual",
     "Contract governance, litigation holds, IP protection, licensing, entity "
     "structure, NDAs, antitrust compliance"),
    ("Financial Compliance & Reporting", "financial-compliance-reporting",
     "SOX/ICFR, GAAP/IFRS, financial disclosures, audit requirements, internal "
     "controls, revenue recognition, pricing regulations, fee disclosures"),
    ("Tax & Trade Compliance", "tax-trade-compliance",
     "Corporate tax, payroll tax, sales tax, international tax (FATCA), "
     "transfer pricing, export controls, customs, OFAC sanctions, tariffs"),
    ("Workforce & Employment", "workforce-employment",
     "Labor laws, wage & hour, FMLA, ADA, anti-discrimination, benefits "
     "(ERISA), immigration/work authorization, DEI policies"),
    ("Health & Safety", "health-safety",
     "Workplace safety, emergency preparedness, hazard communication, PPE, "
     "incident reporting, product/consumer safety"),
    ("Data Privacy & Cybersecurity", "data-privacy-cybersecurity",
     "GDPR, CCPA/CPRA, state privacy laws, data breach notification, "
     "cybersecurity frameworks, data retention, information security"),
    ("Environmental & Sustainability", "environmental-sustainability",
     "EPA regulations, emissions, waste management, environmental permits, "
     "GHG reporting, ESG disclosures, climate risk, energy management"),
    ("Operations & Quality", "operations-quality",
     "Quality management, process compliance, GMP, FDA product regulations, "
     "CAPA, operational standards, business process documentation"),
    ("Information Technology & Records", "information-technology-records",
     "IT policies, system access controls, change management, records "
     "retention, digital accessibility (ADA/WCAG), AI governance and "
     "responsible use"),
    ("Supply Chain & Third-Party Risk", "supply-chain-third-party-risk",
     "Vendor compliance, third-party risk, supplier due diligence, modern "
     "slavery/forced labor, supply chain transparency, conflict minerals"),
    ("Policy & Training Management", "policy-training-management",
     "Policy lifecycle, document control, version management, compliance "
     "training programs, employee acknowledgments"),
    ("Risk & Resilience", "risk-resilience",
     "Enterprise risk management, insurance requirements, business "
     "continuity, disaster recovery, operational resilience"),
]

# ---------------------------------------------------------------------------
# table_schemas.md §6 — default old (stored) name -> new name, for any value
# not covered by the per-doc_number override below.
# ---------------------------------------------------------------------------
DEFAULT_MAP = {
    "Policy & Governance": "Corporate Governance & Board",
    "Compliance & Legal": "Compliance & Ethics",
    "Financial & Reporting": "Financial Compliance & Reporting",
    "Revenue & Pricing": "Financial Compliance & Reporting",
    "Operations & Processes": "Operations & Quality",
    "Technology & Systems": "Information Technology & Records",
    "Workforce & Safety": "Workforce & Employment",
    "Environmental": "Environmental & Sustainability",
    "Supply Chain & Procurement": "Supply Chain & Third-Party Risk",
    "Risk & Insurance": "Risk & Resilience",
    "Strategic & Competitive": "Corporate Governance & Board",
    "Reputational & Stakeholder": "Corporate Governance & Board",
    "Contractual & Third-Party Obligations": "Legal & Contractual",
    "Capital & Infrastructure": "Risk & Resilience",
}

# ---------------------------------------------------------------------------
# table_schemas.md §7 — explicit per-doc_number override for the 15 live
# company_documents rows (confirmed against production/branch doc_number
# values, including the "#register" twin suffix). Takes precedence over
# DEFAULT_MAP, but only for company_id = 'rpl' (plan.md): doc_number is only
# guaranteed unique within one tenant, so this override must never match a
# different company's document that happens to share a doc_number string.
# ---------------------------------------------------------------------------
DOC_NUMBER_OVERRIDE = {
    "RPL-CMP-REG-001": "Compliance & Ethics",
    "RPL-CMP-REG-001#register": "Compliance & Ethics",
    "RPL-REG-CAL-2025": "Compliance & Ethics",
    "RPL-REG-CAL-2025#register": "Compliance & Ethics",
    "RPL-LEG-RRS-001": "Information Technology & Records",
    "RPL-LEG-RRS-001#register": "Information Technology & Records",
    "RPL-TAR-GRR-012": "Financial Compliance & Reporting",
    "RPL-CS-PRO-004": "Compliance & Ethics",
    "RPL-CS-PRO-007": "Financial Compliance & Reporting",
    "RPL-DO-PLN-002": "Operations & Quality",
    "RPL-CS-PRO-011": "Compliance & Ethics",
    "RPL-MTR-PGM-001": "Operations & Quality",
    "RPL-DCC-PRO-003": "Operations & Quality",
    "RPL-ENV-PRO-005": "Environmental & Sustainability",
    "RPL-SAF-PRO-009": "Health & Safety",
}

_BACKUP_DOCS = "company._vertical_backfill_20261031"
_BACKUP_POLICIES = "company._approval_policy_vertical_backfill_20261031"


def upgrade() -> None:
    bind = op.get_bind()

    # -- 1. company.verticals (table_schemas.md §1) -------------------------
    op.execute("""
        CREATE TABLE company.verticals (
            name        text PRIMARY KEY,
            slug        text UNIQUE NOT NULL,
            description text
        )
    """)
    bind.execute(
        sa.text(
            "INSERT INTO company.verticals (name, slug, description) "
            "VALUES (:name, :slug, :description)"
        ),
        [{"name": n, "slug": s, "description": d} for n, s, d in NEW_VERTICALS],
    )

    # -- 2. backup tables (table_schemas.md §3) — before the UPDATE ---------
    # Idempotent on purpose: the backup tables are deliberately NOT dropped by
    # downgrade() (they are the rollback source and must outlive a revert), so
    # a later upgrade() after a downgrade() must not try to recreate them. If
    # one already exists, its contents are already the true pre-migration
    # values (either from this migration's first run, or restored verbatim by
    # downgrade() immediately before this), so skipping the recreate is safe.
    backup_docs_exists = bind.execute(sa.text(
        "SELECT to_regclass('company._vertical_backfill_20261031') IS NOT NULL"
    )).scalar()
    if not backup_docs_exists:
        op.execute(f"""
            CREATE TABLE {_BACKUP_DOCS} AS
              SELECT company_id, doc_id, vertical AS old_vertical
              FROM company.company_documents
        """)

    backup_policies_exists = bind.execute(sa.text(
        "SELECT to_regclass('company._approval_policy_vertical_backfill_20261031') IS NOT NULL"
    )).scalar()
    if not backup_policies_exists:
        op.execute(f"""
            CREATE TABLE {_BACKUP_POLICIES} AS
              SELECT company_id, policy_id, applies_to_vertical AS old_applies_to_vertical
              FROM company.approval_policies
        """)

    # -- 3. backfill company.company_documents.vertical --------------------
    doc_rows = bind.execute(
        sa.text(
            "SELECT company_id, doc_id, doc_number, vertical "
            "FROM company.company_documents"
        )
    ).mappings().all()

    doc_updates = []
    for row in doc_rows:
        old = row["vertical"]
        if old is None:
            continue  # unclassified stays unclassified, valid under nullable FK
        override = (
            DOC_NUMBER_OVERRIDE.get(row["doc_number"])
            if row["company_id"] == "rpl"
            else None
        )
        new = override or DEFAULT_MAP.get(old)
        if new is None:
            raise RuntimeError(
                f"verticals migration: no mapping for company_documents "
                f"({row['company_id']}, {row['doc_id']}, doc_number="
                f"{row['doc_number']!r}) with vertical={old!r}. Aborting — "
                f"refusing to silently null or skip a document."
            )
        if new != old:
            doc_updates.append(
                {"company_id": row["company_id"], "doc_id": row["doc_id"], "new": new}
            )

    if doc_updates:
        bind.execute(
            sa.text(
                "UPDATE company.company_documents "
                "SET vertical = :new "
                "WHERE company_id = :company_id AND doc_id = :doc_id"
            ),
            doc_updates,
        )

    # -- 4. backfill company.approval_policies.applies_to_vertical ----------
    policy_rows = bind.execute(
        sa.text(
            "SELECT company_id, policy_id, applies_to_vertical "
            "FROM company.approval_policies"
        )
    ).mappings().all()

    policy_updates = []
    for row in policy_rows:
        old = row["applies_to_vertical"]
        if old is None:
            continue
        new = DEFAULT_MAP.get(old)
        if new is None:
            raise RuntimeError(
                f"verticals migration: no mapping for approval_policies "
                f"policy_id={row['policy_id']} with applies_to_vertical="
                f"{old!r}. Aborting."
            )
        if new != old:
            policy_updates.append(
                {"company_id": row["company_id"], "policy_id": row["policy_id"], "new": new}
            )

    if policy_updates:
        bind.execute(
            sa.text(
                "UPDATE company.approval_policies "
                "SET applies_to_vertical = :new "
                "WHERE company_id = :company_id AND policy_id = :policy_id"
            ),
            policy_updates,
        )

    # -- 5. FK constraints, nullable, ON UPDATE CASCADE ----------------------
    op.execute("""
        ALTER TABLE company.company_documents
          ADD CONSTRAINT company_documents_vertical_fk
          FOREIGN KEY (vertical) REFERENCES company.verticals(name)
          ON UPDATE CASCADE
    """)
    op.execute("""
        ALTER TABLE company.approval_policies
          ADD CONSTRAINT approval_policies_vertical_fk
          FOREIGN KEY (applies_to_vertical) REFERENCES company.verticals(name)
          ON UPDATE CASCADE
    """)


def downgrade() -> None:
    """Restore old vertical/applies_to_vertical values from the backup tables
    and drop the verticals lookup table + both FKs. The backup tables
    themselves are NOT dropped here (see module docstring)."""
    bind = op.get_bind()

    op.execute("""
        ALTER TABLE company.company_documents
          DROP CONSTRAINT company_documents_vertical_fk
    """)
    op.execute("""
        ALTER TABLE company.approval_policies
          DROP CONSTRAINT approval_policies_vertical_fk
    """)

    bind.execute(sa.text(f"""
        UPDATE company.company_documents AS cd
        SET vertical = b.old_vertical
        FROM {_BACKUP_DOCS} AS b
        WHERE cd.company_id = b.company_id AND cd.doc_id = b.doc_id
    """))
    bind.execute(sa.text(f"""
        UPDATE company.approval_policies AS ap
        SET applies_to_vertical = b.old_applies_to_vertical
        FROM {_BACKUP_POLICIES} AS b
        WHERE ap.company_id = b.company_id AND ap.policy_id = b.policy_id
    """))

    op.execute("DROP TABLE company.verticals")
