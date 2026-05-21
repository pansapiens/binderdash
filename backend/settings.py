import secrets
from typing import List

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class RawSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
    database: str = ""
    run_base_dirs: str = ""
    local_users: str = ""
    secret_key: str = ""
    cors_allowed_origins: str = ""
    disable_authentication: str = ""
    access_token_expire_minutes: int = 60 * 24
    domain: str = ""
    log_level: str = "INFO"
    pam_local_enabled: str = ""
    pam_local_allowed_users: str = ""
    pam_local_service: str = ""
    google_auth_enabled: str = ""
    google_auth_client_id: str = ""
    google_auth_client_secret: str = ""
    google_auth_redirect_uri: str = ""
    google_auth_allowed_users: str = ""
    binderdash_api_key: str = ""


class LocalUser(BaseModel):
    username: str
    password_hash: str


class AppSettings(BaseModel):
    run_base_dirs: List[str] = []
    local_users: List[LocalUser] = []
    auth_disabled: bool = False
    access_token_expire_minutes: int = 60 * 24
    log_level: str = "INFO"
    pam_local_enabled: bool = False
    pam_local_allowed_users: List[str] = []
    pam_local_service: str = "common-auth"
    google_auth_enabled: bool = False
    google_auth_client_id: str = ""
    google_auth_client_secret: str = ""
    google_auth_redirect_uri: str = ""
    google_auth_allowed_users: List[str] = []
    binderdash_api_key: str = ""

    def api_key_enabled(self) -> bool:
        return bool(self.binderdash_api_key)

    def local_auth_enabled(self) -> bool:
        return len(self.local_users) > 0

    def is_pam_user_allowed(self, username: str) -> bool:
        if not self.pam_local_enabled:
            return False
        items = self.pam_local_allowed_users
        if not items:
            return False
        if "*" in items:
            return True
        return username.strip().lower() in items

    def is_google_user_allowed(self, email: str) -> bool:
        if not self.google_auth_enabled:
            return False
        e = email.strip().lower()
        if not e or not self.google_auth_allowed_users:
            return False
        return e in self.google_auth_allowed_users


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


def _parse_csv_lower(s: str) -> List[str]:
    return [x.strip().lower() for x in s.split(",") if x.strip()]


raw_settings = RawSettings()
settings = AppSettings(
    run_base_dirs=(
        [item.strip() for item in raw_settings.run_base_dirs.split(",")]
        if raw_settings.run_base_dirs
        else []
    ),
    local_users=parse_local_users(raw_settings.local_users),
    auth_disabled=raw_settings.disable_authentication.lower() == "true",
    access_token_expire_minutes=raw_settings.access_token_expire_minutes,
    log_level=(raw_settings.log_level or "INFO").strip().upper(),
    pam_local_enabled=raw_settings.pam_local_enabled.lower() == "true",
    pam_local_allowed_users=_parse_csv_lower(raw_settings.pam_local_allowed_users),
    pam_local_service=(
        (raw_settings.pam_local_service or "").strip() or "common-auth"
    ),
    google_auth_enabled=raw_settings.google_auth_enabled.lower() == "true",
    google_auth_client_id=(raw_settings.google_auth_client_id or "").strip(),
    google_auth_client_secret=(raw_settings.google_auth_client_secret or "").strip(),
    google_auth_redirect_uri=(raw_settings.google_auth_redirect_uri or "").strip(),
    google_auth_allowed_users=_parse_csv_lower(raw_settings.google_auth_allowed_users),
    binderdash_api_key=(raw_settings.binderdash_api_key or "").strip(),
)

SECRET_KEY = raw_settings.secret_key or secrets.token_urlsafe(32)
CORS_ALLOWED_ORIGINS = (
    [item.strip() for item in raw_settings.cors_allowed_origins.split(",")]
    if raw_settings.cors_allowed_origins
    else ["*"]
)
