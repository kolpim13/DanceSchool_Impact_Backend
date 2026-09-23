"""Add login session revocation tracking.

Revision ID: 20260923_0003
Revises: 20260921_0002
Create Date: 2026-09-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260923_0003'
down_revision: Union[str, None] = '20260921_0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('login_sessions') as batch_op:
        batch_op.add_column(sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('login_sessions') as batch_op:
        batch_op.drop_column('revoked_at')
