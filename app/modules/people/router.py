from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.core.auth import Db
from .models import Account, Person, Role
from .queries import public_profiles
from .schemas import AccountCreate, AccountRead, PersonCreate, PersonRead, RoleRead, SchoolProfileRead
from .service import ConflictError, create_person, attach_account, set_school_profile, grant_role

router = APIRouter(tags=['people'])

@router.get('/school-profiles/public', response_model=list[SchoolProfileRead])
def profiles_public(db: Db, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    return public_profiles(db, offset, limit)