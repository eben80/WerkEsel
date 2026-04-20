-- Update script for WerkEsel job_leads table
-- Adds matched_at, tailored_at, and applied_at columns for tracking job lifecycle.
-- Updates status ENUM to include 'tailored'.

ALTER TABLE job_leads
ADD COLUMN matched_at TIMESTAMP DEFAULT NULL AFTER ai_summary,
ADD COLUMN tailored_at TIMESTAMP DEFAULT NULL AFTER matched_at,
ADD COLUMN applied_at TIMESTAMP DEFAULT NULL AFTER tailored_at;

ALTER TABLE job_leads
MODIFY COLUMN status ENUM('new', 'approved', 'rejected', 'tailored', 'applied', 'archived') DEFAULT 'new';
