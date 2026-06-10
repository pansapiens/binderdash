import asyncio
import logging
from pathlib import Path
from typing import Optional

from ..settings import settings
from .base import AuthUser

logger = logging.getLogger(__name__)

try:
    import pwd
except ImportError:
    pwd = None  # type: ignore[assignment]


def _pam_authenticate(username: str, password: str, service: str) -> bool:
    try:
        import pam
    except ImportError:
        logger.error("python-pam is not installed")
        return False
    try:
        client = pam.pam()
        ok = bool(client.authenticate(username, password, service=service))
        if not ok:
            logger.info(
                "PAM authenticate returned false for user %r (service=%r, code=%r, reason=%r)",
                username,
                service,
                getattr(client, "code", None),
                getattr(client, "reason", None),
            )
        return ok
    except Exception:
        logger.exception(
            "PAM authentication error for user %r (service=%r)", username, service
        )
        return False


async def authenticate_pam(username: str, password: str) -> Optional[AuthUser]:
    if pwd is None:
        logger.debug("PAM auth unavailable: pwd module not found on this platform")
        return None
    if not settings.pam_local_enabled:
        logger.debug("PAM auth skipped because PAM_LOCAL_ENABLED is false")
        return None
    if not settings.is_pam_user_allowed(username):
        logger.info(
            "PAM auth rejected before verify: user %r is not in PAM_LOCAL_ALLOWED_USERS=%r",
            username,
            settings.pam_local_allowed_users,
        )
        return None
    svc = settings.pam_local_service
    if not Path(f"/etc/pam.d/{svc}").exists():
        logger.warning("PAM service file is missing: /etc/pam.d/%s", svc)
    try:
        pwd.getpwnam(username)
    except KeyError:
        logger.warning(
            "PAM username %r not present in container /etc/passwd", username
        )
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
