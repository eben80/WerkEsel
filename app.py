import os
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import pandas as pd

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
RESUME_DIR = "resumes" # Ensure this matches your tailor.py path

st.set_page_config(page_title="WerkEsel Job Board", layout="wide")

st.title("🚜 WerkEsel: PM Job Matcher")
st.write("Reviewing jobs for **tefinitely.com**")
# --- NEW: STATUS DASHBOARD ---
with engine.connect() as conn:
    stats_query = text("""
        SELECT 
            COUNT(CASE WHEN status = 'new' AND match_score IS NULL THEN 1 END) as unscored,
            COUNT(CASE WHEN status = 'new' AND match_score >= 70 THEN 1 END) as high_matches,
            COUNT(CASE WHEN status = 'approved' THEN 1 END) as pending_tailor,
            COUNT(CASE WHEN status = 'applied' THEN 1 END) as ready_to_download
        FROM job_leads
    """)
    stats = conn.execute(stats_query).fetchone()

# Display metrics in 4 columns
m1, m2, m3, m4 = st.columns(4)
m1.metric("📥 Unscored Jobs", stats[0])
m2.metric("🔥 High Matches", stats[1])
m3.metric("🧵 Pending Tailor", stats[2])
m4.metric("✅ Ready to Apply", stats[3])

st.divider()
# --- END STATUS DASHBOARD ---
# 1. Fetch Jobs: Show 'new' high-scores AND 'applied' (tailored) jobs
query = text("""
    SELECT id, title, company, match_score, ai_summary, job_url, status, created_at, matched_at, applied_at
    FROM job_leads 
    WHERE (match_score >= 70 AND status = 'new') OR status = 'applied'
    ORDER BY status DESC, match_score DESC
""")

with engine.connect() as conn:
    df = pd.read_sql(query, conn)

if df.empty:
    st.success("No new high-match jobs. Run scout.py and matcher.py!")
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
                if pd.notnull(row['applied_at']):
                    ts_info += f" | Tailored: {row['applied_at'].strftime('%Y-%m-%d %H:%M')}"

                st.caption(f"Score: {row['match_score']}% | Status: {status.upper()} | [View Posting]({row['job_url']})")
                st.caption(ts_info)
                st.write(f"**AI Insight:** {row['ai_summary']}")
                
                # --- DOWNLOAD SECTION ---
                if status == 'applied':
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
                # Only show Approve/Reject if it's still in 'new' status
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
                else:
                    # Option to archive/reset if you want to re-run it later
                    if st.button("🗑️ Archive", key=f"arc_{job_id}"):
                        with engine.connect() as conn:
                            conn.execute(text("UPDATE job_leads SET status = 'archived' WHERE id = :id"), {"id": job_id})
                            conn.commit()
                        st.rerun()
            st.divider()