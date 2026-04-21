import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")

DB_URL = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?charset=utf8mb4"
engine = create_engine(DB_URL)

def setup_db():
    """Ensures tables exist and have all necessary columns."""
    with engine.connect() as conn:
        # Users Table
        conn.execute(text("""
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
            )
        """))

        # Search Profiles Table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS search_profiles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                name VARCHAR(255) NOT NULL,
                profile_text TEXT,
                search_params JSON,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """))

        # Migration for existing users
        try:
            conn.execute(text("SELECT verification_code FROM users LIMIT 1"))
        except Exception:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN verification_code VARCHAR(10) AFTER is_verified"))
            except Exception:
                pass

        for col in [("phone", "VARCHAR(50)"), ("location", "VARCHAR(255)"), ("linkedin_url", "VARCHAR(255)"), ("website_url", "VARCHAR(255)"), ("header_template", "TEXT"), ("match_threshold", "INT DEFAULT 70")]:
            try:
                conn.execute(text(f"SELECT {col[0]} FROM users LIMIT 1"))
            except Exception:
                try:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {col[0]} {col[1]}"))
                except Exception:
                    pass

        # Job Leads Table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS job_leads (
                id INT AUTO_INCREMENT PRIMARY KEY,
                profile_id INT,
                job_id VARCHAR(255),
                site VARCHAR(50),
                title VARCHAR(255),
                company VARCHAR(255),
                location VARCHAR(255),
                job_url TEXT,
                description TEXT,
                is_remote BOOLEAN DEFAULT FALSE,
                date_posted DATE,
            status ENUM('new', 'approved', 'rejected', 'tailored', 'applied', 'archived', 'interview') DEFAULT 'new',
                match_score INT DEFAULT NULL,
                ai_summary TEXT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                matched_at TIMESTAMP DEFAULT NULL,
                tailored_at TIMESTAMP DEFAULT NULL,
                applied_at TIMESTAMP DEFAULT NULL,
                CONSTRAINT fk_profile FOREIGN KEY (profile_id) REFERENCES search_profiles(id) ON DELETE CASCADE,
                UNIQUE KEY unique_job_per_profile (job_id, profile_id)
            )
        """))

        # Migration for existing job_leads
        try:
            # 1. Add profile_id if it doesn't exist
            conn.execute(text("SELECT profile_id FROM job_leads LIMIT 1"))
        except Exception:
            try:
                conn.execute(text("ALTER TABLE job_leads ADD COLUMN profile_id INT AFTER id"))
                print("Added profile_id column to job_leads.")
            except Exception as e:
                print(f"Error adding profile_id: {e}")

        try:
            # 2. Add foreign key if it doesn't exist
            conn.execute(text("ALTER TABLE job_leads ADD CONSTRAINT fk_profile FOREIGN KEY (profile_id) REFERENCES search_profiles(id) ON DELETE CASCADE"))
            print("Added foreign key constraint fk_profile.")
        except Exception:
            pass

        try:
            # 3. Update Unique Key
            conn.execute(text("ALTER TABLE job_leads DROP INDEX job_id"))
            print("Dropped old unique index job_id.")
        except Exception:
            pass

        try:
            conn.execute(text("ALTER TABLE job_leads ADD UNIQUE KEY unique_job_per_profile (job_id, profile_id)"))
            print("Added unique key unique_job_per_profile.")
        except Exception:
            pass

        conn.commit()
