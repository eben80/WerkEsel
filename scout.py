import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from jobspy import scrape_jobs
import logging
import random
import json

# --- CONFIG ---
import os
# Load the variables from the .env file
load_dotenv()
# Build the URL dynamically
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")

DB_URL = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"

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
                status ENUM('new', 'approved', 'rejected', 'tailored', 'applied', 'archived') DEFAULT 'new',
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
            except Exception:
                pass

        try:
            # 2. Add foreign key if it doesn't exist
            conn.execute(text("ALTER TABLE job_leads ADD CONSTRAINT fk_profile FOREIGN KEY (profile_id) REFERENCES search_profiles(id) ON DELETE CASCADE"))
        except Exception:
            pass

        try:
            # 3. Update Unique Key
            conn.execute(text("ALTER TABLE job_leads DROP INDEX job_id"))
        except Exception:
            pass

        try:
            conn.execute(text("ALTER TABLE job_leads ADD UNIQUE KEY unique_job_per_profile (job_id, profile_id)"))
        except Exception:
            pass

        conn.commit()
    print("✅ Database tables verified.")

def run_scout_for_profile(profile_id, profile_name, search_params):
    print(f"🚀 Starting Scout for Profile: {profile_name} (ID: {profile_id})...")
    
    # search_params is a list of dictionaries, e.g., [{"search_term": "Product Manager", "location": "Toronto", "is_remote": False}]
    if not search_params:
        print(f"⚠️ No search parameters defined for profile {profile_name}")
        return

    all_found_jobs = []

    for query in search_params:
        search_term = query.get('search_term', 'Product Manager')
        location = query.get('location', 'Toronto, ON')
        is_remote = query.get('is_remote', False)
        country_indeed = query.get('country_indeed', 'canada')

        loc_label = location if not is_remote else f"Remote ({country_indeed})"
        print(f"🔍 Searching for '{search_term}' in {loc_label}...")
        
        try:
            jobs = scrape_jobs(
                site_name=["linkedin", "indeed", "glassdoor"],
                search_term=search_term,
                location=location,
                is_remote=is_remote,
                results_wanted=20,
                hours_old=24,
                enforce_desktop=True,
                country_indeed=country_indeed
            )
            
            if not jobs.empty:
                jobs['is_remote'] = is_remote
                jobs['profile_id'] = profile_id
                all_found_jobs.append(jobs)
                
        except Exception as e:
            print(f"⚠️ Error during {loc_label} search: {e}")

    if not all_found_jobs:
        print(f"📭 No new jobs found for profile {profile_name}.")
        return

    df = pd.concat(all_found_jobs).drop_duplicates(subset=['id'])
    df = df[['id', 'site', 'title', 'company', 'location', 'job_url', 'description', 'date_posted', 'is_remote', 'profile_id']]
    df = df.rename(columns={'id': 'job_id'})

    new_entries = 0
    for _, row in df.iterrows():
        try:
            row_df = pd.DataFrame([row])
            row_df.to_sql('job_leads', con=engine, if_exists='append', index=False)
            new_entries += 1
        except Exception:
            continue

    print(f"✅ Success for {profile_name}! Found {len(df)} jobs. Added {new_entries} NEW entries.")

def run_scout_all():
    with engine.connect() as conn:
        profiles = conn.execute(text("SELECT id, name, search_params FROM search_profiles WHERE is_active = TRUE")).fetchall()

    if not profiles:
        print("📭 No active search profiles found.")
        return

    for profile_id, name, search_params_raw in profiles:
        search_params = json.loads(search_params_raw) if isinstance(search_params_raw, str) else search_params_raw
        run_scout_for_profile(profile_id, name, search_params)

if __name__ == "__main__":
    setup_db()
    run_scout_all()
