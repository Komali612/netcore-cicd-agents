"""Data-access layer — the ONLY module the rest of the app imports for the DB.

Service code (ci_service) never touches the ORM or sessions directly; it calls
three verbs around a run:

    uuid = begin_ci_run(repo_url, options, selected_tools, secrets, github_token)
    finish_ci_run(uuid, result)          # on success
    fail_ci_run(uuid, error_type, msg)   # on exception

Every function is **best-effort and non-fatal**: if the DB is not configured or a
write fails, it logs and returns (None), so persistence can never break a CI run.
Secret values are encrypted via the Credential model; only redacted config and
result snapshots are stored on the run itself.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from . import crypto
from .base import (
    CredentialKind,
    PullRequestState,
    RunStatus,
    ScopeType,
    SecretStatus,
)
from .engine import enabled, session_scope
from .models import (
    Credential,
    Organization,
    PipelineRun,
    PullRequest,
    Repository,
    SecretDelivery,
)

log = logging.getLogger(__name__)

DEFAULT_ORG_SLUG = "default"

# Result-status string (from run_ci_pipeline) -> RunStatus enum.
_RUN_STATUS = {
    "opened": RunStatus.OPENED,
    "generated": RunStatus.GENERATED,
    "validation_failed": RunStatus.VALIDATION_FAILED,
    "error": RunStatus.ERROR,
}

# UI field labels that are NOT secret and are safe to keep verbatim in the
# redacted config snapshot. Everything else is replaced with '***'.
_NON_SECRET_LABELS = {
    "Host URL", "SSC URL", "IQ Server URL", "Base URL", "Login server",
    "Repository URL", "Region", "Organization", "Username", "HEC URL",
    "Environment ID",
}


# --------------------------------------------------------------------------- #
# Redaction
# --------------------------------------------------------------------------- #
def redact_config(selected_tools: dict) -> dict:
    """Return a copy of the UI's selected_tools with secret values masked. Keeps
    the structure and the ``tool`` selector plus known non-secret fields, so the
    record shows *what* was configured without leaking secret values."""
    out: dict = {}
    for capability, entry in (selected_tools or {}).items():
        if not isinstance(entry, dict):
            out[capability] = entry
            continue
        red: dict = {}
        for label, value in entry.items():
            if label == "tool" or label in _NON_SECRET_LABELS:
                red[label] = value
            elif value in (None, ""):
                red[label] = value
            else:
                red[label] = "***"
        out[capability] = red
    return out


# --------------------------------------------------------------------------- #
# Tenancy / repository resolution
# --------------------------------------------------------------------------- #
def _get_or_create_org(session, slug: str = DEFAULT_ORG_SLUG) -> Organization:
    org = session.scalar(select(Organization).where(Organization.slug == slug))
    if org is None:
        org = Organization(slug=slug, name=slug.replace("-", " ").title())
        session.add(org)
        session.flush()
    return org


def _get_or_create_repo(session, org: Organization, repo_url: str) -> Repository:
    from ..github_client import parse_repo_full_name

    try:
        full_name = parse_repo_full_name(repo_url)
    except Exception:
        full_name = None
    repo = session.scalar(
        select(Repository).where(Repository.org_id == org.id, Repository.url == repo_url)
    )
    if repo is None:
        repo = Repository(org_id=org.id, url=repo_url, full_name=full_name)
        session.add(repo)
        session.flush()
    elif full_name and not repo.full_name:
        repo.full_name = full_name
    return repo


# --------------------------------------------------------------------------- #
# Credentials
# --------------------------------------------------------------------------- #
def _kind_for(name: str) -> CredentialKind:
    upper = name.upper()
    if "PASSWORD" in upper:
        return CredentialKind.PASSWORD
    if "TOKEN" in upper or "PAT" in upper:
        return CredentialKind.TOKEN
    if "KEY" in upper or "SECRET" in upper:
        return CredentialKind.API_KEY
    return CredentialKind.GENERIC


def _upsert_credential(session, *, scope_type: ScopeType, scope_id: int, name: str,
                       value: str, provider: Optional[str] = None) -> Optional[Credential]:
    """Insert/update one encrypted credential at a scope. Skips silently (returns
    None) when encryption is unavailable — we never store a secret in plaintext."""
    if not value or not crypto.available():
        return None
    cred = session.scalar(
        select(Credential).where(
            Credential.scope_type == scope_type,
            Credential.scope_id == scope_id,
            Credential.name == name,
        )
    )
    if cred is None:
        cred = Credential(scope_type=scope_type, scope_id=scope_id, name=name,
                          kind=_kind_for(name), provider=provider)
        session.add(cred)
    cred.secret = value            # EncryptedString encrypts on flush
    cred.encryption_key_id = crypto.key_id()
    cred.provider = provider or cred.provider
    cred.is_active = True
    cred.rotated_at = datetime.now(timezone.utc)
    session.flush()
    return cred


# --------------------------------------------------------------------------- #
# Public API — the three verbs the service calls
# --------------------------------------------------------------------------- #
def begin_ci_run(*, repo_url: str, options: Optional[dict], selected_tools: Optional[dict],
                 pipeline_secrets: Optional[dict] = None, github_token: Optional[str] = None,
                 org_slug: str = DEFAULT_ORG_SLUG) -> Optional[str]:
    """Record the start of a run and (best-effort) persist submitted credentials.
    Returns the run's uuid, or None if the DB is disabled / unavailable."""
    if not enabled():
        return None
    try:
        with session_scope() as session:
            org = _get_or_create_org(session, org_slug)
            repo = _get_or_create_repo(session, org, repo_url)

            run = PipelineRun(
                repository_id=repo.id,
                org_id=org.id,
                status=RunStatus.RUNNING,
                options=options or {},
                config_overrides=redact_config(selected_tools or {}),
                started_at=datetime.now(timezone.utc),
            )
            session.add(run)
            session.flush()

            # Persist submitted secrets (encrypted), scoped to the repository, so
            # they are reusable and auditable. Disable with options.store_credentials=False.
            if (options or {}).get("store_credentials", True):
                for name, value in (pipeline_secrets or {}).items():
                    _upsert_credential(session, scope_type=ScopeType.REPO,
                                       scope_id=repo.id, name=name, value=value)
                if github_token:
                    _upsert_credential(session, scope_type=ScopeType.REPO,
                                       scope_id=repo.id, name="GITHUB_TOKEN",
                                       value=github_token, provider="GitHub")
            return run.uuid
    except Exception as exc:  # never let persistence break a CI run
        log.warning("begin_ci_run failed (continuing without DB): %s", exc)
        return None


