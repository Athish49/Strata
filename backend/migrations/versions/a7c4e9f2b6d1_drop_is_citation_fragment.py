"""drop company.clause_parameters.is_citation_fragment (task 3.4 Option B, deploy 2)

Confirmed before this migration was written (see pending.txt item 4 / report.md):
the column is unwired at write time (never set by the live ingest pipeline) and
provably inert at all 3 read sites (app/engine/candidates.py, rules.py, judge.py)
-- those reads were already removed in a prior, code-only deploy. This is the
second, schema-changing deploy, run only after that code-only deploy was
confirmed live and stable, per guardrail 2 (migrations serialized, one at a time).

Revision ID: a7c4e9f2b6d1
Revises: 9c1e4b7a2f05
Create Date: 2026-11-01
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a7c4e9f2b6d1'
down_revision: Union[str, None] = '9c1e4b7a2f05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE company.clause_parameters "
        "DROP COLUMN IF EXISTS is_citation_fragment"
    )


def downgrade() -> None:
    # Re-add as nullable with no backfill -- the column's own values are not
    # recoverable once dropped. Matches the column's original definition in
    # d1e2f3a4b5c6_preengine_columns.py.
    op.execute(
        "ALTER TABLE company.clause_parameters "
        "ADD COLUMN IF NOT EXISTS is_citation_fragment boolean"
    )
