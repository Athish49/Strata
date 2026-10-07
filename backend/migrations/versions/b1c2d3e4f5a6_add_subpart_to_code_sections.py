"""add subpart to code_sections

Revision ID: b1c2d3e4f5a6
Revises: 428534d6a348
Create Date: 2026-10-06 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = '428534d6a348'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('code_sections', sa.Column('subpart', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('code_sections', 'subpart')
