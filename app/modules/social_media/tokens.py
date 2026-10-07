"""Call mutation functions under the shared synchronization file lock."""
import time
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete
from .facebook import SyncError
from .models import FacebookConnection, FacebookPost, FacebookSyncState
from .token_client import MetaTokens, expiration, live

AUTH_ERRORS = {"reauthorization_required", "permission_denied", "wrong_page", "token_identity_mismatch"}


def cipher(settings):
    return Fernet(settings.token_encryption_key.get_secret_value().encode())


def decrypt(settings, text):
    try:
        return cipher(settings).decrypt((text or "").encode()).decode()
    except (InvalidToken, UnicodeError):
        raise SyncError("token_decryption_failed") from None


def deadline(*values):
    finite = [v for v in values if v is not None]
    return min(finite) if finite else None


def accept_authorization(settings, factory, admin_id, code, transport=None):
    with MetaTokens(settings, transport) as api:
        user_token = api.from_code(code)
        user_info = api.inspect(user_token, "USER")
        if not live(user_info):
            raise SyncError("reauthorization_required")
        page_token, page_info, page_name = api.page_from_user(user_token)
    now = int(time.time())
    with factory.begin() as db:
        row = db.get(FacebookConnection, settings.page_id)
        if row is None:
            row = FacebookConnection(page_id=settings.page_id)
            db.add(row)
        row.page_name = page_name
        row.connected_by = admin_id
        row.facebook_user_id = str(user_info["user_id"])
        row.user_token_ciphertext = cipher(settings).encrypt(user_token.encode()).decode()
        row.page_token_ciphertext = cipher(settings).encrypt(page_token.encode()).decode()
        row.user_expires_at = expiration(user_info, "expires_at")
        row.user_data_expires_at = expiration(user_info, "data_access_expires_at")
        row.page_expires_at = expiration(page_info, "expires_at")
        row.page_data_expires_at = expiration(page_info, "data_access_expires_at")
        row.connected_at = row.last_checked_at = row.last_reacquired_at = now
        row.status, row.last_error = "connected", None
        # Do not re-expose cached content until a fresh sync succeeds.
        db.execute(delete(FacebookPost).where(FacebookPost.page_id == settings.page_id))
        db.execute(delete(FacebookSyncState).where(FacebookSyncState.page_id == settings.page_id))


def mark_failure(settings, factory, category):
    with factory.begin() as db:
        row = db.get(FacebookConnection, settings.page_id)
        if row:
            row.last_error = category
            if category in AUTH_ERRORS:
                row.status = "needs_reconnect"


def token_for_sync(settings, factory, transport=None, force=False):
    """Validate periodically; reacquire only while parent User authorization works.

    Never repeatedly exchange an old long-lived User token as a fake refresh.
    A live Page token continues to work even if its parent User token expires.
    """
    now = int(time.time())
    with factory() as db:
        row = db.get(FacebookConnection, settings.page_id)
        if row is None or row.status == "disconnected":
            raise SyncError("facebook_not_connected")
        if row.status == "needs_reconnect":
            raise SyncError("reauthorization_required")
        page_token = decrypt(settings, row.page_token_ciphertext)
        due = deadline(row.page_expires_at, row.page_data_expires_at)
        if not force and row.last_checked_at and now - row.last_checked_at < settings.token_check_seconds:
            if due is None or due > now:
                return page_token
        # Copy detached scalar values; no long DB transaction during network work.
        user_cipher = row.user_token_ciphertext
        expected_user = row.facebook_user_id
    try:
        with MetaTokens(settings, transport) as api:
            try:
                page_info = api.inspect(page_token, "PAGE")
            except SyncError as exc:
                if str(exc) != "reauthorization_required":
                    raise
                page_info = {"is_valid": False}
            valid = live(page_info)
            due = deadline(expiration(page_info, "expires_at"),
                           expiration(page_info, "data_access_expires_at")) if valid else 0
            renewal_needed = force or not valid or (due is not None and due <= now + settings.renew_before_seconds)
            warning = None
            acquired = False
            user_info = None
            if renewal_needed:
                user_token = decrypt(settings, user_cipher)
                try:
                    user_info = api.inspect(user_token, "USER")
                except SyncError as exc:
                    if str(exc) != "reauthorization_required":
                        raise
                    user_info = {"is_valid": False}
                if live(user_info):
                    if str(user_info["user_id"]) != expected_user:
                        raise SyncError("token_identity_mismatch")
                    page_token, page_info, _ = api.page_from_user(user_token)
                    acquired = True
                    due = deadline(expiration(page_info, "expires_at"),
                                   expiration(page_info, "data_access_expires_at"))
                    # Reacquisition may return the SAME token and deadline. Do not claim renewal.
                    if due is not None and due <= now + settings.renew_before_seconds:
                        warning = "page_expiry_reconnect_recommended"
                elif not valid or force:
                    raise SyncError("reauthorization_required")
                else:
                    warning = "page_expiry_reconnect_recommended"
            with factory.begin() as db:
                row = db.get(FacebookConnection, settings.page_id)
                row.page_token_ciphertext = cipher(settings).encrypt(page_token.encode()).decode()
                row.page_expires_at = expiration(page_info, "expires_at")
                row.page_data_expires_at = expiration(page_info, "data_access_expires_at")
                row.last_checked_at = now
                if acquired:
                    row.last_reacquired_at = now
                if user_info and live(user_info):
                    row.user_expires_at = expiration(user_info, "expires_at")
                    row.user_data_expires_at = expiration(user_info, "data_access_expires_at")
                row.last_error = warning
            return page_token
    except SyncError as exc:
        mark_failure(settings, factory, str(exc))
        raise

