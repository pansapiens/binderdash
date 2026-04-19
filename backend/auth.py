import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import Depends, HTTPException, Request, Response, status
from jose import JWTError, jwt

from .auth_providers.base import AuthUser
from .settings import SECRET_KEY, settings

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
COOKIE_NAME = "binderdash_session"
CSRF_COOKIE_NAME = "binderdash_csrf"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def set_auth_cookie(
    response: Response, token: str, expires_delta: Optional[timedelta] = None
):
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        expires=expire,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
    )


def clear_auth_cookie(response: Response):
    response.delete_cookie(
        key=COOKIE_NAME, path="/", httponly=True, secure=False, samesite="lax"
    )


def get_token_from_cookie(request: Request) -> Optional[str]:
    return request.cookies.get(COOKIE_NAME)


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, token: str):
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,
        secure=False,
        samesite="lax",
        path="/",
    )


def clear_csrf_cookie(response: Response):
    response.delete_cookie(key=CSRF_COOKIE_NAME, path="/", secure=False, samesite="lax")


def _claims_to_user(sub: str, provider: str, email: Optional[str]) -> AuthUser:
    if provider == "local":
        if not any(u.username == sub for u in settings.local_users):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return AuthUser(username=sub, provider="local", email=None)
    if provider == "pam":
        if not settings.pam_local_enabled or not settings.is_pam_user_allowed(sub):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return AuthUser(username=sub, provider="pam", email=None)
    if provider == "google":
        em = (email or sub or "").strip()
        if not settings.google_auth_enabled or not settings.is_google_user_allowed(em):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return AuthUser(username=em, provider="google", email=em)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _decode_user_from_payload(payload: dict[str, Any]) -> AuthUser:
    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    provider = payload.get("provider") or "local"
    email = payload.get("email")
    if email is not None and not isinstance(email, str):
        email = str(email)
    return _claims_to_user(str(sub), str(provider), email)


async def get_current_user(request: Request) -> AuthUser:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = get_token_from_cookie(request)
    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return _decode_user_from_payload(payload)
    except HTTPException:
        raise
    except JWTError:
        raise credentials_exception


async def get_current_active_user(current_user: AuthUser = Depends(get_current_user)):
    return current_user


async def get_current_user_optional(request: Request):
    if settings.auth_disabled:
        return None

    token = get_token_from_cookie(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await get_current_user(request)


async def get_current_user_optional_with_query(
    request: Request,
    token: Optional[str] = None,
):
    if settings.auth_disabled:
        return None

    cookie_token = get_token_from_cookie(request)
    if cookie_token:
        try:
            return await get_current_user(request)
        except Exception:
            pass

    if token:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return _decode_user_from_payload(payload)
        except (JWTError, HTTPException):
            pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def record_login_audit(user: AuthUser) -> None:
    try:
        from .persistence.factory import get_designs_repository

        repo = get_designs_repository()
        ident = user.email if user.provider == "google" else user.username
        repo.record_login(user.provider, ident, user.email)
    except RuntimeError:
        pass
    except Exception:
        logger.exception("record_login failed")


def issue_session_cookies(response: Response, user: AuthUser) -> str:
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    token_data: dict[str, Any] = {
        "sub": user.username,
        "provider": user.provider,
    }
    if user.email:
        token_data["email"] = user.email
    access_token = create_access_token(
        data=token_data,
        expires_delta=access_token_expires,
    )
    set_auth_cookie(response, access_token, access_token_expires)
    csrf = generate_csrf_token()
    set_csrf_cookie(response, csrf)
    record_login_audit(user)
    return csrf
