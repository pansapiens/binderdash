"""Per-user API keys: generation, storage format, and request validation.

Storage is a plain SHA-256 of the token, deliberately *not* bcrypt/argon2:

1. The token is 256 bits of CSPRNG output, so there is no dictionary to attack
   and a KDF work factor buys nothing. Work factors exist to slow offline
   guessing of low-entropy, human-chosen passwords.
2. A KDF cannot be indexed. Verifying would mean loading every key row and
   running a ~100 ms hash against each until one matched -- on a path that runs
   for every mutating request, behind a single global SQLite lock.

Only the hash and a short display prefix are kept, which is why the token is
shown exactly once, at creation.

Validation is cached, because ``request_has_valid_api_key`` is called from the
CSRF middleware on every mutating request and again from the auth dependency.
Steady state for an API-key request is one dict lookup and zero database I/O.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

KEY_PREFIX = "bd_"
PREFIX_DISPLAY_LEN = 12

# Cross-process revocation lag is bounded by POSITIVE_TTL; in-process it is
# immediate, because the create/revoke endpoints invalidate directly.
POSITIVE_TTL_SECONDS = 30.0
NEGATIVE_TTL_SECONDS = 5.0
MAX_NEGATIVE_ENTRIES = 1024
LAST_USED_INTERVAL_SECONDS = 60.0

_MISS = object()


@dataclass(frozen=True)
class ApiKeyPrincipal:
    """An authenticated API-key holder. Never carries the token itself."""

    key_id: int
    user_id: int
    username: str
    provider: str
    email: Optional[str]
    display_name: Optional[str]
    is_admin: bool


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _sql_timestamp(dt: datetime) -> str:
    """Match the `datetime('now')` format every other table uses."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _parse_sql_timestamp(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip().replace("T", " ")
    if text.endswith("Z"):
        text = text[:-1]
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def generate_key() -> tuple[str, str, str]:
    """Return (token, sha256_hex, display_prefix)."""
    token = KEY_PREFIX + secrets.token_urlsafe(32)
    return token, hash_key(token), token[:PREFIX_DISPLAY_LEN]


def hash_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def expiry_from_days(days: Optional[int]) -> Optional[str]:
    """Convert an ``expires_in_days`` request field to a stored timestamp.

    Done server-side so a skewed client clock cannot mint a key that outlives
    what the user asked for.
    """
    if days is None:
        return None
    return _sql_timestamp(utc_now() + timedelta(days=int(days)))


def key_status(
    revoked_at: Any, expires_at: Any, now: Optional[datetime] = None
) -> str:
    """Derived, never stored, so status can't drift from the timestamps."""
    if revoked_at:
        return "revoked"
    exp = _parse_sql_timestamp(expires_at)
    if exp is not None and exp <= (now or utc_now()):
        return "expired"
    return "active"


def decorate_key(row: Dict[str, Any]) -> Dict[str, Any]:
    """Add the derived status to a repository key row for API output."""
    out = dict(row)
    out.pop("key_hash", None)
    out["status"] = key_status(row.get("revoked_at"), row.get("expires_at"))
    return out


# --- caches ---------------------------------------------------------------

_lock = threading.Lock()
_positive: Dict[str, tuple[float, ApiKeyPrincipal]] = {}
_negative: Dict[str, float] = {}
_dirty_last_used: Dict[int, str] = {}
_next_flush = 0.0


def reset_cache() -> None:
    """Drop all cached state. Exported for tests (module-level globals)."""
    global _next_flush
    with _lock:
        _positive.clear()
        _negative.clear()
        _dirty_last_used.clear()
        _next_flush = 0.0


def invalidate_key_hash(key_hash: str) -> None:
    with _lock:
        _positive.pop(key_hash, None)
        _negative.pop(key_hash, None)


def invalidate_user(user_id: int) -> None:
    """Drop every cached key for a user (revocation, admin change, deletion)."""
    with _lock:
        stale = [h for h, (_, p) in _positive.items() if p.user_id == user_id]
        for h in stale:
            _positive.pop(h, None)


def _cache_get(key_hash: str) -> Any:
    now = time.monotonic()
    with _lock:
        hit = _positive.get(key_hash)
        if hit is not None:
            if hit[0] > now:
                return hit[1]
            _positive.pop(key_hash, None)
        neg = _negative.get(key_hash)
        if neg is not None:
            if neg > now:
                return None
            _negative.pop(key_hash, None)
    return _MISS


