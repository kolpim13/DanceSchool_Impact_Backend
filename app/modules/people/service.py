import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pwdlib import PasswordHash
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.config import settings
from .models import Account, LoginSession, SchoolProfile, Person, Role
from .schemas import AccountCreate, LoginRequest, SchoolProfileCreate, PersonCreate
#=====================================================

password_hasher = PasswordHash.recommended()

PHOTO_DIRECTORY = Path(__file__).resolve().parents[2] / 'media' / 'people'
MAX_PHOTO_BYTES = 5 * 1024 * 1024
PHOTO_TYPES = {
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/webp': '.webp',
}
#=====================================================

class ConflictError(ValueError):
    pass


class AuthenticationError(ValueError):
    pass


def create_person(db: Session, data: PersonCreate) -> Person:
    person = Person(**data.model_dump())
    db.add(person)
    db.flush()
    return person


def attach_account(db: Session, person: Person, data: AccountCreate) -> Account:
    if person.account is not None:
        raise ConflictError('Person already has an account')
    account = Account(
        person=person, login_email=str(data.login_email).strip().lower(),
        password_hash=password_hasher.hash(data.password.get_secret_value()),
        roles=[],
    )
    db.add(account)
    db.flush()
    return account


def authenticate_account(db: Session, data: LoginRequest) -> Account:
    account = db.scalar(select(Account).where(Account.login_email == data.login_email))
    if account is None or account.status != 'active' or not password_hasher.verify(
        data.password.get_secret_value(), account.password_hash if account else ''
    ):
        raise AuthenticationError('Invalid email or password')
    return account


def find_active_account_by_email(db: Session, login_email: str) -> Account:
    account = db.scalar(select(Account).where(Account.login_email == login_email.strip().lower()))
    if account is None or account.status != 'active':
        raise AuthenticationError('Invalid email')
    return account


def create_login_session(db: Session, account: Account) -> str:
    token = secrets.token_urlsafe(32)
    session = LoginSession(
        account=account,
        token_hash=hashlib.sha256(token.encode('utf-8')).hexdigest(),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.session_days),
    )
    db.add(session)
    db.flush()
    return token


def revoke_session(db: Session, token: str) -> None:
    # Only the session matching this exact token is revoked; other devices/sessions are untouched.
    token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    session = db.scalar(
        select(LoginSession).where(
            LoginSession.token_hash == token_hash,
            LoginSession.revoked_at.is_(None),
        )
    )
    if session is not None:
        session.revoked_at = datetime.now(timezone.utc)
        db.flush()


def set_school_profile(db: Session, person: Person, data: SchoolProfileCreate) -> SchoolProfile:
    profile = person.school_profile
    if profile is None:
        profile = SchoolProfile(person=person)
        db.add(profile)
    for key, value in data.model_dump().items():
        setattr(profile, key, value)
    db.flush()
    return profile


def grant_role(db: Session, account: Account, role: Role) -> None:
    if role not in account.roles:
        account.roles.append(role)
    db.flush()

