"""Tests for the file-based SQL migration runner."""
from __future__ import annotations

import sqlalchemy as sa

from app.db.migrations import run_migrations


def _fresh_engine(tmp_path, name: str):
    return sa.create_engine(f"sqlite:///{tmp_path / name}")


def _old_schema(engine) -> None:
    """Create tables WITHOUT the columns the migrations add (legacy DB)."""
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                """
                CREATE TABLE xray_uploads (
                    id VARCHAR(36) PRIMARY KEY,
                    owner_id INTEGER
                )
                """
            )
        )
        conn.execute(
            sa.text(
                """
                CREATE TABLE rehabilitation_recommendations (
                    id VARCHAR(36) PRIMARY KEY,
                    upload_id VARCHAR(36)
                )
                """
            )
        )


def test_migrations_apply_to_legacy_database(tmp_path):
    engine = _fresh_engine(tmp_path, "legacy.db")
    _old_schema(engine)

    results = run_migrations(engine)
    statuses = dict(results)
    assert statuses["001_add_xray_report_columns.sql"] == "applied"
    assert statuses["002_add_recommendation_affected_side.sql"] == "applied"
    # No progress table in this legacy schema -> 004 must skip, not crash.
    assert statuses["004_add_progress_session_metrics.sql"] == "skipped"

    with engine.begin() as conn:
        cols = {r["name"] for r in conn.execute(sa.text("PRAGMA table_info(xray_uploads)")).mappings()}
        assert {"xray_report", "report_parsed"}.issubset(cols)
        rec_cols = {
            r["name"]
            for r in conn.execute(
                sa.text("PRAGMA table_info(rehabilitation_recommendations)")
            ).mappings()
        }
        assert "affected_side" in rec_cols

    # Running again is a no-op — everything already tracked.
    assert run_migrations(engine) == []


def test_migrations_skip_on_fresh_current_schema(tmp_path):
    """On a brand-new DB create_all already made the columns, so the
    guarded migrations must be recorded as skipped, not executed."""
    engine = _fresh_engine(tmp_path, "fresh.db")
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                """
                CREATE TABLE xray_uploads (
                    id VARCHAR(36) PRIMARY KEY,
                    xray_report TEXT,
                    report_parsed JSON
                )
                """
            )
        )
        conn.execute(
            sa.text(
                """
                CREATE TABLE rehabilitation_recommendations (
                    id VARCHAR(36) PRIMARY KEY,
                    affected_side VARCHAR(16) DEFAULT 'right' NOT NULL
                )
                """
            )
        )

    results = run_migrations(engine)
    statuses = dict(results)
    assert statuses["001_add_xray_report_columns.sql"] == "skipped"
    assert statuses["002_add_recommendation_affected_side.sql"] == "skipped"

    with engine.begin() as conn:
        rows = list(conn.execute(sa.text("SELECT filename FROM schema_migrations")).mappings())
        from app.db.migrations import MIGRATIONS_DIR

        assert len(rows) == len(list(MIGRATIONS_DIR.glob("*.sql")))


def test_migrations_partial_guard(tmp_path):
    """A table missing only one guarded column still gets that file applied."""
    engine = _fresh_engine(tmp_path, "partial.db")
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                """
                CREATE TABLE xray_uploads (
                    id VARCHAR(36) PRIMARY KEY,
                    xray_report TEXT
                )
                """
            )
        )
        conn.execute(sa.text("CREATE TABLE rehabilitation_recommendations (id VARCHAR(36) PRIMARY KEY)"))

    results = run_migrations(engine)
    statuses = dict(results)
    # report_parsed is missing -> guard not fully satisfied -> apply.
    assert statuses["001_add_xray_report_columns.sql"] == "applied"
    assert statuses["002_add_recommendation_affected_side.sql"] == "applied"


def test_progress_metrics_migration_applies_to_old_progress_table(tmp_path):
    """An old DB that HAS a progress table gets the new columns added."""
    engine = _fresh_engine(tmp_path, "old-progress.db")
    _old_schema(engine)
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                """
                CREATE TABLE progress (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36),
                    pain_level INTEGER
                )
                """
            )
        )

    results = run_migrations(engine)
    assert dict(results)["004_add_progress_session_metrics.sql"] == "applied"

    with engine.begin() as conn:
        cols = {r["name"] for r in conn.execute(sa.text("PRAGMA table_info(progress)")).mappings()}
        assert {
            "exercise_session_id", "form_score", "reps_completed",
            "duration_seconds", "source",
        }.issubset(cols)

    # Running again is a no-op.
    assert run_migrations(engine) == []
