"""drop the 2 verticals-retaxonomy backup tables (task 5.3)

9c1e4b7a2f05 created company._vertical_backfill_20261031 and
company._approval_policy_vertical_backfill_20261031 as a 30-day rollback
safety net (retain until 2026-11-30 per plan.md/table_schemas.md, both since
deleted from the working tree but recoverable via `git show 147cf2d:<path>`).

Dropped ahead of that date after an extensive manual verification (see
pending.txt item 6 / the conversation that authorized this): every one of
the 15 live company_documents rows' current `vertical` was independently
re-checked against the signed-off per-document mapping in table_schemas.md
§7 (0/15 mismatches), the live distribution matches the plan's own recorded
verification target exactly, both FK constraints
(company_documents_vertical_fk, approval_policies_vertical_fk) are in place
and enforced so no future write can introduce an invalid value regardless of
these tables, zero code anywhere references either table, and the 10 tables
the plan flagged as "should be unaffected by this migration" all still have
exactly their documented pre-migration row counts.

Once this runs, 9c1e4b7a2f05's own downgrade() can no longer function (it
reads from these tables to restore old values) -- accepted, since the
forward migration's correctness has now been independently re-verified
against the original plan rather than merely trusted.

Revision ID: d4a9e1c7f052
Revises: b3f8d2a6c914
Create Date: 2026-11-01
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'd4a9e1c7f052'
down_revision: Union[str, None] = 'b3f8d2a6c914'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS company._vertical_backfill_20261031")
    op.execute("DROP TABLE IF EXISTS company._approval_policy_vertical_backfill_20261031")


def downgrade() -> None:
    # Cannot be recreated with real data -- the whole point of dropping them now
    # (rather than waiting for 2026-11-30) is that they are no longer needed as a
    # rollback source. A downgrade here is a no-op by design, not a data restore.
    pass
