from pydantic import BaseModel


class AuthUser(BaseModel):
    """An authenticated principal for one request.

    ``provider`` is the identity provider the account belongs to (local / pam /
    google); ``auth_method`` is how *this particular request* proved itself.
    Keeping the two separate is what lets an API key act as a real person
    rather than as a synthetic "api" account.

    Every field beyond the original three is defaulted, so providers that know
    nothing about users keep constructing AuthUser unchanged.
    """

    username: str
    provider: str
    email: str | None = None
    display_name: str | None = None
    picture_url: str | None = None
    user_id: int | None = None
    is_admin: bool = False
    auth_method: str = "session"
    api_key_id: int | None = None
