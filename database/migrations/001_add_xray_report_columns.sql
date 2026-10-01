-- Adds patient-supplied X-ray report columns for older databases.
-- Each guard applies to the statement that follows it.

-- requires-missing-column: xray_uploads.xray_report
ALTER TABLE xray_uploads ADD COLUMN xray_report TEXT;

-- requires-missing-column: xray_uploads.report_parsed
ALTER TABLE xray_uploads ADD COLUMN report_parsed JSON;
