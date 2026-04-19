import asyncio
import logging
from typing import Optional

from ..settings import settings
from .base import AuthUser

logger = logging.getLogger(__name__)


def _pam_authenticate(username: str, password: str, service: str) -> bool:
    try:
        import pam
    except ImportError:
        logger.error("python-pam is not installed")
        return False
    try:
        return bool(pam.authenticate(username, password, service=service))
    except Exception:
        logger.exception(
            "PAM authentication error for user %r (service=%r)", username, service
        )
        return False


async def authenticate_pam(username: str, password: str) -> Optional[AuthUser]:
    if not settings.pam_local_enabled:
        return None
    if not settings.is_pam_user_allowed(username):
        return None
    svc = settings.pam_local_service
    ok = await asyncio.to_thread(_pam_authenticate, username, password, svc)
    if not ok:
        logger.info(
            "PAM rejected user %r (service=%r). Wrong password, user not in "
            "PAM_LOCAL_ALLOWED_USERS, user missing from this system's passwd "
            "(typical in Docker: only the image users exist), or unsuitable service "
            "(try PAM_LOCAL_SERVICE=common-auth).",
            username,
            svc,
        )
        return None
    return AuthUser(username=username, provider="pam", email=None)
