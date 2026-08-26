"""ORM models — the schema.

Two clusters, joined at ``repositories``:

  Tenancy & config (who owns what, and their stored config/secrets)
    organizations 1─* teams
    organizations 1─* users            teams *─* users  (via team_memberships)
    organizations 1─* repositories     teams 1─* repositories (optional)
    credentials / oauth_tokens / settings  ── scoped to org|team|user|repo
                                               (polymorphic, see ScopedMixin)

  Operational history (what the agent actually did)
    repositories 1─* pipeline_runs
    pipeline_runs 1─* pull_requests
    pipeline_runs 1─* run_secret_deliveries ─* credentials (optional link)

Secret-bearing columns use ``EncryptedString`` (encrypted at rest). Non-secret
config lives in ``settings.value_json`` and in the redacted JSON snapshots on
``pipeline_runs``.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import (
    Base,
    CredentialKind,
    EncryptedString,
    PullRequestState,
    RunStatus,
    ScopedMixin,
    SecretStatus,
    TimestampMixin,
    _enum,
)


# --------------------------------------------------------------------------- #
# Tenancy
# --------------------------------------------------------------------------- #
class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    teams: Mapped[list["Team"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    users: Mapped[list["User"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    repositories: Mapped[list["Repository"]] = relationship(back_populates="organization", cascade="all, delete-orphan")


class Team(Base, TimestampMixin):
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("org_id", "slug", name="uq_team_org_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="teams")
    memberships: Mapped[list["TeamMembership"]] = relationship(back_populates="team", cascade="all, delete-orphan")


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("org_id", "email", name="uq_user_org_email"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(255))
    external_id: Mapped[Optional[str]] = mapped_column(String(255))  # e.g. GitHub login

    organization: Mapped[Organization] = relationship(back_populates="users")
    memberships: Mapped[list["TeamMembership"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class TeamMembership(Base, TimestampMixin):
    __tablename__ = "team_memberships"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_membership_team_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="member")

    team: Mapped[Team] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


class Repository(Base, TimestampMixin):
    __tablename__ = "repositories"
    __table_args__ = (UniqueConstraint("org_id", "url", name="uq_repo_org_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    team_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), index=True)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(512), index=True)  # owner/repo
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="github")
    default_branch: Mapped[str] = mapped_column(String(128), nullable=False, default="main")

    organization: Mapped[Organization] = relationship(back_populates="repositories")
    runs: Mapped[list["PipelineRun"]] = relationship(back_populates="repository", cascade="all, delete-orphan")


# --------------------------------------------------------------------------- #
# Scoped config & secrets  (owner = scope_type + scope_id, see ScopedMixin)
# --------------------------------------------------------------------------- #
class Credential(Base, TimestampMixin, ScopedMixin):
    """A single stored secret: PAT, password, API key, SSH key, etc. The value is
    encrypted (``EncryptedString``). OAuth tokens with refresh semantics live in
    ``oauth_tokens`` instead; simple bearer tokens can live here."""

    __tablename__ = "credentials"
    __table_args__ = (
        UniqueConstraint("scope_type", "scope_id", "name", name="uq_credential_scope_name"),
        CheckConstraint("scope_id > 0", name="ck_credential_scope_id_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)  # logical key, e.g. SONAR_TOKEN
    kind: Mapped[CredentialKind] = mapped_column(_enum(CredentialKind), nullable=False, default=CredentialKind.TOKEN)
    provider: Mapped[Optional[str]] = mapped_column(String(128))    # SonarQube, GitHub, GHCR...
    secret: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    encryption_key_id: Mapped[Optional[str]] = mapped_column(String(64))
    description: Mapped[Optional[str]] = mapped_column(String(512))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    rotated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class OAuthToken(Base, TimestampMixin, ScopedMixin):
    """OAuth grant with refresh semantics: access + refresh tokens (both
    encrypted), token type, granted scopes, and expiry."""

    __tablename__ = "oauth_tokens"
    __table_args__ = (
        UniqueConstraint(
            "scope_type", "scope_id", "provider", "provider_account_id",
            name="uq_oauth_scope_provider_account",
        ),
        CheckConstraint("scope_id > 0", name="ck_oauth_scope_id_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)  # github, google, azure_ad...
    provider_account_id: Mapped[Optional[str]] = mapped_column(String(255))
    access_token: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    refresh_token: Mapped[Optional[str]] = mapped_column(EncryptedString)
    token_type: Mapped[str] = mapped_column(String(64), nullable=False, default="bearer")
    scopes: Mapped[Optional[str]] = mapped_column(String(1024))  # space/comma-separated
    encryption_key_id: Mapped[Optional[str]] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class Setting(Base, TimestampMixin, ScopedMixin):
    """Non-secret config / override, keyed and scoped. Values are JSON so a
    setting can be a scalar, a list, or a nested object."""

    __tablename__ = "settings"
    __table_args__ = (
        UniqueConstraint("scope_type", "scope_id", "key", name="uq_setting_scope_key"),
        CheckConstraint("scope_id > 0", name="ck_setting_scope_id_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    value_json: Mapped[Optional[dict]] = mapped_column(JSON)
    description: Mapped[Optional[str]] = mapped_column(String(512))


# --------------------------------------------------------------------------- #
# Operational history
# --------------------------------------------------------------------------- #
class PipelineRun(Base, TimestampMixin):
    """One invocation of the agent against a repository (a POST /ci call).
    ``config_overrides`` and ``result`` are REDACTED JSON snapshots — no secret
    values ever land here; secret values go (encrypted) to ``credentials``."""

    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uuid: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, default=lambda: str(uuid.uuid4()))
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    org_id: Mapped[Optional[int]] = mapped_column(ForeignKey("organizations.id", ondelete="SET NULL"), index=True)
    team_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), index=True)
    triggered_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)

    agent: Mapped[str] = mapped_column(String(64), nullable=False, default="netcore-ci-agent")
    status: Mapped[RunStatus] = mapped_column(_enum(RunStatus), nullable=False, default=RunStatus.PENDING, index=True)
    stage: Mapped[Optional[str]] = mapped_column(String(32))  # discover/generate/validate/secrets/pr
    target_framework: Mapped[Optional[str]] = mapped_column(String(64))
    build_tool: Mapped[Optional[str]] = mapped_column(String(64))
    workflow_path: Mapped[Optional[str]] = mapped_column(String(512))
    options: Mapped[Optional[dict]] = mapped_column(JSON)
    config_overrides: Mapped[Optional[dict]] = mapped_column(JSON)  # redacted selected_tools
    result: Mapped[Optional[dict]] = mapped_column(JSON)            # redacted result snapshot
    error: Mapped[Optional[str]] = mapped_column(Text)
    warnings: Mapped[Optional[list]] = mapped_column(JSON)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    repository: Mapped[Repository] = relationship(back_populates="runs")
    pull_requests: Mapped[list["PullRequest"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    secret_deliveries: Mapped[list["SecretDelivery"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class PullRequest(Base, TimestampMixin):
    __tablename__ = "pull_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    number: Mapped[Optional[int]] = mapped_column(Integer)
    url: Mapped[Optional[str]] = mapped_column(String(1024))
    branch: Mapped[Optional[str]] = mapped_column(String(255))
    base: Mapped[Optional[str]] = mapped_column(String(255))
    title: Mapped[Optional[str]] = mapped_column(String(512))
    state: Mapped[PullRequestState] = mapped_column(_enum(PullRequestState), nullable=False, default=PullRequestState.OPEN)
    is_merged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    run: Mapped[PipelineRun] = relationship(back_populates="pull_requests")


class SecretDelivery(Base, TimestampMixin):
    """Audit row: which named secret the run tried to deliver to the CI runner and
    what happened. Mirrors one entry of the pipeline's ``secrets`` result list."""

    __tablename__ = "run_secret_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    secret_name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_scope: Mapped[str] = mapped_column(String(32), nullable=False, default="repo")  # Actions repo secret
    status: Mapped[SecretStatus] = mapped_column(_enum(SecretStatus), nullable=False)
    credential_id: Mapped[Optional[int]] = mapped_column(ForeignKey("credentials.id", ondelete="SET NULL"), index=True)
    error: Mapped[Optional[str]] = mapped_column(String(1024))

    run: Mapped[PipelineRun] = relationship(back_populates="secret_deliveries")
