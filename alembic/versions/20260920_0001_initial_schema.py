"""Create the initial people and access-control schema.

Revision ID: 20260920_0001
Revises:
Create Date: 2026-09-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260920_0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'people',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('first_name', sa.String(length=100), nullable=False),
        sa.Column('last_name', sa.String(length=100), nullable=False),
        sa.Column('contact_email', sa.String(length=320), nullable=True),
        sa.Column('photo_path', sa.String(length=500), nullable=True),
        sa.Column('phone', sa.String(length=40), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id', name='pk_people'),
    )
    op.create_table(
        'roles',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=30), nullable=False),
        sa.Column('description', sa.String(length=300), nullable=False),
        sa.PrimaryKeyConstraint('id', name='pk_roles'),
        sa.UniqueConstraint('name', name='uq_roles_name'),
    )
    op.create_table(
        'accounts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('person_id', sa.Uuid(), nullable=False),
        sa.Column('login_email', sa.String(length=320), nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'disabled')", name='valid_status'),
        sa.ForeignKeyConstraint(['person_id'], ['people.id'], name='fk_accounts_person_id_people', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name='pk_accounts'),
        sa.UniqueConstraint('person_id', name='uq_accounts_person_id'),
    )
    op.execute(sa.text('CREATE UNIQUE INDEX uq_accounts_login_email_ci ON accounts (lower(login_email))'))
    op.create_table(
        'school_profiles',
        sa.Column('person_id', sa.Uuid(), nullable=False),
        sa.Column('position', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=50), nullable=False),
        sa.Column('short_bio', sa.String(length=500), nullable=False),
        sa.Column('full_bio', sa.Text(), nullable=False),
        sa.Column('is_published', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.ForeignKeyConstraint(['person_id'], ['people.id'], name='fk_school_profiles_person_id_people', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('person_id', name='pk_school_profiles'),
    )
    op.create_table(
        'account_roles',
        sa.Column('account_id', sa.Uuid(), nullable=False),
        sa.Column('role_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], name='fk_account_roles_account_id_accounts', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], name='fk_account_roles_role_id_roles', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('account_id', 'role_id', name='pk_account_roles'),
    )


def downgrade() -> None:
    op.drop_table('account_roles')
    op.drop_table('school_profiles')
    op.drop_index('uq_accounts_login_email_ci', table_name='accounts')
    op.drop_table('accounts')
    op.drop_table('roles')
    op.drop_table('people')
