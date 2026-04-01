-- Update script for WerkEsel job_leads table
-- Adds matched_at and applied_at columns for tracking job lifecycle.

ALTER TABLE job_leads
ADD COLUMN matched_at TIMESTAMP DEFAULT NULL AFTER ai_summary,
ADD COLUMN applied_at TIMESTAMP DEFAULT NULL AFTER matched_at;
