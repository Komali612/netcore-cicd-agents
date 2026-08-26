"""CLI: create the database schema.  ``uv run db-init``

Bootstrap helper for dev and first deploy — it runs ``CREATE TABLE IF NOT
EXISTS`` for every model against whatever ``DATABASE_URL`` / ``DB_*`` points at.
For evolving a live schema, use Alembic instead (see db/README.md); this command
does not diff or migrate.
"""
from __future__ import annotations

import sys

from . import config as db_config
from .engine import init_db


def main() -> None:
    cfg = db_config.load_config()
    if not cfg.enabled():
        print(
            "No database configured. Set DATABASE_URL, or DB_NAME (+ DB_USER/"
            "DB_PASSWORD/DB_HOST/DB_PORT). Nothing to do.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    # Mask credentials when echoing the target.
    shown = cfg.url
    if "@" in shown:
        shown = shown.split("@", 1)[0].rsplit(":", 1)[0] + ":***@" + shown.split("@", 1)[1]
    print(f"Creating schema on: {shown}")
    init_db()
    print("Done.")


if __name__ == "__main__":
    main()
