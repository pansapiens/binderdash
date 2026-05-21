import httpx
from authlib.integrations.base_client import OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from ..auth import (
    clear_auth_cookie,
    clear_csrf_cookie,
    get_current_active_user,
    issue_session_cookies,
)
from ..auth_providers.base import AuthUser
from ..auth_providers.google import get_oauth, google_oauth_configured
from ..auth_providers.local import authenticate_local
from ..auth_providers.pam import authenticate_pam
from ..schemas import LoginRequest
from ..settings import settings


router = APIRouter(prefix="/api/auth", tags=["auth"])


def safe_next_url(next_q: str | None) -> str:
    if not next_q:
        return "/"
    n = next_q.strip()
    if not n.startswith("/") or n.startswith("//"):
        return "/"
    return n


@router.post("/login")
async def login(login_request: LoginRequest, response: Response):
    if not settings.local_auth_enabled() and not settings.pam_local_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Username/password login is disabled",
        )

    user = authenticate_local(login_request.username, login_request.password)
    if user is None and settings.pam_local_enabled:
        user = await authenticate_pam(login_request.username, login_request.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    csrf_token = issue_session_cookies(response, user)
    return {
        "message": "Login successful",
        "user": {
            "username": user.username,
            "provider": user.provider,
            "email": user.email,
        },
        "csrf_token": csrf_token,
    }


@router.post("/logout")
async def logout(response: Response):
    clear_auth_cookie(response)
    clear_csrf_cookie(response)
    return {"message": "Logout successful"}


@router.get("/me")
async def read_users_me(current_user: AuthUser = Depends(get_current_active_user)):
    return {
        "username": current_user.username,
        "provider": current_user.provider,
        "email": current_user.email,
    }


@router.get("/status")
async def auth_status():
    google_login_path = "/api/auth/google/login"
    return {
        "auth_disabled": settings.auth_disabled,
        "providers": {
            "local": {"enabled": settings.local_auth_enabled()},
            "pam": {"enabled": settings.pam_local_enabled},
            "google": {
                "enabled": google_oauth_configured(),
                "login_url": google_login_path,
            },
            "api_key": {"enabled": settings.api_key_enabled()},
        },
    }


@router.get("/google/login")
async def google_login(request: Request):
    if not google_oauth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured",
        )
    request.session["post_oauth_next"] = safe_next_url(
        request.query_params.get("next")
    )
    oauth = get_oauth()
    return await oauth.google.authorize_redirect(
        request,
        settings.google_auth_redirect_uri,
    )


@router.get("/google/callback")
async def google_callback(request: Request):
    if not google_oauth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured",
        )
    oauth = get_oauth()
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError:
        return RedirectResponse(url="/?auth_error=oauth_failed", status_code=302)

    userinfo = token.get("userinfo") or {}
    if not (isinstance(userinfo, dict) and userinfo.get("email")):
        access = token.get("access_token")
        if access:
            try:
                async with httpx.AsyncClient() as client:
                    r = await client.get(
                        "https://www.googleapis.com/oauth2/v3/userinfo",
                        headers={"Authorization": f"Bearer {access}"},
                    )
                    if r.status_code == 200:
                        userinfo = r.json()
            except Exception:
                pass
    if not isinstance(userinfo, dict):
        userinfo = {}
    email = (userinfo.get("email") or "").strip()
    if not email or not settings.is_google_user_allowed(email):
        return RedirectResponse(url="/?auth_error=not_allowed", status_code=302)

    next_url = safe_next_url(request.session.pop("post_oauth_next", None))
    user = AuthUser(username=email, provider="google", email=email)
    resp = RedirectResponse(url=next_url, status_code=302)
    issue_session_cookies(resp, user)
    return resp
