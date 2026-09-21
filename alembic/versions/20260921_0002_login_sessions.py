"""Add persisted login sessions.

Revision ID: 20260921_0002
Revises: 20260920_0001
Create Date: 2026-09-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260921_0002'
down_revision: Union[str, None] = '20260920_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'login_sessions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('account_id', sa.Uuid(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], name='fk_login_sessions_account_id_accounts', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='pk_login_sessions'),
        sa.UniqueConstraint('token_hash', name='uq_login_sessions_token_hash'),
    )
    op.create_index('ix_login_sessions_account_id', 'login_sessions', ['account_id'])
    op.create_index('ix_login_sessions_expires_at', 'login_sessions', ['expires_at'])


def downgrade() -> None:
    op.drop_index('ix_login_sessions_expires_at', table_name='login_sessions')
    op.drop_index('ix_login_sessions_account_id', table_name='login_sessions')
    op.drop_table('login_sessions')