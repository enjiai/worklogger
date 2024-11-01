"""empty message

Revision ID: c7bb4e36e4a8
Revises: f198d38c3ba7
Create Date: 2024-08-21 16:03:45.907435

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7bb4e36e4a8'
down_revision: Union[str, None] = 'f198d38c3ba7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('dialog_reference_dialog_id_fkey', 'dialog_reference', type_='foreignkey')
    op.create_foreign_key(None, 'dialog_reference', 'virtual_Oleg_dialogs', ['dialog_id'], ['id'])
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'dialog_reference', type_='foreignkey')
    op.create_foreign_key('dialog_reference_dialog_id_fkey', 'dialog_reference', 'projects', ['dialog_id'], ['id'])
    # ### end Alembic commands ###
