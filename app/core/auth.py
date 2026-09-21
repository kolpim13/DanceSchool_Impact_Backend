import hashlib
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID
from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.db.session import get_db
from app.modules.people.models import Account, LoginSession


Db = Annotated[Session, Depends(get_db)]
SESSION_COOKIE = 'impact_session'


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
    if session is None or session.expires_at <= now or session.account.status != 'active':
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Invalid or expired session')
    return session.account


def require_any_role(*names: str):
    allowed = set(names)
    def check(account: Annotated[Account, Depends(current_account)]) -> Account:
        if not allowed.intersection(role.name for role in account.roles):
            raise HTTPException(403, 'Role not allowed')
        return account
    return check