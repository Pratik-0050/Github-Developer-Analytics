"""Pydantic schemas for GitHub OAuth 2.0 authentication (Step 7)."""

from typing import Optional
from pydantic import BaseModel, ConfigDict


class AuthLoginUrlResponse(BaseModel):
    """Authorization URL the frontend redirects the user to."""

    authorization_url: str
    redirect_uri: str
    scope: str

    model_config = ConfigDict(from_attributes=True)


class AuthStatusResponse(BaseModel):
    """Public OAuth configuration status (no secrets exposed)."""

    configured: bool
    client_id_present: bool
    redirect_uri: str
    scope: str

    model_config = ConfigDict(from_attributes=True)


class AuthMeResponse(BaseModel):
    """Current session user resolved from JWT + DB token state."""

    login: str
    github_id: int
    avatar_url: str
    html_url: str
    scope: Optional[str] = None
    private_enabled: bool = False
    token_obtained_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AuthCallbackResponse(BaseModel):
    """Successful OAuth callback: user snapshot.

    The session JWT is delivered ONLY via the HttpOnly ``gda_session``
    cookie (``Set-Cookie`` header) — never in the body, URL, or logs.
    """

    scope: Optional[str] = None
    private_enabled: bool = False
    login: str
    github_id: int
    avatar_url: str
    html_url: str

    model_config = ConfigDict(from_attributes=True)
