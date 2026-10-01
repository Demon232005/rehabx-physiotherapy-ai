-- Adds affected_side to rehabilitation recommendations for older databases.
-- requires-missing-column: rehabilitation_recommendations.affected_side

ALTER TABLE rehabilitation_recommendations ADD COLUMN affected_side VARCHAR(16) DEFAULT 'right' NOT NULL;
