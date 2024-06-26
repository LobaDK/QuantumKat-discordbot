"""DB setup

Revision ID: 0bac96146ecb
Revises: 
Create Date: 2024-04-24 09:03:37.995177

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0bac96146ecb'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('servers',
    sa.Column('server_id', sa.Integer(), nullable=False),
    sa.Column('server_name', sa.String(), nullable=False),
    sa.Column('is_authorized', sa.Integer(), nullable=False),
    sa.Column('is_banned', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('server_id')
    )
    op.create_index(op.f('ix_servers_server_id'), 'servers', ['server_id'], unique=False)
    op.create_table('users',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(), nullable=False),
    sa.Column('agreed_to_tos', sa.Integer(), nullable=False),
    sa.Column('is_banned', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_index(op.f('ix_users_user_id'), 'users', ['user_id'], unique=False)
    op.create_table('chat',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('server_id', sa.Integer(), nullable=True),
    sa.Column('user_message', sa.String(), nullable=False),
    sa.Column('assistant_message', sa.String(), nullable=False),
    sa.Column('shared_chat', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['server_id'], ['servers.server_id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_id'), 'chat', ['id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_chat_id'), table_name='chat')
    op.drop_table('chat')
    op.drop_index(op.f('ix_users_user_id'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_servers_server_id'), table_name='servers')
    op.drop_table('servers')
    # ### end Alembic commands ###
