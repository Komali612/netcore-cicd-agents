"""The CI agent's direct HTTP service — the credentialed, non-LLM path.

    GET  /         the CI console (repo + token + tools -> Run CI)
    GET  /healthz  liveness
    POST /ci       {repo_url, github_token, options, selected_tools} -> real PR

``POST /ci`` receives the actual token values (this is the direct channel that
does NOT go through the LLM), maps the selected tools to GitHub Actions secret
names, and runs the deterministic pipeline: Discover -> Generate -> Validate ->
set Actions secrets -> open a real PR (never merged).

Run it:  python -m agent.ci_service   (or:  uvicorn agent.ci_service:app)
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from . import db
from .console_ci import CI_CONSOLE_HTML
from .pipeline import run_ci_pipeline, to_actions_secrets

app = FastAPI(title="netcore-ci-agent", version="0.1.0")


class CIRequest(BaseModel):
    repo_url: str
    github_token: str
    options: dict[str, Any] = {}
    selected_tools: dict[str, Any] = {}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home() -> str:
    return CI_CONSOLE_HTML


@app.get("/healthz", tags=["ops"])
def healthz() -> dict:
    return {"status": "ok", "agent": "netcore-ci-agent"}


@app.post("/ci", tags=["ci"])
def ci(req: CIRequest) -> dict:
    """Run the real CI flow and return the result (incl. the opened PR URL).

    Each call is recorded to the database when one is configured (see agent.db):
    a run row is opened before the pipeline, then updated with the outcome, the
    PR, and per-secret delivery status. Secret values are encrypted; DB failures
    never break the CI run.
    """
    pipeline_secrets = to_actions_secrets(req.selected_tools)
    run_uuid = db.begin_ci_run(
        repo_url=req.repo_url,
        options=req.options or {},
        selected_tools=req.selected_tools,
        pipeline_secrets=pipeline_secrets,
        github_token=req.github_token,
    )
    try:
        result = run_ci_pipeline(
            repo_url=req.repo_url,
            github_token=req.github_token,
            options=req.options or {},
            pipeline_secrets=pipeline_secrets,
        )
        db.finish_ci_run(run_uuid, result)
        return result
    except Exception as exc:  # return a clean error, never echo the token
        db.fail_ci_run(run_uuid, type(exc).__name__, str(exc))
        return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}


def main() -> None:
    import uvicorn

    from agent_core.config import settings

    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
