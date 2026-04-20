import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from jobspy import scrape_jobs
import logging
import random

# --- CONFIG ---
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
    """Ensures the table exists with all necessary columns."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS job_leads (
                id INT AUTO_INCREMENT PRIMARY KEY,
                job_id VARCHAR(255) UNIQUE,
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
                applied_at TIMESTAMP DEFAULT NULL
            )
        """))
        # Add columns if they don't exist (for existing databases)
        try:
            conn.execute(text("ALTER TABLE job_leads ADD COLUMN matched_at TIMESTAMP DEFAULT NULL"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE job_leads ADD COLUMN tailored_at TIMESTAMP DEFAULT NULL"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE job_leads ADD COLUMN applied_at TIMESTAMP DEFAULT NULL"))
        except Exception:
            pass
        # Update ENUM for status column
        try:
            conn.execute(text("ALTER TABLE job_leads MODIFY COLUMN status ENUM('new', 'approved', 'rejected', 'tailored', 'applied', 'archived') DEFAULT 'new'"))
        except Exception:
            pass
        conn.commit()
    print("✅ Database table verified.")

def run_scout():
    print("🚀 Starting Product Manager Job Scout...")
    
    # Define our two search passes
    search_queries = [
        {"location": "Toronto, ON", "is_remote": False}, # Local/Hybrid Toronto
        {"location": "Toronto, ON", "is_remote": True}   # Remote roles available in Canada
    ]
    
    all_found_jobs = []

    for query in search_queries:
        loc_label = query['location'] if not query['is_remote'] else "Remote (Canada)"
        print(f"🔍 Searching in {loc_label}...")
        
        try:
            # JobSpy pulls from LinkedIn, Indeed, and Glassdoor
            jobs = scrape_jobs(
                site_name=["linkedin", "indeed", "glassdoor"],
                search_term="Product Manager",
                location=query['location'],
                is_remote=query['is_remote'],
                results_wanted=20,
                hours_old=24,
		enforce_desktop=True,
                country_indeed='canada' 
            )
            
            if not jobs.empty:
                # Add the is_remote flag for our DB
                jobs['is_remote'] = query['is_remote']
                all_found_jobs.append(jobs)
                
        except Exception as e:
            print(f"⚠️ Error during {loc_label} search: {e}")

    if not all_found_jobs:
        print("📭 No new jobs found in this cycle.")
        return

    # Combine results and drop duplicates from the search itself
    df = pd.concat(all_found_jobs).drop_duplicates(subset=['id'])
    
    # Clean and rename columns to match our DB schema
    df = df[['id', 'site', 'title', 'company', 'location', 'job_url', 'description', 'date_posted', 'is_remote']]
    df = df.rename(columns={'id': 'job_id'})

    # Save to MySQL with duplicate handling
    new_entries = 0
    for _, row in df.iterrows():
        try:
            # Convert row to a small dataframe for to_sql
            row_df = pd.DataFrame([row])
            row_df.to_sql('job_leads', con=engine, if_exists='append', index=False)
            new_entries += 1
        except Exception:
            # This triggers if job_id already exists in the UNIQUE column
            continue

    print(f"✅ Success! Found {len(df)} jobs. Added {new_entries} NEW entries to the database.")

if __name__ == "__main__":
    setup_db()
    run_scout()
