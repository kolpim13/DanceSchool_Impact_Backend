import hashlib
import hmac
import time
from datetime import datetime
from urllib.parse import urlsplit, parse_qsl

import httpx
from .config import Settings


class SyncError(Exception):
    """Only fixed, non-secret error categories should be supplied."""


FIELDS = "id,message,created_time,permalink_url,full_picture,privacy"


def safe_url(value, *, facebook_only=False):
    if not isinstance(value, str):
        return None
    try:
        url = urlsplit(value)
        host = url.hostname or ""
        if url.scheme != "https" or not host or url.username or url.password:
            return None
        if any(k.lower() in {"access_token", "appsecret_proof"}
               for k, _ in parse_qsl(url.query)):
            return None
        if facebook_only and not (host == "facebook.com" or host.endswith(".facebook.com")):
            return None
        return value
    except ValueError:
        return None


def normalize(raw):
    privacy = raw.get("privacy")

    if not isinstance(privacy, dict):
        raise SyncError("missing_audience_information")

    audience = privacy.get("value")

    if not isinstance(audience, str):
        raise SyncError("invalid_audience_information")

    # Exclude explicit nonpublic audiences.
    # An empty string means the audience is unspecified in this response.
    if audience not in {"", "EVERYONE"}:
        return None

    # Exclude explicit audience restrictions even if value is empty.
    if any(privacy.get(field) for field in ("allow", "deny", "friends")):
        return None
    
    try:
        post_id = raw["id"]
        published = datetime.fromisoformat(raw["created_time"].replace("Z", "+00:00"))
        link = safe_url(raw["permalink_url"], facebook_only=True)
        if not isinstance(post_id, str) or not post_id or not link or published.tzinfo is None:
            raise ValueError
        message = raw.get("message") or ""
        if not isinstance(message, str):
            raise ValueError
        return dict(external_id=post_id, text=message,
                    published_at=int(published.timestamp()), permalink=link,
                    preview_url=safe_url(raw.get("full_picture")))
    except (KeyError, TypeError, ValueError, AttributeError):
        raise SyncError("invalid_post_payload") from None


def request_json(client, url, params):
    for attempt in range(3):
        try:
            response = client.get(url, params=params)
        except httpx.RequestError:
            if attempt == 2:
                raise SyncError("network_error") from None
            time.sleep(2 ** attempt)
            continue
        try:
            payload = response.json()
        except ValueError:
            payload = None
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        if not isinstance(error, dict):
            error = {}
        code = error.get("code")
        if code == 190 or response.status_code == 401:
            raise SyncError("reauthorization_required")
        if code in {10, 200} or response.status_code == 403:
            raise SyncError("permission_denied")
        retryable = (response.status_code == 429 or response.status_code >= 500
                     or code in {4, 17, 32, 613} or error.get("is_transient") is True)
        if retryable:
            if attempt == 2:
                raise SyncError("upstream_temporarily_unavailable")
            try:
                delay = min(60, max(1, int(response.headers.get("Retry-After", 2 ** attempt))))
            except ValueError:
                delay = 2 ** attempt
            time.sleep(delay)
            continue
        if not response.is_success or error:
            raise SyncError("meta_request_rejected")
        if not isinstance(payload, dict):
            raise SyncError("invalid_meta_response")
        return payload
    raise SyncError("upstream_temporarily_unavailable")


def fetch_snapshot(settings: Settings, token: str, transport=None):
    """Complete the API's accessible published-post collection, then sort.

    Do not assume the first Graph page is chronological or complete.
    A scan cap or interrupted pagination aborts without replacing the cache.
    This cannot recover posts that Meta itself does not expose through this edge.
    """
    params = {"fields": FIELDS, "limit": "100"}
    if settings.app_secret:
        params["appsecret_proof"] = hmac.new(
            settings.app_secret.get_secret_value().encode(), token.encode(), hashlib.sha256
        ).hexdigest()
    url = (f"https://graph.facebook.com/{settings.graph_version}/"
           f"{settings.page_id}/published_posts")
    posts, cursors = {}, set()
    with httpx.Client(headers={"Authorization": f"Bearer {token}"},
                      timeout=httpx.Timeout(30, connect=10),
                      follow_redirects=False, transport=transport) as client:
        for _ in range(settings.max_scan_pages):
            payload = request_json(client, url, params)
            data = payload.get("data")
            if not isinstance(data, list):
                raise SyncError("invalid_meta_response")
            for raw in data:
                if not isinstance(raw, dict):
                    raise SyncError("invalid_post_payload")
                post = normalize(raw)
                if post:
                    posts[post["external_id"]] = post
            paging = payload.get("paging") or {}
            if not isinstance(paging, dict):
                raise SyncError("invalid_pagination")
            if not paging.get("next"):
                return sorted(posts.values(), key=lambda p: (p["published_at"], p["external_id"]),
                              reverse=True)[:settings.max_posts]
            cursor = (paging.get("cursors") or {}).get("after")
            if not isinstance(cursor, str) or not cursor or cursor in cursors:
                raise SyncError("invalid_pagination")
            cursors.add(cursor)
            # Never follow paging.next: it can contain a token. Rebuild a fixed-host request.
            params["after"] = cursor
    raise SyncError("scan_limit_reached")
