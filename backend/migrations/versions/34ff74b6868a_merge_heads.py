"""merge heads

Revision ID: 34ff74b6868a
Revises: 77a04f843fe2, d1e2f3a4b5c6
Create Date: 2026-10-07 15:35:13.328232

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '34ff74b6868a'
down_revision: Union[str, None] = ('77a04f843fe2', 'd1e2f3a4b5c6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
