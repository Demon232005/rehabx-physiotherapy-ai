-- 006: report-driven rehabilitation - laterality snapshots + extraction.
-- Sessions/progress carry the injury (side + region + structure) extracted
-- from the driving report; recommendations store the structured extraction.

-- requires-table: exercise_sessions
-- requires-missing-column: exercise_sessions.affected_side
ALTER TABLE exercise_sessions ADD COLUMN affected_side VARCHAR(16);

-- requires-table: exercise_sessions
-- requires-missing-column: exercise_sessions.body_region
ALTER TABLE exercise_sessions ADD COLUMN body_region VARCHAR(64);

-- requires-table: exercise_sessions
-- requires-missing-column: exercise_sessions.specific_structure
ALTER TABLE exercise_sessions ADD COLUMN specific_structure VARCHAR(64);

-- requires-table: progress
-- requires-missing-column: progress.affected_side
ALTER TABLE progress ADD COLUMN affected_side VARCHAR(16);

-- requires-table: progress
-- requires-missing-column: progress.body_region
ALTER TABLE progress ADD COLUMN body_region VARCHAR(64);

-- requires-table: progress
-- requires-missing-column: progress.specific_structure
ALTER TABLE progress ADD COLUMN specific_structure VARCHAR(64);

-- requires-table: rehabilitation_recommendations
-- requires-missing-column: rehabilitation_recommendations.extraction
ALTER TABLE rehabilitation_recommendations ADD COLUMN extraction JSON;
