# Database migrations

Lightweight file-based SQL migrations applied by
`backend/app/db/migrations.py` on app startup (`init_db`) or manually:

```powershell
cd backend
python -m app.db.migrations
```

## Conventions

- Files are named `NNN_description.sql` and run in filename order.
- Each file runs at most once — tracked in the `schema_migrations` table.
- A file may declare preconditions that mark it as already-satisfied,
  so it is skipped on fresh databases where `create_all` already created
  the current schema:

  ```sql
  -- requires-missing-column: table_name.column_name
  ```

- Keep migrations additive (`ADD COLUMN`) and engine-neutral so they work
  on both SQLite (dev) and PostgreSQL (production).

## Applied

| File | Purpose |
|------|---------|
| `001_add_xray_report_columns.sql` | Patient-supplied X-ray report text + parsed JSON on `xray_uploads` |
| `002_add_recommendation_affected_side.sql` | `affected_side` on `rehabilitation_recommendations` |

## Planned future migrations

- 003_add_model_registry.sql
- 004_add_analysis_snapshots.sql
