import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from jobspy import scrape_jobs
import logging
import random
import json
from db_utils import engine, setup_db

# --- CONFIG ---
import os
# Load the variables from the .env file
load_dotenv()

def run_scout_for_profile(profile_id, profile_name, search_params):
    """Runs the scout for a specific profile. Returns count of new entries."""
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
        sites = query.get('sites', ["linkedin", "indeed", "glassdoor"])

        loc_label = location if not is_remote else f"Remote ({country_indeed})"
        print(f"🔍 Searching for '{search_term}' in {loc_label} using sites {sites}...")
        
        try:
            jobs = scrape_jobs(
                site_name=sites,
                search_term=search_term,
                location=location,
                is_remote=is_remote,
                results_wanted=query.get('results_wanted', 20),
                hours_old=query.get('hours_old', 24),
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
    return new_entries

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
