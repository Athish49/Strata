"""add_cross_refs_to_code_sections

Revision ID: 77a04f843fe2
Revises: b1c2d3e4f5a6
Create Date: 2026-10-06 20:23:14.054540

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '77a04f843fe2'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('code_sections', sa.Column(
        'federal_refs', postgresql.ARRAY(sa.String()), nullable=True
    ))
    op.add_column('code_sections', sa.Column(
        'iac_cross_refs', postgresql.ARRAY(sa.String()), nullable=True
    ))
    op.add_column('code_sections', sa.Column(
        'dins', postgresql.ARRAY(sa.String()), nullable=True
    ))


def downgrade() -> None:
    op.drop_column('code_sections', 'dins')
    op.drop_column('code_sections', 'iac_cross_refs')
    op.drop_column('code_sections', 'federal_refs')
