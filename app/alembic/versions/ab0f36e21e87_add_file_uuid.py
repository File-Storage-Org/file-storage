"""add file_uuid

Revision ID: ab0f36e21e87
Revises: 47ae9dbf43c5
Create Date: 2024-05-16 17:20:14.206715

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ab0f36e21e87'
down_revision: Union[str, None] = '47ae9dbf43c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('files', sa.Column('file_uuid', sa.UUID(), nullable=False))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('files', 'file_uuid')
    # ### end Alembic commands ###