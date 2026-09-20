from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Role

from app.modules.people.schemas import AccountCreate, PersonCreate, SchoolProfileCreate
from app.modules.people.service import attach_account, grant_role, create_person, set_school_profile
#=====================================================

ROLES = {
    'instructor':   "Teach assigned classes",
    'manager':      "Manage schedules and school profiles",
    'admin':        "Manage accounts and role assignments",
    'partner':      "Some description",
    'it':           "Able to manipulate DB",
}


def seed_roles(db: Session):
    existing = set(db.scalars(select(Role.name)))
    for name, description in ROLES.items():
        if name not in existing:
            db.add(Role(name=name, description=description))
    db.flush()


def seed_initial_members(db: Session):
    """ Function creates 2 persons and add them to a database:
        * Admin (Grzegosz Caban)
        * Member (Piotr Kowalski)
    """
    # Create and add Member
    person = PersonCreate(first_name="Piotr", last_name="Kowalksi")
    member = create_person(db, person)
    print('Created generic person:', member.id)

    # Create admin -> make school account --> create associated account
    admin = PersonCreate(first_name="Grzegosz", last_name="Caban")
    admin = create_person(db, admin)

    school_profile = SchoolProfileCreate(display_name="Grzgosz Caban",
                                         position="School owner",
                                         short_bio="Own school",
                                         full_bio="Have been dancing and teaching since ages",
                                         is_published=True)
    set_school_profile(db, admin, school_profile)

    admin_credentials = AccountCreate(login_email="email@gmail.com", password="password")
    admin_account = attach_account(db, admin, admin_credentials)
    grant_role(db, admin_account, db.scalar(select(Role).where(Role.name == 'instructor')))
    grant_role(db, admin_account, db.scalar(select(Role).where(Role.name == 'admin')))

    # Debug info
    identifier = admin_account.id
    print('Created administrator account:', identifier)
    