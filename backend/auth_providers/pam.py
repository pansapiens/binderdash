import asyncio
import logging
import re
from pathlib import Path
from typing import Optional

from ..settings import settings
from .base import AuthUser

logger = logging.getLogger(__name__)

try:
    import pwd
except ImportError:
    pwd = None  # type: ignore[assignment]


# The GECOS "other" field (the 5th), and ONLY that field.
#
# This is a security boundary, not a formatting preference. chfn lets users
# rewrite their own GECOS, and /etc/login.defs CHFN_RESTRICT commonly ships as
# "rwh" -- room, work phone, home phone. There is no chfn flag for the 5th
# field, and chfn preserves it verbatim (it also rejects commas in input, so a
# user cannot smuggle in extra fields). Root is therefore the only writer.
#
# Reading any other field would let any shell user run `chfn` to claim a
# colleague's address and be merged into their Binderdash account, inheriting
# its API keys and admin rights.
GECOS_EMAIL_FIELD = 5

# Applied within that one field, so a trailing note alongside the address is
# tolerated. Both sides are restricted to characters legal in an address, so
# the match stops at whitespace by itself.
_GECOS_EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+!#$&*/=?^`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"
)


def gecos_email(gecos: str) -> Optional[str]:
    """The address in the GECOS "other" field, lowercased.

    Deliberately ignores every other field -- see GECOS_EMAIL_FIELD.
    """
    if not gecos:
        return None
    fields = gecos.split(",")
    if len(fields) < GECOS_EMAIL_FIELD:
        return None
    m = _GECOS_EMAIL_RE.search(fields[GECOS_EMAIL_FIELD - 1])
    return m.group(0).lower() if m else None


def _lookup_gecos_email(username: str) -> Optional[str]:
    """Read a PAM user's email from the root-only GECOS "other" field."""
    if pwd is None or not settings.pam_gecos_email:
        return None
    try:
        entry = pwd.getpwnam(username)
    except KeyError:
        return None
    email = gecos_email(entry.pw_gecos or "")
    if email:
        logger.debug("PAM user %r resolved GECOS email %r", username, email)
    return email


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
    return AuthUser(
        username=username,
        provider="pam",
        email=_lookup_gecos_email(username),
    )
