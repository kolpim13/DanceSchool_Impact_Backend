import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from .config import Settings, get_settings
from app.db.session import SessionLocal
from .models import FacebookPost, FacebookSyncState
#=====================================================

router = APIRouter(tags=["Social feed"])
#=====================================================


class PostRead(BaseModel):
    id: str
    platform: str = "facebook"
    text: str
    published_at: datetime
    permalink: str
    preview_url: str | None


class FeedRead(BaseModel):
    items: list[PostRead]
    last_synced_at: datetime | None
    stale: bool
    available: bool


def read_feed(settings, session_factory, limit, offset):
    with session_factory() as db:
        state = db.get(FacebookSyncState, settings.page_id)
        last = state.last_success_at if state else None
        age = int(time.time()) - last if last is not None else None
        blocked = bool(state and state.last_error in {
            "reauthorization_required", "permission_denied", "missing_audience_information"
        })
        available = age is not None and age <= settings.hide_after_seconds and not blocked
        items = []
        if available:
            total = db.scalar(select(func.count()).select_from(FacebookPost)
                .where(FacebookPost.page_id == settings.page_id))
            # A limit beyond the end simply returns what exists; only a start past the end is an error.
            if offset > 0 and offset >= total:
                raise HTTPException(status_code=416,
                    detail=f"Offset {offset} is out of range; only {total} posts are available")
            rows = db.scalars(select(FacebookPost)
                .where(FacebookPost.page_id == settings.page_id)
                .order_by(FacebookPost.published_at.desc(), FacebookPost.external_id.desc())
                .offset(offset).limit(min(limit, settings.max_posts))).all()
            items = [PostRead(id=row.external_id, text=row.text,
                     published_at=datetime.fromtimestamp(row.published_at, timezone.utc),
                     permalink=row.permalink, preview_url=row.preview_url) for row in rows]
        return FeedRead(items=items,
            last_synced_at=datetime.fromtimestamp(last, timezone.utc) if last is not None else None,
            stale=age is None or age > settings.stale_after_seconds or bool(state and state.last_error),
            available=available)


@router.get("/facebook/posts", response_model=FeedRead)
def list_posts(response: Response, limit: int = Query(6, ge=1, le=100),
               offset: int = Query(0, ge=0, le=500),
               settings: Settings = Depends(get_settings)):
    
    # The DB is the cache. Avoid stale public responses after authorization loss.
    response.headers["Cache-Control"] = "no-store"
    return read_feed(settings, SessionLocal, limit, offset)
