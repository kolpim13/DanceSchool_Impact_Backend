import logging
import time
from filelock import FileLock, Timeout
from sqlalchemy import delete
from .config import get_settings
from app.db.session import SessionLocal
from .facebook import SyncError, fetch_snapshot
from .models import FacebookPost, FacebookSyncState
from .tokens import token_for_sync, mark_failure, AUTH_ERRORS

log = logging.getLogger(__name__)


def record_error(session_factory, page_id, started, category):
    with session_factory.begin() as db:
        state = db.get(FacebookSyncState, page_id)
        if state is None:
            state = FacebookSyncState(page_id=page_id)
            db.add(state)
        state.last_attempt_at = started
        state.last_error = category


def synchronize(settings, session_factory=SessionLocal, transport=None):
    """Single-host lock. Use only this entry point for manual and scheduled syncs."""
    try:
        with FileLock(settings.lock_path, timeout=0):
            started = int(time.time())
            try:
                token = token_for_sync(settings, session_factory, transport)
                try:
                    posts = fetch_snapshot(settings, token, transport)
                except SyncError as exc:
                    if str(exc) not in AUTH_ERRORS:
                        raise
                    # One recovery attempt. No login loops and no refresh-token fiction.
                    token = token_for_sync(settings, session_factory, transport, force=True)
                    posts = fetch_snapshot(settings, token, transport)
            except SyncError as exc:
                mark_failure(settings, session_factory, str(exc))
                record_error(session_factory, settings.page_id, started, str(exc))
                raise
            now = int(time.time())
            # All rows and success state change together, or the transaction rolls back.
            # These are disposable cache rows, with no local editorial fields or references.
            with session_factory.begin() as db:
                db.execute(delete(FacebookPost).where(FacebookPost.page_id == settings.page_id))
                db.add_all(FacebookPost(page_id=settings.page_id, **p) for p in posts)
                state = db.get(FacebookSyncState, settings.page_id)
                if state is None:
                    state = FacebookSyncState(page_id=settings.page_id)
                    db.add(state)
                state.last_attempt_at = started
                state.last_success_at = now
                state.last_error = None
            return len(posts)
    except Timeout:
        raise SyncError("sync_already_running") from None


def refresh_facebook_feed(settings=None, session_factory=SessionLocal, transport=None):
    """Replace stored FacebookPost rows with a fresh snapshot. Never raises.

    Returns the number of stored posts, or None if the refresh failed or was skipped.
    On failure the previous posts are kept.
    """
    try:
        settings = settings or get_settings()
        return synchronize(settings, session_factory, transport)
    except SyncError as exc:
        log.warning("Facebook feed refresh failed: %s", exc)
    except Exception:
        # Avoid logging raw exceptions, which may contain config or URLs.
        log.warning("Facebook feed refresh failed: configuration_or_database_error")
    return None


def main():
    # Avoid request URL/header logging, including proof query parameters.
    import logging
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    try:
        count = synchronize(get_settings())
    except SyncError as exc:
        print(f"Facebook synchronization failed: {exc}")
        return 1
    except Exception:
        # Never print raw exceptions containing config or URLs. Investigate locally.
        print("Facebook synchronization failed: configuration_or_database_error")
        return 1
    print(f"Facebook synchronization complete: {count} posts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

