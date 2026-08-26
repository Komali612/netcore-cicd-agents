"""DB layer tests — run fully offline against SQLite in-memory.

Because the schema is dialect-agnostic, the same models/queries that target
MySQL in production run under SQLite here: no database server needed for CI.
"""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select, text

from agent.db import crypto, engine, repository
from agent.db.base import RunStatus, SecretStatus
from agent.db.models import Credential, PipelineRun, PullRequest, SecretDelivery


@pytest.fixture()
def db(monkeypatch):
    """A fresh in-memory database + encryption key for one test."""
    monkeypatch.setenv("DB_ENCRYPTION_KEY", Fernet.generate_key().decode())
    crypto.reset_cache()
    eng = engine.make_engine("sqlite://")
    engine.configure(eng)
    engine.init_db()
    try:
        yield eng
    finally:
        engine._engine = None
        engine._SessionLocal = None
        eng.dispose()
        crypto.reset_cache()


def _fake_result() -> dict:
    return {
        "status": "opened",
        "repo": "owner/repo",
        "discovery": {"target_framework": ".NET 8", "existing_ci_pipeline": False},
        "validation": {"valid": True},
        "secrets": [
            {"name": "SONAR_TOKEN", "scope": "repo", "status": "set"},
            {"name": "REGISTRY_TOKEN", "status": "failed", "error": "403 no access"},
        ],
        "workflow_path": ".github/workflows/ci-pipeline.yml",
        "pr": {"pr_number": 7, "pr_url": "https://github.com/owner/repo/pull/7",
               "branch": "ci/netcore-app", "base": "main"},
        "warnings": ["Could not set these Actions secrets: REGISTRY_TOKEN"],
    }


def test_redact_config_masks_secrets_keeps_non_secret():
    selected = {"sast": {"tool": "SonarQube", "Host URL": "https://sonar.example",
                         "Token": "supersecret"}}
    red = repository.redact_config(selected)
    assert red["sast"]["Host URL"] == "https://sonar.example"  # non-secret kept
    assert red["sast"]["Token"] == "***"                        # secret masked
    assert red["sast"]["tool"] == "SonarQube"


def test_begin_run_records_run_and_encrypts_credentials(db):
    run_uuid = repository.begin_ci_run(
        repo_url="https://github.com/owner/repo",
        options={},
        selected_tools={"sast": {"tool": "SonarQube", "Token": "supersecret"}},
        pipeline_secrets={"SONAR_TOKEN": "sonar-secret", "EMPTY": ""},
        github_token="ghp_exampletoken",
    )
    assert run_uuid

    with engine.session_scope() as s:
        run = s.scalar(select(PipelineRun).where(PipelineRun.uuid == run_uuid))
        assert run.status == RunStatus.RUNNING
        assert run.config_overrides["sast"]["Token"] == "***"

        # Secret stored and decrypts back through the ORM...
        cred = s.scalar(select(Credential).where(Credential.name == "SONAR_TOKEN"))
        assert cred.secret == "sonar-secret"
        assert cred.encryption_key_id
        # ...but the raw column is ciphertext, never plaintext.
        raw = s.execute(text("SELECT secret FROM credentials WHERE name='SONAR_TOKEN'")).scalar()
        assert raw != "sonar-secret"
        assert raw.startswith("gAAAA")  # Fernet token prefix

        # github token persisted; blank secret skipped.
        assert s.scalar(select(Credential).where(Credential.name == "GITHUB_TOKEN")).secret == "ghp_exampletoken"
        assert s.scalar(select(Credential).where(Credential.name == "EMPTY")) is None


def test_finish_run_records_pr_and_secret_deliveries(db):
    run_uuid = repository.begin_ci_run(
        repo_url="https://github.com/owner/repo", options={},
        selected_tools={}, pipeline_secrets={}, github_token=None,
    )
    repository.finish_ci_run(run_uuid, _fake_result())

    with engine.session_scope() as s:
        run = s.scalar(select(PipelineRun).where(PipelineRun.uuid == run_uuid))
        assert run.status == RunStatus.OPENED
        assert run.target_framework == ".NET 8"
        assert run.finished_at is not None

        pr = s.scalar(select(PullRequest).where(PullRequest.run_id == run.id))
        assert pr.number == 7
        assert pr.url.endswith("/pull/7")

        deliveries = s.scalars(select(SecretDelivery).where(SecretDelivery.run_id == run.id)).all()
        by_name = {d.secret_name: d for d in deliveries}
        assert by_name["SONAR_TOKEN"].status == SecretStatus.SET
        assert by_name["REGISTRY_TOKEN"].status == SecretStatus.FAILED
        assert by_name["REGISTRY_TOKEN"].error == "403 no access"


def test_fail_run_marks_error(db):
    run_uuid = repository.begin_ci_run(
        repo_url="https://github.com/owner/repo", options={},
        selected_tools={}, pipeline_secrets={}, github_token=None,
    )
    repository.fail_ci_run(run_uuid, "ValueError", "bad repo", stage="discover")

    with engine.session_scope() as s:
        run = s.scalar(select(PipelineRun).where(PipelineRun.uuid == run_uuid))
        assert run.status == RunStatus.ERROR
        assert run.stage == "discover"
        assert "ValueError: bad repo" in run.error


def test_disabled_db_is_a_noop(monkeypatch):
    """With no DB configured, the verbs return quietly and never raise."""
    monkeypatch.setattr(repository, "enabled", lambda: False)
    assert repository.begin_ci_run(
        repo_url="https://github.com/owner/repo", options={},
        selected_tools={}, pipeline_secrets={}, github_token="x",
    ) is None
    # finish/fail with a None uuid must be safe too.
    repository.finish_ci_run(None, _fake_result())
    repository.fail_ci_run(None, "E", "m")
