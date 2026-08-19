# NetCore CI/CD Agents

An agentic framework that generates **CI and CD pipelines for .NET Core 6/7/8**
applications targeting AKS (Azure Kubernetes Service). A user provides a Git
repository URL and chooses which agent to run; the agent analyzes the repo,
generates the pipeline, validates it, and opens a pull request for human review.

Built on the reusable agent scaffolding:
[`agent-core`](https://github.com/Komali612/agent-core) (the runtime/framework)
and [`agent-starter`](https://github.com/Komali612/agent-starter) (the template
every agent is stamped from).

## Repository layout

```
netcore-cicd-agents/
├── agent-orchestrators/
│   └── netcore-orchestrator/   # Unified browser UI: repo URL + CI/CD options, routes to a worker
├── agent-ci-workers/
│   └── netcore-ci-agent/       # Generates a GitHub Actions CI workflow
└── agent-cd-workers/
    └── netcore-cd-agent/       # Generates a Harness blue/green CD pipeline for AKS
```

Each agent is self-contained (its own `pyproject.toml`, `Dockerfile`, Helm chart,
and tests) and edits only three things: `src/agent/prompts/system.md` (role),
`src/agent/skills/*.md` (capabilities), and `src/agent/tools/tools.py` (code).

## The three agents

### netcore-orchestrator (`agent-orchestrators/`)
The entry point. Serves a browser console (`GET /`) with a Git-URL field, CI/CD
option checkboxes, and **Run CI Agent** / **Run CD Agent** buttons. The user
decides which agent runs — there is no automatic routing. Options exposed:

- **open pull request** (shared)
- **LLM fallback (CI / CD)** — if no built-in template matches the repo, let the LLM author one
- **DAST scan** (CI) · **DAST gate** / **Playwright gate** (CD)
- **CD handoff: auto / manual** and **deploy automatically (else click-to-approve)**

### netcore-ci-agent (`agent-ci-workers/`)
Runs **Discover → Generate → Validate → Deploy**. Generates a GitHub Actions
workflow with build, unit tests, SonarQube coverage, SAST/SCA/DAST, container
build + SBOM + image scan, Nexus storage, Helm update, and Dynatrace/Splunk
monitoring. Validates the workflow (up to 3 attempts) and opens a PR — it never
self-merges, and repairs an existing pipeline rather than overwriting it.

### netcore-cd-agent (`agent-cd-workers/`)
Runs **Prepare → Design → Validate → Deploy**. Reads the CI handoff and the
repo's `deployment/cluster.yaml`, then generates a Harness (Argo) blue/green
pipeline with Deploy → Health-check → DAST → Playwright → Finalize gates, each
wired to roll back to the previous version on failure. Validation is a sandboxed
dry-run (no real deploys/scans). Opens a PR for review.

## Run an agent locally

```bash
cd agent-orchestrators/netcore-orchestrator   # or agent-ci-workers/… , agent-cd-workers/…
uv sync
cp .env.example .env          # set AGENT_MODEL + ANTHROPIC_API_KEY for the LLM brain
uv run agent                  # serves on http://localhost:8080  (console at GET /)
```

Invoke over HTTP:

```bash
curl -sX POST localhost:8080/run -H 'content-type: application/json' \
  -d '{"input":"Generate a CI pipeline for https://github.com/org/repo.git"}'
```

## Ship (Kubernetes)

```bash
cd <agent-folder>
make image
make deploy
```

## Status

The agents genuinely analyze a repository and generate valid CI/CD pipeline
files. Opening real GitHub/Harness pull requests and wiring the production
security tools (Fortify, Sonatype, Wiz, Nexus) are the next integration steps —
those tool steps are currently scaffolded as placeholders in the generated
pipelines.
