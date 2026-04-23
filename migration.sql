-- WerkEsel Multi-User Migration Script
-- This script sets up the necessary tables for multi-user and multi-profile support.
-- It also performs migrations on the existing job_leads table.

-- 1. Create Users Table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    google_id VARCHAR(255) UNIQUE,
    name VARCHAR(255),
    role ENUM('admin', 'user') DEFAULT 'user',
    is_verified BOOLEAN DEFAULT FALSE,
    verification_code VARCHAR(10),
    phone VARCHAR(50),
    location VARCHAR(255),
    linkedin_url VARCHAR(255),
    website_url VARCHAR(255),
    header_template TEXT,
    match_threshold INT DEFAULT 70,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Create Search Profiles Table
CREATE TABLE IF NOT EXISTS search_profiles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    profile_text TEXT,
    search_params JSON,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 2b. Activity Logs Table
CREATE TABLE IF NOT EXISTS user_activity (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action VARCHAR(255),
    details TEXT,
    ip_address VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- 3. Migrate Users Table (if it already existed without verification_code)
-- Using a procedure to safely check for column existence
DROP PROCEDURE IF EXISTS MigrateUsers;
DELIMITER //
CREATE PROCEDURE MigrateUsers()
BEGIN
    IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'users' AND COLUMN_NAME = 'verification_code') THEN
        ALTER TABLE users ADD COLUMN verification_code VARCHAR(10) AFTER is_verified;
    END IF;
    IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'users' AND COLUMN_NAME = 'phone') THEN
        ALTER TABLE users ADD COLUMN phone VARCHAR(50);
    END IF;
    IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'users' AND COLUMN_NAME = 'location') THEN
        ALTER TABLE users ADD COLUMN location VARCHAR(255);
    END IF;
    IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'users' AND COLUMN_NAME = 'linkedin_url') THEN
        ALTER TABLE users ADD COLUMN linkedin_url VARCHAR(255);
    END IF;
    IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'users' AND COLUMN_NAME = 'website_url') THEN
        ALTER TABLE users ADD COLUMN website_url VARCHAR(255);
    END IF;
    IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'users' AND COLUMN_NAME = 'header_template') THEN
        ALTER TABLE users ADD COLUMN header_template TEXT;
    END IF;
    IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'users' AND COLUMN_NAME = 'match_threshold') THEN
        ALTER TABLE users ADD COLUMN match_threshold INT DEFAULT 70;
    END IF;
END //
DELIMITER ;
CALL MigrateUsers();
DROP PROCEDURE MigrateUsers;

-- 4. Migrate Job Leads Table
DROP PROCEDURE IF EXISTS MigrateJobLeads;
DELIMITER //
CREATE PROCEDURE MigrateJobLeads()
BEGIN
    -- Add profile_id column
    IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'job_leads' AND COLUMN_NAME = 'profile_id') THEN
        ALTER TABLE job_leads ADD COLUMN profile_id INT AFTER id;
    END IF;

    -- Add foreign key constraint
    -- We check if the constraint exists by looking for the constraint name in information_schema
    IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS WHERE CONSTRAINT_NAME = 'fk_profile' AND TABLE_NAME = 'job_leads') THEN
        ALTER TABLE job_leads ADD CONSTRAINT fk_profile FOREIGN KEY (profile_id) REFERENCES search_profiles(id) ON DELETE CASCADE;
    END IF;

    -- Update Status Enum
    ALTER TABLE job_leads MODIFY COLUMN status ENUM('new', 'approved', 'rejected', 'tailored', 'applied', 'archived', 'interview') DEFAULT 'new';

    -- Drop old unique index on job_id if it exists
    IF EXISTS (SELECT * FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_NAME = 'job_leads' AND INDEX_NAME = 'job_id') THEN
        ALTER TABLE job_leads DROP INDEX job_id;
    END IF;

    -- Add new unique index on (job_id, profile_id)
    IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_NAME = 'job_leads' AND INDEX_NAME = 'unique_job_per_profile') THEN
        ALTER TABLE job_leads ADD UNIQUE KEY unique_job_per_profile (job_id, profile_id);
    END IF;

    -- Add is_manual column
    IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'job_leads' AND COLUMN_NAME = 'is_manual') THEN
        ALTER TABLE job_leads ADD COLUMN is_manual BOOLEAN DEFAULT FALSE;
    END IF;
END //
DELIMITER ;
CALL MigrateJobLeads();
DROP PROCEDURE MigrateJobLeads;
