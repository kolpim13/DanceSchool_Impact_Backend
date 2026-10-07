"""Manual live update + terminal/JSON diagnostic. Never dumps unrelated tables."""
import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from .config import get_settings
from app.db.session import SessionLocal
from .facebook import SyncError
from .models import FacebookConnection, FacebookPost, FacebookSyncState
from .sync import synchronize

# Explicit allowlists keep future secret columns out of diagnostics by default.
POST_FIELDS = ("page_id", "external_id", "text", "published_at", "permalink", "preview_url")
STATE_FIELDS = ("page_id", "last_attempt_at", "last_success_at", "last_error")
CONNECTION_FIELDS = (
    "page_id", "page_name", "facebook_user_id", "connected_by", "user_expires_at",
    "user_data_expires_at", "page_expires_at", "page_data_expires_at", "connected_at",
    "last_checked_at", "last_reacquired_at", "status", "last_error",
)


def fields(row, names):
    return {name: getattr(row, name) for name in names} if row is not None else None


def database_snapshot(settings, session_factory=SessionLocal):
    with session_factory() as db:
        # The shared engine begins the read transaction before the first SELECT.
        connection = db.get(FacebookConnection, settings.page_id)
        state = db.get(FacebookSyncState, settings.page_id)
        posts = db.scalars(select(FacebookPost).where(
            FacebookPost.page_id == settings.page_id).order_by(
                FacebookPost.published_at.desc(), FacebookPost.external_id.desc())).all()
        metadata = fields(connection, CONNECTION_FIELDS)
        if metadata is not None:
            metadata["user_token_ciphertext"] = "[REDACTED]" if connection.user_token_ciphertext else None
            metadata["page_token_ciphertext"] = "[REDACTED]" if connection.page_token_ciphertext else None
        return {
            "page_id": settings.page_id,
            "connection": metadata,
            "sync_state": fields(state, STATE_FIELDS),
            "post_count": len(posts),
            "posts": [fields(post, POST_FIELDS) for post in posts],
        }


def write_json_atomic(path, text):
    """Replace the export only after the full UTF-8 file is written successfully."""
    path = Path(path)
    descriptor, temporary = tempfile.mkstemp(prefix=".facebook-export-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(text + "\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def update_and_export(settings, output_path, session_factory=SessionLocal, transport=None):
    result = {"ok": False, "error": None, "updated_posts": None}
    try:
        result["updated_posts"] = synchronize(settings, session_factory, transport)
        result["ok"] = True
    except SyncError as exc:
        result["error"] = str(exc)
    except Exception:
        result["error"] = "configuration_or_database_error"
    # On a failed update, export surviving cache and explicit failure metadata.
    report = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "update": result,
        **database_snapshot(settings, session_factory),
    }
    text = json.dumps(report, indent=2, ensure_ascii=False)
    write_json_atomic(output_path, text)
    print(text)
    return 0 if result["ok"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("facebook_dump.json"))
    args = parser.parse_args()
    try:
        return update_and_export(get_settings(), args.output)
    except Exception:
        # A broken database/configuration or unwritable destination cannot produce a dump.
        print("Diagnostic failed: configuration_database_or_export_error")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
