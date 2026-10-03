"""SQLAlchemy ORM models for cached profiles and analytics runs."""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class User(Base):
    """Cached GitHub developer profile."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    login: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str] = mapped_column(String(500), nullable=False)
    html_url: Mapped[str] = mapped_column(String(500), nullable=False)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    blog: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    public_repos: Mapped[int] = mapped_column(Integer, default=0)
    public_gists: Mapped[int] = mapped_column(Integer, default=0)
    followers: Mapped[int] = mapped_column(Integer, default=0)
    following: Mapped[int] = mapped_column(Integer, default=0)
    github_created_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Step 7: GitHub OAuth — encrypted personal access token for private repo analytics.
    # Never store raw tokens; see app/services/auth.py encrypt/decrypt helpers.
    github_token_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_scope: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    token_obtained_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    analytics_runs: Mapped[List["AnalyticsRun"]] = relationship(
        "AnalyticsRun", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User login={self.login} github_id={self.github_id}>"


class AnalyticsRun(Base):
    """Audit log of analytics requests, response times, and cache hit metrics."""

    __tablename__ = "analytics_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    username: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    query_type: Mapped[str] = mapped_column(String(50), default="profile_lookup", nullable=False)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="success", nullable=False)
    response_time_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="analytics_runs")

    def __repr__(self) -> str:
        return f"<AnalyticsRun username={self.username} cache_hit={self.cache_hit} status={self.status}>"
