from typing import Annotated
from uuid import UUID
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.modules.people.models import Account


Db = Annotated[Session, Depends(get_db)]