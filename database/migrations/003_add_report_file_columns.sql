-- Stores the original uploaded X-ray report file so it can be shown
-- back to the user in the UI.
-- requires-missing-column: xray_uploads.report_file_key
ALTER TABLE xray_uploads ADD COLUMN report_file_key VARCHAR(255);

-- requires-missing-column: xray_uploads.report_file_name
ALTER TABLE xray_uploads ADD COLUMN report_file_name VARCHAR(255);
