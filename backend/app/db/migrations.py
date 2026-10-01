"""File-based SQL migration runner.

Applies numbered ``*.sql`` files from ``database/migrations/`` in order,
recording each one in a ``schema_migrations`` table. Works on SQLite and
PostgreSQL.

Idempotency on fresh databases: a migration statement may declare a
precondition that marks it as already-satisfied::

    -- requires-missing-column: xray_uploads.report_parsed
    ALTER TABLE xray_uploads ADD COLUMN report_parsed JSON;

A guarded statement runs only when its target column does NOT exist,
so the same set of migrations runs safely against both brand-new
databases (where ``Base.metadata.create_all`` already created current
columns) and older deployed ones. A file is recorded as ``applied``
when at least one statement ran, otherwise as ``skipped``.

Statements altering a table that may not exist at all in very old
schemas can require the table to be present::

    -- requires-table: progress
    ALTER TABLE progress ADD COLUMN source VARCHAR(16);

Usage (programmatic)::

    from app.db.migrations import run_migrations
    run_migrations(engine)

Usage (CLI)::

    python -m app.db.migrations
"""
from __future__ import annotations

import re
import sqlalchemy as sa
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "database" / "migrations"

_GUARD_RE = re.compile(r"^--\s*requires-missing-column:\s*(\w+)\.(\w+)\s*$")
_TABLE_REQ_RE = re.compile(r"^--\s*requires-table:\s*(\w+)\s*$")


def _parse_blocks(sql: str) -> list[tuple[list[tuple[str, str]], list[str], str]]:
    """Split a migration file into ``(column_reqs, table_reqs, statement)``.

    A ``-- requires-missing-column: table.column`` directive applies to
    the statement that follows it; the statement runs only while that
    column is absent. ``-- requires-table: name`` runs the statement only
    when the table itself exists. Files are simple DDL, so splitting on
    ``;`` is sufficient; comment-only blocks are dropped.
    """
    blocks: list[tuple[list[tuple[str, str]], list[str], str]] = []
    for chunk in sql.split(";"):
        column_reqs: list[tuple[str, str]] = []
        table_reqs: list[str] = []
        body: list[str] = []
        for line in chunk.splitlines():
            col_match = _GUARD_RE.match(line.strip())
            if col_match:
                column_reqs.append((col_match.group(1), col_match.group(2)))
                continue
            table_match = _TABLE_REQ_RE.match(line.strip())
            if table_match:
                table_reqs.append(table_match.group(1))
                continue
            if not line.strip().startswith("--") and line.strip():
                body.append(line)
        if body:
            blocks.append((column_reqs, table_reqs, chunk.strip()))
    return blocks


def _existing_columns(conn: sa.Connection, table: str) -> set[str]:
    if conn.dialect.name == "sqlite":
        rows = conn.execute(sa.text(f"PRAGMA table_info({table})")).mappings()
        return {row["name"] for row in rows}
    rows = conn.execute(
        sa.text("SELECT column_name FROM information_schema.columns WHERE table_name = :t"),
        {"t": table},
    ).mappings()
    return {row["column_name"] for row in rows}


def _ensure_tracking_table(conn: sa.Connection) -> None:
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename VARCHAR(255) PRIMARY KEY,
                status VARCHAR(16) NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )


def pending_migrations(engine: sa.Engine) -> list[Path]:
    """Return migration files not yet applied or skipped."""
    files = sorted(p for p in MIGRATIONS_DIR.glob("*.sql") if p.is_file())
    with engine.begin() as conn:
        _ensure_tracking_table(conn)
        done = {
            row["filename"]
            for row in conn.execute(sa.text("SELECT filename FROM schema_migrations")).mappings()
        }
    return [p for p in files if p.name not in done]


def _table_exists(conn: sa.Connection, table: str) -> bool:
    return bool(_existing_columns(conn, table))


def run_migrations(engine: sa.Engine) -> list[tuple[str, str]]:
    """Apply pending migrations. Returns [(filename, status), ...]."""
    applied: list[tuple[str, str]] = []
    with engine.begin() as conn:
        _ensure_tracking_table(conn)

    for path in pending_migrations(engine):
        blocks = _parse_blocks(path.read_text(encoding="utf-8"))
        ran_any = False
        with engine.begin() as conn:
            for column_reqs, table_reqs, statement in blocks:
                # Skip while guarded columns already exist; skip when a
                # required table is entirely absent (pre-date the feature).
                if all(column in _existing_columns(conn, table) for table, column in column_reqs):
                    continue
                if any(not _table_exists(conn, table) for table in table_reqs):
                    continue
                conn.execute(sa.text(statement))
                ran_any = True
            status = "applied" if ran_any else "skipped"
            conn.execute(
                sa.text("INSERT INTO schema_migrations (filename, status) VALUES (:f, :s)"),
                {"f": path.name, "s": status},
            )
        applied.append((path.name, status))
    return applied


if __name__ == "__main__":
    from app.db.session import engine

    results = run_migrations(engine)
    for name, status in results:
        print(f"{status:>8}  {name}")
    print(f"{len(results)} migration(s) processed")
