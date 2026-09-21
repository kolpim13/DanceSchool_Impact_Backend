from typing import Annotated
from uuid import UUID
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.core.auth import Db, SESSION_COOKIE, current_account, require_any_role
from app.core.config import settings
from .models import Account, Person, Role
from .queries import public_profiles
from .schemas import (
    AccountCreate, AccountRead, DevelopmentLoginRequest, LoginRequest,
    PersonCreate, PersonRead, RoleRead, SchoolProfileRead,
)
from .service import (
    MAX_PHOTO_BYTES, PHOTO_DIRECTORY, PHOTO_TYPES, AuthenticationError,
    ConflictError, attach_account, authenticate_account, create_login_session,
    find_active_account_by_email,
)
#=====================================================

router = APIRouter(tags=['people'])
#=====================================================

def get_person(db, identifier):
    p = db.get(Person, identifier)
    if p is None:
        raise HTTPException(404, 'Person not found')
    return p


@router.post('/auth/login', 
             response_model=AccountRead)
def login(data: LoginRequest, response: Response, db: Db):
    try:
        account = authenticate_account(db, data)
    except AuthenticationError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    token = create_login_session(db, account)
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=True,
        samesite='lax',
        max_age=settings.session_days * 24 * 60 * 60,
    )
    return account


@router.post('/auth/dev-login', response_model=AccountRead)
def development_login(data: DevelopmentLoginRequest, response: Response, db: Db):
    if settings.environment != 'development':
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Not found')
    try:
        account = find_active_account_by_email(db, str(data.login_email))
    except AuthenticationError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    token = create_login_session(db, account)
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=True,
        samesite='lax',
        max_age=settings.session_days * 24 * 60 * 60,
    )
    return account


@router.get('/school-profiles/public', 
            response_model=list[SchoolProfileRead])
def profiles_public(db: Db, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    return public_profiles(db, offset, limit)


@router.get('/people/me',
            status_code=status.HTTP_200_OK, 
            response_model=PersonRead)
def read_own_person(account: Annotated[Account, Depends(current_account)], db: Db):
    return get_person(db, account.person_id)


@router.get('/people/{person_id}', 
            response_model=PersonRead,
            status_code=status.HTTP_200_OK,
            dependencies=[Depends(require_any_role('admin', 'it'))])
def read_person(person_id: UUID, db: Db):
    return get_person(db, person_id)


@router.post('/people/{person_id}/account',
             response_model=AccountRead,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_any_role('admin', 'it'))],
)
def create_account(person_id: UUID, data: AccountCreate, db: Db):
    person = get_person(db, person_id)
    try:
        account = attach_account(db, person, data)
        db.commit()
    except ConflictError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, 'Login email is already in use') from exc
    return account


@router.put('/people/{person_id}/photo', 
            response_model=PersonRead, 
            dependencies=[Depends(require_any_role('admin', 'it'))])
async def upload_photo(person_id: UUID, file: UploadFile, db: Db):
    person = get_person(db, person_id)

    extension = PHOTO_TYPES.get(file.content_type or '')
    if extension is None:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            'Only JPEG, PNG, and WebP images are supported',
        )

    PHOTO_DIRECTORY.mkdir(parents=True, exist_ok=True)
    filename = f'{person.id.hex}{extension}'
    stored_path = PHOTO_DIRECTORY / filename
    size = 0
    old_photo_path = person.photo_path
    try:
        with stored_path.open('wb') as destination:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_PHOTO_BYTES:
                    raise HTTPException(
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        'Photo must not exceed 5 MiB',
                    )
                destination.write(chunk)

        if size == 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Photo cannot be empty')

        person.photo_path = f'/media/people/{filename}'
        db.flush()
        db.commit()
    except HTTPException:
        db.rollback()
        stored_path.unlink(missing_ok=True)
        raise
    except Exception:
        db.rollback()
        stored_path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    # Delete old photo if name differs from new one
    if old_photo_path and old_photo_path.startswith('/media/people/'):
        old_path = PHOTO_DIRECTORY / Path(old_photo_path).name
        if old_path != stored_path:
            old_path.unlink(missing_ok=True)

    return person
#=====================================================
