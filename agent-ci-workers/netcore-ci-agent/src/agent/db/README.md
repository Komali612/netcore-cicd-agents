# Database layer (`agent.db`)

Persists everything the CI agent is given and everything it does, so we keep
**records instead of rushing to implementation**: config overrides from the UI,
credentials / tokens / OAuth grants (encrypted), non-secret settings, target
repositories, and the full history of runs and the PRs they open.

MySQL today; **Postgres (or anything SQLAlchemy speaks) tomorrow is a config
change, not a rewrite** — see [Swapping the database](#swapping-the-database).

## Layout

| File | Responsibility |
|------|----------------|
| `config.py` | Builds the one connection string from env; `enabled()` gate. |
| `crypto.py` | Fernet encrypt/decrypt for secret columns; key fingerprint for rotation. |
| `base.py` | Declarative `Base`, timestamp/scope mixins, enums, `EncryptedString`. |
| `models.py` | The schema (ORM models). |
| `engine.py` | Engine singleton, `session_scope()`, `init_db()`. Only module that opens connections. |
| `repository.py` | Data-access layer. The rest of the app imports **only** this. |
| `db_init.py` | `uv run db-init` — create tables (dev/bootstrap). |

Nothing outside `db/` imports the ORM or a session — service code calls three
verbs: `begin_ci_run` → `finish_ci_run` / `fail_ci_run`. Every DB write is
**best-effort and non-fatal**: if the DB is unconfigured or a write fails, the
CI run still completes.

## Schema

```
organizations ─1─* teams
organizations ─1─* users            teams *─* users  (team_memberships)
organizations ─1─* repositories     teams ─1─* repositories (optional)

credentials  ┐
oauth_tokens ├─ owned by  (scope_type ∈ {org,team,user,repo}, scope_id)   ← polymorphic
settings     ┘

repositories ─1─* pipeline_runs ─1─* pull_requests
                  pipeline_runs ─1─* run_secret_deliveries ─*─ credentials (optional)
```

### Why two ownership styles
- **Operational chain** (`repositories → pipeline_runs → pull_requests /
  run_secret_deliveries`) uses real **foreign keys** with cascade — integrity
  matters and the shapes are fixed.
- **Config & secrets** (`credentials`, `oauth_tokens`, `settings`) use a
  **polymorphic owner** `(scope_type, scope_id)`. Ownership has a natural
  precedence (user > team > org > repo default), a single
  `(scope_type, scope_id, name)` uniqueness rule, and one indexed lookup.
  Owner integrity is enforced in `repository.py`, which only writes ids it just
  resolved.

### What is and isn't stored in the clear
- **Encrypted** (`EncryptedString`, Fernet): `credentials.secret`,
  `oauth_tokens.access_token`, `oauth_tokens.refresh_token`.
- **Redacted** before storage: `pipeline_runs.config_overrides` and
  `pipeline_runs.result` — secret field values become `***`; non-secret fields
  (URLs, region, org, username) are kept for auditability.
- **Never stored**: raw secret values on the run, tokens in logs or API responses.

## Security

Secrets are encrypted **before** they reach the database. Set a key once and
keep it in your secret manager:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
export DB_ENCRYPTION_KEY='...'
```

Without `DB_ENCRYPTION_KEY` the layer **fails closed**: it records non-secret
run/PR history but refuses to store any secret value in plaintext. Each
ciphertext carries a key fingerprint (`encryption_key_id`) so keys can be
rotated (keep old keys to decrypt, add a new key to encrypt, back-fill offline).

## Configuration (env)

```bash
# Option A — one URL (wins if set)
export DATABASE_URL='mysql+pymysql://user:pass@127.0.0.1:3306/netcore_cicd'

# Option B — discrete parts
export DB_NAME=netcore_cicd        # required to enable via parts
export DB_USER=root DB_PASSWORD=secret
export DB_HOST=127.0.0.1 DB_PORT=3306
export DB_DRIVER=mysql+pymysql     # swap target here

export DB_ENCRYPTION_KEY='...'     # required to store secrets
export DB_ECHO=1                   # optional: log SQL
```

If neither `DATABASE_URL` nor `DB_NAME` is set, persistence is **disabled** and
the agent behaves exactly as before.

```bash
uv run db-init      # create tables
```

## Swapping the database

Everything is dialect-agnostic: generic column types, string-backed enums (no
native `ENUM` to migrate), `JSON` columns (MySQL 8 + Postgres both native),
portable `CHECK` constraints. To move to Postgres:

```bash
export DATABASE_URL='postgresql+psycopg://user:pass@host:5432/netcore_cicd'
uv run db-init
```

No model or query changes. For a production-grade swap, front `repository.py`
with the same three verbs and everything above it is untouched.

## Migrations

`db-init` / `init_db()` are `CREATE TABLE IF NOT EXISTS` — fine for dev and the
first deploy, but they do not evolve a live schema. For production, add
[Alembic](https://alembic.sqlalchemy.org/): `alembic init`, point
`sqlalchemy.url` at `DATABASE_URL`, `--autogenerate` against `Base.metadata`.
