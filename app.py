import os
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import pandas as pd
import requests
from importlib import metadata

# --- DB MIGRATION ---
def setup_db():
    """Ensures the table exists and has all necessary columns."""
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
        # Add columns if they don't exist (for older existing databases)
        for col in ["matched_at", "tailored_at", "applied_at"]:
            try:
                conn.execute(text(f"ALTER TABLE job_leads ADD COLUMN {col} TIMESTAMP DEFAULT NULL"))
            except Exception:
                pass # Already exists

        # Update ENUM for status column
        try:
            conn.execute(text("ALTER TABLE job_leads MODIFY COLUMN status ENUM('new', 'approved', 'rejected', 'tailored', 'applied', 'archived') DEFAULT 'new'"))
        except Exception:
            pass
        conn.commit()

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

setup_db() # Run migration on start

RESUME_DIR = "resumes" # Ensure this matches your tailor.py path

st.set_page_config(page_title="WerkEsel Job Board", layout="wide")

# --- VERSION CHECK ---
@st.cache_data(ttl=3600)
def check_jobspy_update():
    try:
        package_name = "python-jobspy"
        current_version = metadata.version(package_name)

        response = requests.get(f"https://pypi.org/pypi/{package_name}/json", timeout=2)
        latest_version = response.json()["info"]["version"]

        if current_version != latest_version:
            return {
                "message": f"🔔 Update available for **{package_name}**: {current_version} ⮕ {latest_version}",
                "command": f"pip install --upgrade {package_name}"
            }
    except Exception:
        pass # Silently fail if check fails
    return None

st.title("🚜 WerkEsel: PM Job Matcher")
st.write("Reviewing jobs for **tefinitely.com**")

update_info = check_jobspy_update()
if update_info:
    st.warning(update_info["message"])
    st.code(update_info["command"])
# --- NEW: STATUS DASHBOARD ---
with engine.connect() as conn:
    stats_query = text("""
        SELECT 
            COUNT(CASE WHEN status = 'new' AND match_score IS NULL THEN 1 END) as unscored,
            COUNT(CASE WHEN status = 'new' AND match_score >= 70 THEN 1 END) as high_matches,
            COUNT(CASE WHEN status = 'approved' THEN 1 END) as pending_tailor,
            COUNT(CASE WHEN status = 'tailored' THEN 1 END) as ready_to_apply,
            COUNT(CASE WHEN status = 'applied' THEN 1 END) as applied,
            COUNT(CASE WHEN status = 'archived' THEN 1 END) as archived
        FROM job_leads
    """)
    stats = conn.execute(stats_query).fetchone()

# Display metrics in 6 columns
m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("📥 Unscored", stats[0])
m2.metric("🔥 High Matches", stats[1])
m3.metric("🧵 Pending Tailor", stats[2])
m4.metric("✅ Ready to Apply", stats[3])
m5.metric("🚀 Applied", stats[4])
m6.metric("🗑️ Archived", stats[5])

st.divider()

# --- FILTERING UI ---
st.subheader("📋 Job Leads")
filter_status = st.pills(
    "Filter by Status:",
    options=["All", "High Matches (New)", "Pending Tailor (Approved)", "Ready to Apply (Tailored)", "Applied", "Archived"],
    default="All"
)

status_map = {
    "High Matches (New)": "new",
    "Pending Tailor (Approved)": "approved",
    "Ready to Apply (Tailored)": "tailored",
    "Applied": "applied",
    "Archived": "archived"
}

# --- END STATUS DASHBOARD ---
# 1. Fetch Jobs
query = text("""
    SELECT id, title, company, match_score, ai_summary, job_url, status, created_at, matched_at, tailored_at, applied_at
    FROM job_leads 
    WHERE status IN ('new', 'approved', 'tailored', 'applied', 'archived')
    ORDER BY FIELD(status, 'tailored', 'applied', 'new', 'approved', 'archived'), match_score DESC
""")

with engine.connect() as conn:
    df = pd.read_sql(query, conn)

if df.empty:
    st.success("No jobs found. Run scout.py and matcher.py!")
