"""Interactive operator-only authorization, without an HTTP server or router."""
import getpass
import secrets
import time
import warnings
from urllib.parse import parse_qs, urlsplit

from filelock import FileLock, Timeout
from .config import get_settings
from app.db.session import SessionLocal
from .facebook import SyncError
from .token_client import authorize_url
from .tokens import accept_authorization


def callback_code(settings, returned_url, expected_state, started):
    """Accept only our redirect destination and this process's ten-minute state."""
    if time.monotonic() - started > 600:
        raise SyncError("oauth_attempt_expired")
    try:
        actual, expected = urlsplit(returned_url.strip()), urlsplit(settings.redirect_uri)
        if (actual.scheme, actual.netloc, actual.path) != (expected.scheme, expected.netloc, expected.path):
            raise ValueError
        if actual.fragment or len(returned_url) > 16384:
            raise ValueError
        values = parse_qs(actual.query, keep_blank_values=True, max_num_fields=20)
        state = values.get("state", [])
        if len(state) != 1 or not secrets.compare_digest(state[0], expected_state):
            raise ValueError
        if "error" in values:
            raise SyncError("authorization_cancelled")
        code = values.get("code", [])
        if len(code) != 1 or not code[0] or len(code[0]) > 8192:
            raise ValueError
        return code[0]
    except ValueError:
        raise SyncError("invalid_oauth_callback") from None


def main():
    try:
        settings = get_settings()
        # Serialize initial connection/reconnection with every synchronization.
        # This lock also prevents a second CLI authorization from racing this one.
        with FileLock(settings.lock_path, timeout=0):
            state = secrets.token_urlsafe(32)
            started = time.monotonic()
            print("Open this URL in your browser and authorize the configured Page:")
            print(authorize_url(settings, state))
            print("After Facebook redirects, copy the COMPLETE address-bar URL.")
            print("Paste below within 10 minutes. Input is hidden; press Enter once.")
            # Refuse getpass's insecure echo fallback on noninteractive terminals.
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                returned = getpass.getpass("Returned URL: ")
                print(returned)
            code = callback_code(settings, returned, state, started)
            accept_authorization(settings, SessionLocal, "cli:" + getpass.getuser(), code)
        print("Connected. Run python -m app.modules.social_media.test_sync to fetch and inspect posts.")
        return 0
    except Timeout:
        print("Connection failed: integration_busy")
    except SyncError as exc:
        print(f"Connection failed: {exc}")
    except (EOFError, KeyboardInterrupt):
        print("Connection cancelled.")
    except getpass.GetPassWarning:
        print("Connection failed: use_an_interactive_terminal_with_hidden_input")
    except Exception:
        print("Connection failed: configuration_or_database_error")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
