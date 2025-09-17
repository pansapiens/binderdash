import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, Request, Response, status
from jose import JWTError, jwt

from .settings import SECRET_KEY, settings, LocalUser
from .schemas import TokenData


logger = logging.getLogger(__name__)


ALGORITHM = "HS256"
COOKIE_NAME = "binderdash_session"
CSRF_COOKIE_NAME = "binderdash_csrf"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def authenticate_user(username: str, password: str) -> Optional[LocalUser]:
    for user in settings.local_users:
        if user.username == username and verify_password(password, user.password_hash):
            return user
    return None


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


async def get_current_user(request: Request):
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
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user = None
    for local_user in settings.local_users:
        if local_user.username == token_data.username:
            user = local_user
            break

    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: LocalUser = Depends(get_current_user)):
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
            username = payload.get("sub")
            if username is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            token_data = TokenData(username=username)

            user = None
            for local_user in settings.local_users:
                if local_user.username == token_data.username:
                    user = local_user
                    break
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return user
        except JWTError:
            pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
