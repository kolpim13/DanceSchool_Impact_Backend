from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from .models import Person, SchoolProfile
from .schemas import SchoolProfileRead


def public_profiles(db: Session, offset: int, limit: int):
    profiles = db.scalars(select(SchoolProfile).join(Person)
        .options(joinedload(SchoolProfile.person))
        .where(SchoolProfile.is_published.is_(True), Person.is_active.is_(True))
        .order_by(SchoolProfile.display_name, SchoolProfile.person_id)
        .offset(offset).limit(limit))
    return [SchoolProfileRead(
        person_id=p.person_id, display_name=p.display_name, position=p.position,
        short_bio=p.short_bio, full_bio=p.full_bio, photo_path=p.person.photo_path,
    ) for p in profiles]
