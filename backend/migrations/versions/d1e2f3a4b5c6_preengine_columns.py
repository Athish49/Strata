"""pre-engine columns: diff_hash, agency_id, is_citation_fragment, extraction_method

Revision ID: d1e2f3a4b5c6
Revises: c3d4e5f6a7b8
Create Date: 2026-10-07
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # T2: normalized hash for diff comparisons (does not replace content_hash)
    op.add_column(
        'code_sections',
        sa.Column('diff_hash', sa.String(64), nullable=True),
    )

    # T6: resolved agency FK
    op.add_column(
        'code_sections',
        sa.Column('agency_id', sa.String(), nullable=True),
    )
    op.create_foreign_key(
        'fk_code_sections_agency_id',
        'code_sections', 'agencies',
        ['agency_id'], ['agency_id'],
    )

    # T4: flag parameters that fall inside a citation span
    op.execute(
        "ALTER TABLE company.clause_parameters "
        "ADD COLUMN IF NOT EXISTS is_citation_fragment boolean"
    )

    # T5: identify how a citation row was inserted (e.g. 'register_cell_parse')
    op.execute(
        "ALTER TABLE company.clause_citations "
        "ADD COLUMN IF NOT EXISTS extraction_method text"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE company.clause_citations "
        "DROP COLUMN IF EXISTS extraction_method"
    )
    op.execute(
        "ALTER TABLE company.clause_parameters "
        "DROP COLUMN IF EXISTS is_citation_fragment"
    )
    op.drop_constraint('fk_code_sections_agency_id', 'code_sections', type_='foreignkey')
    op.drop_column('code_sections', 'agency_id')
    op.drop_column('code_sections', 'diff_hash')
