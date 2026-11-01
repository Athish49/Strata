"""add company.verticals.sort_order (task 3.7 prerequisite)

Backfills the same fixed 1-14 ordering the frontend's static VERTICALS array
has always used (identical slug sequence to NEW_VERTICALS in
9c1e4b7a2f05_verticals_retaxonomy.py -- inlined here rather than imported, so
this migration has no dependency on another migration module's internals).

Asserts all 14 rows got a sort_order before making the column NOT NULL +
UNIQUE, so a mismatched or incomplete `company.verticals` table aborts the
migration instead of silently leaving NULLs.

Revision ID: b3f8d2a6c914
Revises: a7c4e9f2b6d1
Create Date: 2026-11-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b3f8d2a6c914'
down_revision: Union[str, None] = 'a7c4e9f2b6d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Same order as NEW_VERTICALS in 9c1e4b7a2f05_verticals_retaxonomy.py and the
# frontend's static VERTICALS array (frontend/lib/verticals.ts) before this change.
ORDERED_SLUGS = [
    "corporate-governance-board",
    "compliance-ethics",
    "legal-contractual",
    "financial-compliance-reporting",
    "tax-trade-compliance",
    "workforce-employment",
    "health-safety",
    "data-privacy-cybersecurity",
    "environmental-sustainability",
    "operations-quality",
    "information-technology-records",
    "supply-chain-third-party-risk",
    "policy-training-management",
    "risk-resilience",
]


def upgrade() -> None:
    bind = op.get_bind()

    op.add_column(
        'verticals',
        sa.Column('sort_order', sa.Integer(), nullable=True),
        schema='company',
    )

    for i, slug in enumerate(ORDERED_SLUGS, start=1):
        bind.execute(
            sa.text("UPDATE company.verticals SET sort_order = :i WHERE slug = :slug"),
            {"i": i, "slug": slug},
        )

    missing = bind.execute(
        sa.text("SELECT slug FROM company.verticals WHERE sort_order IS NULL")
    ).scalars().all()
    if missing:
        raise RuntimeError(
            f"verticals_sort_order: {len(missing)} row(s) got no sort_order "
            f"(not in ORDERED_SLUGS): {missing!r}. Aborting before SET NOT NULL."
        )

    op.alter_column('verticals', 'sort_order', nullable=False, schema='company')
    op.create_unique_constraint(
        'uq_verticals_sort_order', 'verticals', ['sort_order'], schema='company',
    )


def downgrade() -> None:
    op.drop_constraint('uq_verticals_sort_order', 'verticals', schema='company', type_='unique')
    op.drop_column('verticals', 'sort_order', schema='company')
