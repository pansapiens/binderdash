from fastapi import APIRouter, Depends, Response

from ..auth import (
    authenticate_user,
    create_access_token,
    generate_csrf_token,
    set_auth_cookie,
    clear_auth_cookie,
    clear_csrf_cookie,
    get_current_active_user,
)
from ..schemas import LoginRequest
from ..settings import settings, LocalUser
from datetime import timedelta


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(login_request: LoginRequest, response: Response):
    user = authenticate_user(login_request.username, login_request.password)
    if not user:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    set_auth_cookie(response, access_token, access_token_expires)
    csrf_token = generate_csrf_token()
    from ..auth import set_csrf_cookie

    set_csrf_cookie(response, csrf_token)
    return {
        "message": "Login successful",
        "user": {"username": user.username},
        "csrf_token": csrf_token,
    }


@router.post("/logout")
async def logout(response: Response):
    clear_auth_cookie(response)
    clear_csrf_cookie(response)
    return {"message": "Logout successful"}


@router.get("/me")
async def read_users_me(current_user: LocalUser = Depends(get_current_active_user)):
    return {"username": current_user.username}


@router.get("/status")
async def auth_status():
    return {"auth_disabled": settings.auth_disabled}
