from typing import Optional

from ..settings import settings
from .base import AuthUser
from .passwords import verify_password


def authenticate_local(username: str, password: str) -> Optional[AuthUser]:
    for user in settings.local_users:
        if user.username == username and verify_password(password, user.password_hash):
            return AuthUser(username=user.username, provider="local", email=None)
    return None
