"""Add project references to dynamically add context for a project prompt

Revision ID: f198d38c3ba7
Revises: 26c42d0d48f0
Create Date: 2024-08-21 14:58:00.810067

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f198d38c3ba7'
down_revision: Union[str, None] = '26c42d0d48f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###
