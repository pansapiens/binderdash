"""FastMCP server construction, authentication, and the ASGI app Binderdash mounts.

Everything that touches ``fastmcp`` is imported inside a function. ``fastmcp`` is an
optional extra (see ``backend/pyproject.toml``) because it pulls ~30 transitive
distributions that the PyInstaller desktop spec does not declare; when it is absent
``build_mcp_http_app`` returns ``None`` and the app runs exactly as before.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:  # pragma: no cover - typing only, never imported at runtime
    from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

MCP_MOUNT_PATH = "/api/mcp"
MCP_SERVER_NAME = "binderdash"

# Clients that send the Binderdash REST header instead of a bearer token would
# otherwise get an opaque 401 -- FastMCP's auth backend reads Authorization only.
API_KEY_HEADER = b"x-binderdash-api-key"


def mcp_available() -> bool:
    """Whether the optional ``fastmcp`` extra is installed."""
    try:
        import fastmcp  # noqa: F401
    except ImportError:
        return False
    return True


def _build_verifier() -> Any:
    from fastmcp.server.auth import TokenVerifier
    from fastmcp.server.auth.auth import AccessToken

    from ..api_keys import KEY_PREFIX, principal_for_token

    class BinderdashTokenVerifier(TokenVerifier):
        """Validates a per-user Binderdash API key and carries its identity as claims.

        Tools read the identity from ``AccessToken.claims`` rather than looking it up
        again, so an authenticated tool call costs no extra database work.
        """

        async def verify_token(self, token: str) -> Optional[AccessToken]:
            import asyncio

            if not token or not token.startswith(KEY_PREFIX):
                return None
            # A cache miss reads SQLite; never block the event loop for it.
            principal = await asyncio.to_thread(principal_for_token, token)
            if principal is None:
                return None
            return AccessToken(
                token=token,
                client_id=principal.username,
                scopes=[],
                claims={
                    "user_id": principal.user_id,
                    "username": principal.username,
                    "email": principal.email,
                    "display_name": principal.display_name,
                    "is_admin": principal.is_admin,
                    "key_id": principal.key_id,
                },
            )

    return BinderdashTokenVerifier()


class _PromoteApiKeyHeader:
    """Let ``X-Binderdash-Api-Key`` work on MCP requests, as it does on REST ones.

    FastMCP's bearer backend reads ``Authorization`` only, so a client configured with
    the Binderdash header would fail with a bare 401 and no way to tell why. Copies the
    scope rather than mutating the caller's.
    """

    def __init__(self, app: "ASGIApp") -> None:
        self.app = app

    async def __call__(self, scope: "Scope", receive: "Receive", send: "Send") -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = scope.get("headers") or []
        lowered = {name for name, _ in headers}
        if b"authorization" in lowered or API_KEY_HEADER not in lowered:
            await self.app(scope, receive, send)
            return
        token = next(value for name, value in headers if name == API_KEY_HEADER)
        scope = dict(scope)
        scope["headers"] = list(headers) + [(b"authorization", b"Bearer " + token)]
        await self.app(scope, receive, send)


def build_mcp_http_app() -> Optional["ASGIApp"]:
    """The streamable-HTTP ASGI app to mount, or ``None`` when MCP is unavailable.

    The returned app still needs its lifespan run by the host application -- mounting
    alone does not start the streamable-HTTP session manager. See ``backend/main.py``.
    """
    if not mcp_available():
        logger.info("fastmcp is not installed; the MCP server at %s is disabled", MCP_MOUNT_PATH)
        return None

    from fastmcp import FastMCP

    from ..settings import settings
    from .tools import register_tools

    if settings.auth_disabled:
        # api_keys_available() is False when auth is off, so every key would be
        # rejected and the endpoint would be unusable rather than open.
        logger.warning(
            "DISABLE_AUTHENTICATION is set: the MCP server at %s is unauthenticated",
            MCP_MOUNT_PATH,
        )
        mcp = FastMCP(name=MCP_SERVER_NAME)
    else:
        mcp = FastMCP(name=MCP_SERVER_NAME, auth=_build_verifier())

    register_tools(mcp)
    return _PromoteApiKeyHeader(mcp.http_app(path="/", stateless_http=True))


def _heavy_semaphore() -> Any:
    """Lazily created so importing this module does not touch an event loop."""
    global _HEAVY
    if _HEAVY is None:
        import asyncio

        _HEAVY = asyncio.Semaphore(2)
    return _HEAVY


_HEAVY: Any = None


async def run_blocking(fn, *args, heavy: bool = False, **kwargs):
    """Run synchronous service-layer work off the event loop.

    ``heavy=True`` additionally caps concurrency: filtering and diversity selection
    spawn subprocesses and hold the GIL for long stretches, and MCP shares this
    process's default executor with the REST API serving the web UI. An agent's
    tool-calling loop must not starve interactive requests.
    """
    import asyncio
    import functools

    call = functools.partial(fn, *args, **kwargs)
    if not heavy:
        return await asyncio.to_thread(call)
    async with _heavy_semaphore():
        return await asyncio.to_thread(call)


def current_identity() -> dict:
    """The authenticated caller's identity, from the access token's claims."""
    from fastmcp.exceptions import ToolError
    from fastmcp.server.dependencies import get_access_token

    from ..settings import settings

    access = get_access_token()
    if access is None:
        if settings.auth_disabled:
            return {"user_id": None, "username": "anonymous", "is_admin": True}
        raise ToolError(
            "[NOT_AUTHENTICATED] No valid Binderdash API key. Set an Authorization: "
            "Bearer bd_... header in your MCP client config."
        )
    return dict(access.claims or {})
