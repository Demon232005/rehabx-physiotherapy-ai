-- Auto-logged exercise-session metrics on progress entries.
-- Rows created from a completed LiveCoach session carry these values;
-- manual entries leave them NULL. Guards keep fresh databases safe and
-- skip entirely on schemas that predate the progress table.

-- requires-table: progress
-- requires-missing-column: progress.exercise_session_id
ALTER TABLE progress ADD COLUMN exercise_session_id VARCHAR(32) REFERENCES exercise_sessions(id);

-- requires-table: progress
-- requires-missing-column: progress.form_score
ALTER TABLE progress ADD COLUMN form_score INTEGER;

-- requires-table: progress
-- requires-missing-column: progress.reps_completed
ALTER TABLE progress ADD COLUMN reps_completed INTEGER;

-- requires-table: progress
-- requires-missing-column: progress.duration_seconds
ALTER TABLE progress ADD COLUMN duration_seconds INTEGER;

-- requires-table: progress
-- requires-missing-column: progress.source
ALTER TABLE progress ADD COLUMN source VARCHAR(16) DEFAULT 'manual';
