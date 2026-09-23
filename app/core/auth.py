import hashlib
from datetime import datetime, timezone
from typing import Annotated
from urllib.parse import urlsplit
from uuid import UUID
from fastapi import Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.core.config import settings
from app.db.session import get_db
from app.modules.people.models import Account, LoginSession


Db = Annotated[Session, Depends(get_db)]
SESSION_COOKIE = 'impact_session'
SESSION_COOKIE_PATH = '/'
SESSION_COOKIE_SAMESITE = 'lax'


def current_account(request: Request, db: Db) -> Account:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Authentication required')

    session = db.scalar(
        select(LoginSession)
        .options(joinedload(LoginSession.account))
        .where(LoginSession.token_hash == hashlib.sha256(token.encode('utf-8')).hexdigest())
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if (
        session is None or session.revoked_at is not None
        or session.expires_at <= now or session.account.status != 'active'
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Invalid or expired session')
    return session.account


def require_any_role(*names: str):
    allowed = set(names)
    def check(account: Annotated[Account, Depends(current_account)]) -> Account:
        if not allowed.intersection(role.name for role in account.roles):
            raise HTTPException(403, 'Role not allowed')
        return account
    return check


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE, token, httponly=True, secure=True,
        samesite=SESSION_COOKIE_SAMESITE, path=SESSION_COOKIE_PATH,
        max_age=settings.session_days * 24 * 60 * 60,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE, path=SESSION_COOKIE_PATH,
        samesite=SESSION_COOKIE_SAMESITE, secure=True,
    )


def _origin_of(header_value: str) -> str:
    parts = urlsplit(header_value)
    return f'{parts.scheme}://{parts.netloc}' if parts.scheme and parts.netloc else header_value


def verify_trusted_origin(request: Request) -> None:
    # SameSite alone does not block every cross-site submission path, so pin state-changing requests to configured website origins.
    header_value = request.headers.get('origin') or request.headers.get('referer')
    if not header_value or _origin_of(header_value) not in settings.website_origins:
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Untrusted origin')