"""Timezone setting removed

Revision ID: 988bd8974053
Revises: 4d6e1dfa83eb
Create Date: 2024-04-23 13:06:47.581364

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '988bd8974053'
down_revision: Union[str, None] = '4d6e1dfa83eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('settings')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('settings',
    sa.Column('user_id', sa.INTEGER(), nullable=False),
    sa.Column('timezone', sa.VARCHAR(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('user_id')
    )
    # ### end Alembic commands ###
