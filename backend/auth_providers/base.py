from pydantic import BaseModel


class AuthUser(BaseModel):
    username: str
    provider: str
    email: str | None = None
