"""Per-user API key management.

Session-cookie auth only, by design. If an API key could mint another API key,
a leaked key would be self-renewing and permanent: the holder simply creates a
replacement before the stolen one is revoked. Requiring a browser session also
keeps CSRF meaningful here, since the CSRF middleware exempts valid API keys.

Ownership is enforced in SQL rather than in this module, so a mistake in a
handler cannot expose another user's keys. Cross-user access returns 404 rather
than 403 so key ids do not leak existence.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..api_keys import (
    api_keys_available,
    decorate_key,
    expiry_from_days,
    generate_key,
    invalidate_user,
    list_keys_for,
)
from ..auth import get_current_user_optional
from ..auth_providers.base import AuthUser
from ..persistence.factory import get_designs_repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["api-keys"])


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    expires_in_days: Optional[int] = Field(default=None, ge=0, le=3650)


class ApiKeyRename(BaseModel):
    name: str = Field(min_length=1, max_length=64)


async def require_session_user(
    user: Optional[AuthUser] = Depends(get_current_user_optional),
) -> AuthUser:
    """A real, logged-in person holding a browser session."""
    if not api_keys_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API keys require persistence to be configured (set DATABASE)",
        )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    if user.auth_method == "api_key":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API keys cannot manage API keys; sign in to the web UI",
        )
    if user.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No user record for this session; sign out and back in",
        )
    return user


@router.get("/api-keys")
async def list_api_keys(
    all: bool = Query(default=False),
    user_id: Optional[int] = Query(default=None),
    user: AuthUser = Depends(require_session_user),
):
    if all or user_id is not None:
        if not user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
            )
        return {"keys": list_keys_for(None if all else user_id)}
    return {"keys": list_keys_for(user.user_id)}


@router.post("/api-keys", status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreate, user: AuthUser = Depends(require_session_user)
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    token, key_hash, key_prefix = generate_key()
    try:
        row = get_designs_repository().create_api_key(
            user_id=int(user.user_id or 0),
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            expires_at=expiry_from_days(payload.expires_in_days),
        )
    except Exception as exc:  # unique (user_id, name) among live keys
        if "UNIQUE" in str(exc).upper():
            raise HTTPException(
                status_code=409, detail=f"You already have a key named {name!r}"
            ) from exc
        raise
    if row is None:
        raise HTTPException(status_code=500, detail="Failed to create API key")

    out = decorate_key(row)
    # The only time the plaintext is ever returned.
    out["key"] = token
    return out


@router.patch("/api-keys/{key_id}")
async def rename_api_key(
    key_id: int, payload: ApiKeyRename, user: AuthUser = Depends(require_session_user)
):
    repo = get_designs_repository()
    scope = None if user.is_admin else user.user_id
    if not repo.rename_api_key(key_id, payload.name.strip(), user_id=scope):
        raise HTTPException(status_code=404, detail="API key not found")
    row = repo.get_api_key(key_id)
    if row is None:
        raise HTTPException(status_code=404, detail="API key not found")
    return decorate_key(row)


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(key_id: int, user: AuthUser = Depends(require_session_user)):
    repo = get_designs_repository()
    scope = None if user.is_admin else user.user_id
    existing = repo.get_api_key(key_id)
    if not repo.revoke_api_key(key_id, user_id=scope):
        # Already revoked, or not yours. Both are "not found" to the caller.
        raise HTTPException(status_code=404, detail="API key not found")
    if existing and existing.get("user_id") is not None:
        # Make revocation take effect immediately in this process.
        invalidate_user(int(existing["user_id"]))
    return {"message": "API key revoked"}


@router.get("/users")
async def list_users(user: AuthUser = Depends(require_session_user)):
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return {"users": get_designs_repository().list_users()}
