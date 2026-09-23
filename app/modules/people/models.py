from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index,
    String, Table, Text, Uuid, func, true, false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


from app.db.base import Base

account_roles = Table(
    'account_roles', Base.metadata,
    Column('account_id', Uuid, ForeignKey('accounts.id', ondelete='CASCADE'), primary_key=True),
    Column('role_id', Uuid, ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
)

class Person(Base):
    __tablename__ = 'people'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    contact_email: Mapped[str | None] = mapped_column(String(320))
    photo_path: Mapped[str | None] = mapped_column(String(500))
    phone: Mapped[str | None] = mapped_column(String(40))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    account: Mapped[Account | None] = relationship(back_populates='person', passive_deletes='all')
    school_profile: Mapped[SchoolProfile | None] = relationship(back_populates='person', passive_deletes='all')


class Account(Base):
    __tablename__ = 'accounts'
    __table_args__ = (
        CheckConstraint("status IN ('active', 'disabled')", name='valid_status'),
        Index('uq_accounts_login_email_ci', func.lower(Column('login_email', String(320))), unique=True),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    person_id: Mapped[UUID] = mapped_column(ForeignKey('people.id', ondelete='RESTRICT'), unique=True)
    login_email: Mapped[str] = mapped_column(String(320))
    password_hash: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default='active', server_default='active')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    person: Mapped[Person] = relationship(back_populates='account')
    roles: Mapped[list[Role]] = relationship(secondary=account_roles, back_populates='accounts', lazy='selectin')


class LoginSession(Base):
    __tablename__ = 'login_sessions'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(ForeignKey('accounts.id', ondelete='CASCADE'))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    account: Mapped[Account] = relationship()


class SchoolProfile(Base):
    __tablename__ = 'school_profiles'
    # The primary key also guarantees at most one profile for each person.
    person_id: Mapped[UUID] = mapped_column(ForeignKey('people.id', ondelete='RESTRICT'), primary_key=True)
    position: Mapped[str] = mapped_column(String(100), default='')
    display_name: Mapped[str] = mapped_column(String(50))
    short_bio: Mapped[str] = mapped_column(String(500), default='')
    full_bio: Mapped[str] = mapped_column(Text, default='')
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    person: Mapped[Person] = relationship(back_populates='school_profile')


class Role(Base):
    __tablename__ = 'roles'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(30), unique=True)
    description: Mapped[str] = mapped_column(String(300), default='')
    accounts: Mapped[list[Account]] = relationship(secondary=account_roles, back_populates='roles')
