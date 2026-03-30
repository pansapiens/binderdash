import secrets
from typing import List

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class RawSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
    run_base_dirs: str = ""
    allowed_users: str = ""
    local_users: str = ""
    secret_key: str = ""
    cors_allowed_origins: str = ""
    disable_authentication: str = ""
    access_token_expire_minutes: int = 60 * 24
    domain: str = ""
    log_level: str = "INFO"


class LocalUser(BaseModel):
    username: str
    password_hash: str


class AppSettings(BaseModel):
    run_base_dirs: List[str] = []
    allowed_users: List[str] = []
    local_users: List[LocalUser] = []
    auth_disabled: bool = False
    access_token_expire_minutes: int = 60 * 24
    log_level: str = "INFO"


def parse_local_users(local_users_str: str) -> List[LocalUser]:
    if not local_users_str:
        return []
    users: List[LocalUser] = []
    for item in local_users_str.split(","):
        item = item.strip()
        if ":" in item:
            username, password_hash = item.split(":", 1)
            users.append(
                LocalUser(
                    username=username.strip(), password_hash=password_hash.strip()
                )
            )
    return users


raw_settings = RawSettings()
settings = AppSettings(
    run_base_dirs=(
        [item.strip() for item in raw_settings.run_base_dirs.split(",")]
        if raw_settings.run_base_dirs
        else []
    ),
    allowed_users=(
        [item.strip() for item in raw_settings.allowed_users.split(",")]
        if raw_settings.allowed_users
        else []
    ),
    local_users=parse_local_users(raw_settings.local_users),
    auth_disabled=raw_settings.disable_authentication.lower() == "true",
    access_token_expire_minutes=raw_settings.access_token_expire_minutes,
    log_level=(raw_settings.log_level or "INFO").strip().upper(),
)

SECRET_KEY = raw_settings.secret_key or secrets.token_urlsafe(32)
CORS_ALLOWED_ORIGINS = (
    [item.strip() for item in raw_settings.cors_allowed_origins.split(",")]
    if raw_settings.cors_allowed_origins
    else ["*"]
)