def finish_ci_run(run_uuid: Optional[str], result: dict) -> None:
    """Update the run from run_ci_pipeline's result: status, discovery, PR row,
    and one SecretDelivery row per delivered secret."""
    if not run_uuid or not enabled():
        return
    try:
        with session_scope() as session:
            run = session.scalar(select(PipelineRun).where(PipelineRun.uuid == run_uuid))
            if run is None:
                return
            run.status = _RUN_STATUS.get(result.get("status"), RunStatus.GENERATED)
            run.stage = result.get("stage")
            run.workflow_path = result.get("workflow_path")
            run.warnings = result.get("warnings")
            run.result = result
            run.finished_at = datetime.now(timezone.utc)
            disc = result.get("discovery") or {}
            run.target_framework = disc.get("target_framework")

            pr = result.get("pr")
            if pr:
                session.add(PullRequest(
                    run_id=run.id, repository_id=run.repository_id,
                    number=pr.get("pr_number"), url=pr.get("pr_url"),
                    branch=pr.get("branch"), base=pr.get("base"),
                    state=PullRequestState.OPEN,
                ))

            for sr in result.get("secrets") or []:
                try:
                    status = SecretStatus(sr.get("status"))
                except ValueError:
                    status = SecretStatus.FAILED
                session.add(SecretDelivery(
                    run_id=run.id, secret_name=sr.get("name", "?"),
                    target_scope=sr.get("scope", "repo"),
                    status=status, error=sr.get("error"),
                ))
    except Exception as exc:
        log.warning("finish_ci_run failed: %s", exc)


def fail_ci_run(run_uuid: Optional[str], error_type: str, message: str,
                stage: Optional[str] = None) -> None:
    """Mark a run as errored (called when the pipeline raised)."""
    if not run_uuid or not enabled():
        return
    try:
        with session_scope() as session:
            run = session.scalar(select(PipelineRun).where(PipelineRun.uuid == run_uuid))
            if run is None:
                return
            run.status = RunStatus.ERROR
            run.stage = stage
            run.error = f"{error_type}: {message}"
            run.finished_at = datetime.now(timezone.utc)
    except Exception as exc:
        log.warning("fail_ci_run failed: %s", exc)
