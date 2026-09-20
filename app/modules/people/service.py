from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Account, SchoolProfile, Person, Role
from .schemas import AccountCreate, SchoolProfileCreate, PersonCreate

password_hasher = PasswordHash.recommended()


class ConflictError(ValueError):
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