def _cache_put(key_hash: str, principal: Optional[ApiKeyPrincipal]) -> None:
    now = time.monotonic()
    with _lock:
        if principal is None:
            # Bounded so a token-spraying client cannot grow this without limit.
            if len(_negative) >= MAX_NEGATIVE_ENTRIES:
                for old in list(_negative)[: MAX_NEGATIVE_ENTRIES // 4]:
                    _negative.pop(old, None)
            _negative[key_hash] = now + NEGATIVE_TTL_SECONDS
        else:
            _positive[key_hash] = (now + POSITIVE_TTL_SECONDS, principal)


# --- last_used_at debounce -------------------------------------------------


def _mark_used(key_id: int) -> None:
    """Queue a last_used_at stamp; flushed in batches, never on the hot path."""
    global _next_flush
    now = time.monotonic()
    due = False
    with _lock:
        _dirty_last_used[key_id] = _sql_timestamp(utc_now())
        if now >= _next_flush:
            _next_flush = now + LAST_USED_INTERVAL_SECONDS
            due = True
    if due:
        threading.Thread(target=flush_last_used, daemon=True).start()


def flush_last_used() -> int:
    """Write queued last_used_at stamps. Safe to call at shutdown."""
    with _lock:
        if not _dirty_last_used:
            return 0
        items = [{"id": k, "last_used_at": v} for k, v in _dirty_last_used.items()]
        _dirty_last_used.clear()
    try:
        from .persistence.factory import get_designs_repository

        return get_designs_repository().touch_api_keys_last_used(items)
    except Exception:
        logger.exception("Failed to flush api key last_used_at")
        return 0


# --- validation ------------------------------------------------------------


def api_keys_available() -> bool:
    """False when there is no user store to hold keys, or auth is off."""
    from .settings import settings

    if settings.auth_disabled:
        return False
    try:
        from .persistence.factory import get_designs_repository

        return get_designs_repository().is_enabled()
    except Exception:
        return False


def _lookup(token: str) -> Optional[ApiKeyPrincipal]:
    digest = hash_key(token)
    cached = _cache_get(digest)
    if cached is not _MISS:
        if cached is not None:
            _mark_used(cached.key_id)
        return cached

    principal: Optional[ApiKeyPrincipal] = None
    try:
        from .persistence.factory import get_designs_repository

        row = get_designs_repository().get_api_key_by_hash(digest)
    except Exception:
        logger.exception("API key lookup failed")
        return None

    if row is not None and row.get("is_active", True):
        status = key_status(row.get("revoked_at"), row.get("expires_at"))
        if status == "active":
            principal = ApiKeyPrincipal(
                key_id=int(row["id"]),
                user_id=int(row["user_id"]),
                username=str(
                    row.get("user_email") or row.get("identifier") or row["user_id"]
                ),
                provider=str(row.get("provider") or "local"),
                email=row.get("user_email"),
                display_name=row.get("user_display_name"),
                is_admin=bool(row.get("is_admin")),
            )
        else:
            logger.info("Rejected %s API key id=%s", status, row.get("id"))

    _cache_put(digest, principal)
    if principal is not None:
        _mark_used(principal.key_id)
    return principal


def principal_for_token(token: str) -> Optional[ApiKeyPrincipal]:
    """Authenticate a bare token, for callers with no ``Request`` to memoise on.

    The MCP server's TokenVerifier gets a token, not a request. Routing it through
    ``_lookup`` keeps one TTL cache and one ``last_used_at`` debounce per process, so
    revoking a key takes effect for MCP and REST at the same moment.
    """
    token = (token or "").strip()
    if not token or not api_keys_available():
        return None
    return _lookup(token)


def token_from_request(request: Any) -> Optional[str]:
    header_key = (request.headers.get("X-Binderdash-Api-Key") or "").strip()
    if header_key:
        return header_key
    auth = (request.headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def resolve_principal(request: Any) -> Optional[ApiKeyPrincipal]:
    """Authenticate a request by API key, memoised for the request's lifetime.

    The CSRF middleware and the auth dependency both call this; without the
    ``request.state`` memo that would be two lookups per mutating request.
    """
    cached = getattr(request.state, "api_key_principal", _MISS)
    if cached is not _MISS:
        return cached if isinstance(cached, ApiKeyPrincipal) else None

    principal: Optional[ApiKeyPrincipal] = None
    token = token_from_request(request)
    if token and api_keys_available():
        principal = _lookup(token)
    try:
        request.state.api_key_principal = principal
    except Exception:
        pass
    return principal


def list_keys_for(user_id: Optional[int]) -> List[Dict[str, Any]]:
    from .persistence.factory import get_designs_repository

    rows = get_designs_repository().list_api_keys(user_id)
    return [decorate_key(r) for r in rows]
