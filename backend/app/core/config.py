"""Configuration management using Pydantic BaseSettings."""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Explicitly load backend/.env (via python-dotenv) so GITHUB_TOKEN and other
# settings resolve regardless of the process working directory. Pydantic's
# env_file=".env" alone is CWD-relative and silently misses the file when
# uvicorn/pytest run from the repo root.
_BACKEND_ENV = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=_BACKEND_ENV, override=False)


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    APP_NAME: str = "GitHub Developer Analytics API"
    APP_VERSION: str = "1.0.0"
    FRONTEND_URL: str = "http://localhost:3000"
    GITHUB_API_URL: str = "https://api.github.com"

    # Database Configuration (PostgreSQL default, falls back to SQLite for local development)
    DATABASE_URL: str = "sqlite:///./analytics.db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    CACHE_TTL_SECONDS: int = 3600

    # GitHub Authentication Token (Optional, increases API rate limit from 60 to 5,000 req/hr)
    # Loaded from backend/.env via python-dotenv above. Never exposed to the
    # frontend — only sent server-side as an Authorization header.
    GITHUB_TOKEN: Optional[str] = None

    # Step 7: GitHub OAuth 2.0 & Private Repositories
    # NOTE: values are stripped of accidental whitespace (e.g. trailing spaces
    # in backend/.env) by the validator below.
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    # Where GitHub redirects after authorize. Must match the OAuth App's
    # "Authorization callback URL" exactly. This is the BACKEND callback so the
    # authorization code is exchanged server-side and the session is stored in
    # an HttpOnly cookie (never exposed to the browser).
    GITHUB_OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/auth/github/callback"
    # Minimal scope: public profile only. Private-repo analytics stay disabled
    # unless the operator explicitly opts in with e.g. "read:user repo".
    GITHUB_OAUTH_SCOPE: str = "read:user"
    # Legacy alias: older backend/.env files used GITHUB_REDIRECT_URI. If set
    # and GITHUB_OAUTH_REDIRECT_URI was left at its default, the alias wins.
    # (Read directly from the environment; extra="ignore" drops it otherwise.)
    JWT_SECRET: Optional[str] = None
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 10080  # 7 days
    # Session / CSRF cookie names. SameSite=Lax is correct when the frontend
    # and API are same-site (e.g. localhost:3000 + localhost:8000, or same
    # domain in prod). For cross-domain prod deployments set
    # SESSION_COOKIE_SAMESITE=none (requires HTTPS).
    SESSION_COOKIE_NAME: str = "gda_session"
    OAUTH_STATE_COOKIE_NAME: str = "gda_oauth_state"
    SESSION_COOKIE_SAMESITE: str = "lax"
    # Fernet key for encrypting stored GitHub OAuth tokens. Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    OAUTH_TOKEN_FERNET_KEY: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator(
        "GITHUB_CLIENT_ID",
        "GITHUB_CLIENT_SECRET",
        "GITHUB_OAUTH_REDIRECT_URI",
        "GITHUB_OAUTH_SCOPE",
        "FRONTEND_URL",
        mode="before",
    )
    @classmethod
    def _strip_strings(cls, value):
        return value.strip() if isinstance(value, str) else value


settings = Settings()

# Legacy alias support: honor GITHUB_REDIRECT_URI from older backend/.env files
# when the canonical GITHUB_OAUTH_REDIRECT_URI was not explicitly configured.
_legacy_redirect = os.getenv("GITHUB_REDIRECT_URI", "").strip()
if _legacy_redirect and settings.GITHUB_OAUTH_REDIRECT_URI == (
    "http://localhost:8000/api/auth/github/callback"
):
    # Only apply when the operator did not set the canonical variable.
    if not os.getenv("GITHUB_OAUTH_REDIRECT_URI"):
        settings.GITHUB_OAUTH_REDIRECT_URI = _legacy_redirect
