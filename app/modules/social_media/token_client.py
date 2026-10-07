"""Meta OAuth and token validation. No generic refresh-token grant is used."""

import hashlib
import hmac
import logging
import time
from urllib.parse import urlencode

import httpx

from .facebook import SyncError


# OAuth requests may carry credentials in query parameters.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

SCOPES = {
    "pages_show_list",
    "pages_read_engagement",
}


def request_stage(path, params, page_id):
    """Return a fixed diagnostic label without exposing request parameters."""
    if path == "oauth/access_token":
        return "exchange_code" if "code" in params else "extend_user_token"
    if path == "debug_token":
        return "inspect_token"
    if path == page_id:
        return "get_page_token"
    if path == "me":
        return "verify_page_identity"
    return "token_request"


def rejection_hint(error):
    """Inspect Meta's message but output only a predefined, non-secret hint."""
    message = error.get("message", "") if isinstance(error, dict) else ""
    message = message.lower() if isinstance(message, str) else ""
    if "redirect_uri" in message or "redirect uri" in message:
        return "check_exact_redirect_uri"
    if "client secret" in message or "app secret" in message or "client_secret" in message:
        return "check_app_id_and_secret_pair"
    if "verification code" in message or "authorization code" in message:
        return "restart_connect_for_a_fresh_code"
    if "unsupported get request" in message:
        return "check_page_id_and_page_access"
    if "nonexisting field" in message or "non-existing field" in message:
        return "check_fields_and_graph_version"
    if "permission" in message:
        return "check_permissions_and_page_assignment"
    return "inspect_stage_and_numeric_codes"


def report_rejection(stage, status, error):
    """Log stage, HTTP status, numeric codes, and a safe hint."""

    def number(field):
        value = error.get(field) if isinstance(error, dict) else None
        if type(value) is int and 0 <= value <= 2147483647:
            return value
        return "unknown"

    logger.warning(
        "Meta request failed: "
        "stage=%s http=%s code=%s subcode=%s hint=%s",
        stage,
        status,
        number("code"),
        number("error_subcode"),
        rejection_hint(error),
    )


def authorize_url(settings, state):
    params = {
        "client_id": settings.app_id,
        "redirect_uri": settings.redirect_uri,
        "state": state,
        "response_type": "code",
    }

    if settings.login_config_id:
        params["config_id"] = settings.login_config_id
    else:
        params.update(
            scope=",".join(sorted(SCOPES)),
            auth_type="rerequest",
        )

    return f"https://www.facebook.com/{settings.graph_version}/dialog/oauth?{urlencode(params)}"


def expiration(data, field):
    """Convert explicit zero expiry to None; reject missing/invalid metadata."""
    value = data.get(field)

    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise SyncError("invalid_token_metadata")
    # No scheduled expiration does not guarantee permanent access.
    return value or None


def live(data):
    if data.get("is_valid") is not True:
        return False

    now = int(time.time())

    return all(expiration(data, field) is None or expiration(data, field) > now
               for field in ("expires_at", "data_access_expires_at"))


class MetaTokens:
    def __init__(self, settings, transport=None):
        self.s = settings
        self.root = f"https://graph.facebook.com/{settings.graph_version}"
        self.http = httpx.Client(
            timeout=httpx.Timeout(30, connect=10),
            follow_redirects=False,
            transport=transport,
        )

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.http.close()

    def get(self, path, params=None, token=None, proof=True):
        params = dict(params or {})
        headers = {}

        if token:
            headers["Authorization"] = f"Bearer {token}"

            if proof:
                params["appsecret_proof"] = hmac.new(
                    self.s.app_secret.get_secret_value().encode(),
                    token.encode(),
                    hashlib.sha256,
                ).hexdigest()

        try:
            response = self.http.get(
                f"{self.root}/{path}",
                params=params,
                headers=headers,
            )
        except httpx.RequestError:
            raise SyncError("token_network_error") from None

        try:
            body = response.json()
        except ValueError:
            raise SyncError("invalid_token_response") from None
        error = body.get("error") if isinstance(body, dict) else None
        code = error.get("code") if isinstance(error, dict) else None
        if not response.is_success or error or not isinstance(body, dict):
            report_rejection(
                request_stage(path, params, self.s.page_id),
                response.status_code,
                error,
            )

        if response.status_code >= 500 or response.status_code == 429 or code in {4, 17, 32, 613}:
            raise SyncError("token_service_unavailable")
        if code == 190 or response.status_code == 401:
            raise SyncError("reauthorization_required")
        if code in {10, 200} or response.status_code == 403:
            raise SyncError("permission_denied")
        if not response.is_success or error or not isinstance(body, dict):
            raise SyncError("token_request_rejected")
        return body

    def token(self, body):
        token = body.get("access_token")
        if not isinstance(token, str) or not token:
            raise SyncError("missing_token")
        return token

    def from_code(self, code):
        common = {
            "client_id": self.s.app_id,
            "client_secret": self.s.app_secret.get_secret_value(),
        }

        # Do not blindly retry a potentially consumed authorization code.
        short = self.token(self.get("oauth/access_token", {
            **common,
            "redirect_uri": self.s.redirect_uri,
            "code": code,
        }))
        return self.token(self.get("oauth/access_token", {
            **common,
            "grant_type": "fb_exchange_token",
            "fb_exchange_token": short,
        }))

    def inspect(self, token, kind):
        app_token = f"{self.s.app_id}|{self.s.app_secret.get_secret_value()}"
        data = self.get("debug_token", {"input_token": token}, app_token, proof=False).get("data")
        if not isinstance(data, dict):
            raise SyncError("invalid_token_metadata")
        if data.get("is_valid") is not True:
            return data
        if str(data.get("app_id")) != self.s.app_id or data.get("type") != kind:
            raise SyncError("token_identity_mismatch")
        expiration(data, "expires_at")
        expiration(data, "data_access_expires_at")
        scopes = data.get("scopes")
        needed = SCOPES if kind == "USER" else {"pages_read_engagement"}
        if not isinstance(scopes, list) or not needed.issubset(set(scopes)):
            raise SyncError("permission_denied")
        if kind == "USER" and not data.get("user_id"):
            raise SyncError("invalid_token_metadata")
        return data

    def page_from_user(self, user_token):
        body = self.get(self.s.page_id, {"fields": "id,name,access_token"}, user_token)
        if str(body.get("id")) != self.s.page_id:
            raise SyncError("wrong_page")
        token = self.token(body)
        info = self.inspect(token, "PAGE")
        if not live(info):
            raise SyncError("reauthorization_required")
        # Verify that the token represents the configured Page.
        identity = self.get("me", {"fields": "id"}, token)
        if str(identity.get("id")) != self.s.page_id:
            raise SyncError("wrong_page")
        return token, info, str(body.get("name") or "")