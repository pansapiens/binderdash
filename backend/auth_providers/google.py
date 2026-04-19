from authlib.integrations.starlette_client import OAuth

from ..settings import settings

_oauth: OAuth | None = None


def get_oauth() -> OAuth:
    global _oauth
    if _oauth is None:
        _oauth = OAuth()
        _oauth.register(
            name="google",
            client_id=settings.google_auth_client_id,
            client_secret=settings.google_auth_client_secret,
            server_metadata_url=(
                "https://accounts.google.com/.well-known/openid-configuration"
            ),
            client_kwargs={"scope": "openid email profile"},
        )
    return _oauth


def google_oauth_configured() -> bool:
    return bool(
        settings.google_auth_enabled
        and settings.google_auth_client_id
        and settings.google_auth_client_secret
        and settings.google_auth_redirect_uri
    )