else:
    # Apply UI filters
    if filter_status == "High Matches (New)":
        df = df[(df['status'] == 'new') & (df['match_score'] >= 70)]
    elif filter_status != "All":
        df = df[df['status'] == status_map[filter_status]]
    elif filter_status == "All":
        # By default, only show relevant jobs unless explicitly filtered
        df = df[((df['status'] == 'new') & (df['match_score'] >= 70)) | (df['status'].isin(['tailored', 'applied']))]

    if df.empty:
        st.info(f"No jobs found for filter: {filter_status}")
    else:
    for index, row in df.iterrows():
        job_id = row['id']
        status = row['status']
        company = row['company']
        
        with st.container():
            col1, col2 = st.columns([4, 1])
            
            with col1:
                st.subheader(f"{row['title']} @ {company}")

                # --- TIMESTAMPS ---
                ts_info = f"Scraped: {row['created_at'].strftime('%Y-%m-%d %H:%M')}"
                if pd.notnull(row['matched_at']):
                    ts_info += f" | Matched: {row['matched_at'].strftime('%Y-%m-%d %H:%M')}"
                if pd.notnull(row['tailored_at']):
                    ts_info += f" | Tailored: {row['tailored_at'].strftime('%Y-%m-%d %H:%M')}"
                if pd.notnull(row['applied_at']):
                    ts_info += f" | Applied: {row['applied_at'].strftime('%Y-%m-%d %H:%M')}"

                st.caption(f"Score: {row['match_score']}% | Status: {status.upper()} | [View Posting]({row['job_url']})")
                st.caption(ts_info)
                st.write(f"**AI Insight:** {row['ai_summary']}")
                
                # --- DOWNLOAD SECTION ---
                if status in ['tailored', 'applied']:
                    st.info("📂 Tailored documents are ready for download:")
                    d_col1, d_col2 = st.columns(2)
                    
                    resume_path = os.path.join(RESUME_DIR, f"{job_id}_Resume.pdf")
                    cl_path = os.path.join(RESUME_DIR, f"{job_id}_CoverLetter.pdf")

                    if os.path.exists(resume_path):
                        with open(resume_path, "rb") as f:
                            d_col1.download_button(
                                label="📥 Download Resume",
                                data=f,
                                file_name=f"Resume_{company.replace(' ', '_')}.pdf",
                                mime="application/pdf",
                                key=f"dl_res_{job_id}"
                            )
                    
                    if os.path.exists(cl_path):
                        with open(cl_path, "rb") as f:
                            d_col2.download_button(
                                label="📥 Download Cover Letter",
                                data=f,
                                file_name=f"CoverLetter_{company.replace(' ', '_')}.pdf",
                                mime="application/pdf",
                                key=f"dl_cl_{job_id}"
                            )
            
            with col2:
                # 1. Action Buttons based on status
                if status == 'approved':
                    st.info("🧵 Pending Tailoring (Run tailor.py)")

                if status == 'new':
                    if st.button("✅ Approve", key=f"app_{job_id}"):
                        with engine.connect() as conn:
                            conn.execute(text("UPDATE job_leads SET status = 'approved' WHERE id = :id"), {"id": job_id})
                            conn.commit()
                        st.rerun()
                    
                    if st.button("❌ Reject", key=f"rej_{job_id}"):
                        with engine.connect() as conn:
                            conn.execute(text("UPDATE job_leads SET status = 'rejected' WHERE id = :id"), {"id": job_id})
                            conn.commit()
                        st.rerun()

                elif status == 'tailored':
                    if st.button("🚀 Mark Applied", key=f"mark_app_{job_id}"):
                        with engine.connect() as conn:
                            conn.execute(text("UPDATE job_leads SET status = 'applied', applied_at = CURRENT_TIMESTAMP WHERE id = :id"), {"id": job_id})
                            conn.commit()
                        st.rerun()

                # 2. Secondary Actions (Archive) for non-new jobs
                if status in ['tailored', 'applied']:
                    if st.button("🗑️ Archive", key=f"arc_{job_id}"):
                        with engine.connect() as conn:
                            conn.execute(text("UPDATE job_leads SET status = 'archived' WHERE id = :id"), {"id": job_id})
                            conn.commit()
                        st.rerun()

                # 3. Permanent Deletion for archived jobs
                if status == 'archived':
                    if st.button("💀 Delete Permanently", key=f"del_{job_id}"):
                        # --- CLEANUP FILES ---
                        resume_path = os.path.join(RESUME_DIR, f"{job_id}_Resume.pdf")
                        cl_path = os.path.join(RESUME_DIR, f"{job_id}_CoverLetter.pdf")

                        if os.path.exists(resume_path):
                            os.remove(resume_path)
                        if os.path.exists(cl_path):
                            os.remove(cl_path)

                        # --- DELETE DB RECORD ---
                        with engine.connect() as conn:
                            conn.execute(text("DELETE FROM job_leads WHERE id = :id"), {"id": job_id})
                            conn.commit()
                        st.rerun()
            st.divider()