-- 005: Upper-limb platform fields on the exercise library.
-- Adds tracking/AI metadata columns so elbow & shoulder exercises can declare
-- how they are tracked (hand landmarks / pose landmarks / both) alongside
-- their clinical classification. Nullable — legacy hand rows stay valid.

-- requires-table: exercises

ALTER TABLE exercises ADD COLUMN category VARCHAR(64);
ALTER TABLE exercises ADD COLUMN tracking_mode VARCHAR(16);
ALTER TABLE exercises ADD COLUMN duration_minutes INTEGER;
ALTER TABLE exercises ADD COLUMN progression_level INTEGER;
