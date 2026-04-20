import streamlit as st
import os
import json
import pandas as pd
from sqlalchemy import create_engine, text, bindparam
from dotenv import load_dotenv

# --- CONFIG ---
load_dotenv()

import auth
from importlib import metadata
import requests

DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_URL = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"
engine = create_engine(DB_URL)
RESUME_DIR = "resumes"
os.makedirs(RESUME_DIR, exist_ok=True)

# --- DB MIGRATION ---
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

        # Migration for existing users
        try:
            conn.execute(text("SELECT verification_code FROM users LIMIT 1"))
        except Exception:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN verification_code VARCHAR(10) AFTER is_verified"))
            except Exception:
                pass

        for col in [("phone", "VARCHAR(50)"), ("location", "VARCHAR(255)"), ("linkedin_url", "VARCHAR(255)"), ("website_url", "VARCHAR(255)"), ("header_template", "TEXT")]:
            try:
                conn.execute(text(f"SELECT {col[0]} FROM users LIMIT 1"))
            except Exception:
                try:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {col[0]} {col[1]}"))
                except Exception:
                    pass

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
            pass # Probably already exists

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

setup_db()

st.set_page_config(page_title="WerkEsel Job Assistant", layout="wide", page_icon="🫏")

# --- SESSION STATE ---
if "user" not in st.session_state:
    st.session_state.user = None
if "profile_id" not in st.session_state:
    st.session_state.profile_id = None

# --- AUTH UI ---
def login_page():
    st.title("🫏 WerkEsel: Login")

    tab1, tab2, tab3, tab4 = st.tabs(["Login", "Sign Up", "Verify Email", "Google Login"])

    with tab1:
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            user = auth.login_user(engine, email, password)
            if user:
                if not user['is_verified']:
                    st.warning("Please verify your email before logging in.")
                else:
                    st.session_state.user = user
                    st.success(f"Welcome back, {user['name']}!")
                    st.rerun()
            else:
                st.error("Invalid email or password.")

    with tab2:
        new_name = st.text_input("Full Name", key="reg_name")
        new_email = st.text_input("Email", key="reg_email")
        new_pass = st.text_input("Password", type="password", key="reg_pass")
        if st.button("Register"):
            if auth.signup_user(engine, new_email, new_pass, new_name):
                st.success("Registration successful! Please check your email for the verification code and enter it in the 'Verify Email' tab.")
            else:
                st.error("Registration failed. Email might already be in use.")

    with tab3:
        v_email = st.text_input("Email", key="v_email")
        v_code = st.text_input("Verification Code", key="v_code")
        if st.button("Verify"):
            if auth.verify_user_code(engine, v_email, v_code):
                st.success("Email verified! You can now log in.")
            else:
                st.error("Invalid email or verification code.")

    with tab4:
        st.write("Google Login integration placeholder.")
        # In a real app, you'd use a Google Login button that returns a JWT token
        # For this demo, let's assume we get a token from a frontend component
        token = st.text_input("Paste Google JWT Token (Demo purposes)")
        if st.button("Login with Google"):
            id_info = auth.verify_google_token(token)
            if id_info:
                user = auth.get_or_create_google_user(engine, id_info)
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Invalid Google Token.")

# --- MAIN APP ---
def main():
    if not st.session_state.user:
        login_page()
        return

    user = st.session_state.user
    st.sidebar.title(f"🫏 {user['name']}")
    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.rerun()

    menu = ["Dashboard", "Profiles", "Jobs", "User Settings"]
    if user['role'] == 'admin':
        menu.append("Admin Panel")

    choice = st.sidebar.selectbox("Navigation", menu)

    if choice == "Dashboard":
        show_dashboard()
    elif choice == "Profiles":
        show_profiles()
    elif choice == "Jobs":
        show_jobs()
    elif choice == "User Settings":
        show_user_settings()
    elif choice == "Admin Panel":
        show_admin()

def show_dashboard():
    st.title("🚀 Dashboard")
    # Stats query for all user's profiles
    with engine.connect() as conn:
        stats = conn.execute(text("""
            SELECT
                COUNT(CASE WHEN status = 'new' AND match_score IS NULL THEN 1 END) as unscored,
                COUNT(CASE WHEN status = 'new' AND match_score >= 70 THEN 1 END) as high_matches,
                COUNT(CASE WHEN status = 'approved' THEN 1 END) as pending_tailor,
                COUNT(CASE WHEN status = 'tailored' THEN 1 END) as ready_to_apply
            FROM job_leads jl
            JOIN search_profiles sp ON jl.profile_id = sp.id
            WHERE sp.user_id = :user_id
        """), {"user_id": st.session_state.user['id']}).fetchone()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📥 Unscored", stats[0])
    m2.metric("🔥 High Matches", stats[1])
    m3.metric("🧵 Pending Tailor", stats[2])
    m4.metric("✅ Ready to Apply", stats[3])

def show_profiles():
    st.title("📂 Search Profiles")
    user_id = st.session_state.user['id']

    with engine.connect() as conn:
        profiles = conn.execute(text("SELECT id, name, is_active, profile_text, search_params FROM search_profiles WHERE user_id = :u"), {"u": user_id}).fetchall()

    for p in profiles:
        with st.expander(f"Profile: {p[1]} {'(Active)' if p[2] else '(Inactive)'}"):
            new_name = st.text_input("Name", value=p[1], key=f"name_{p[0]}")
            new_text = st.text_area("Profile Text", value=p[3], key=f"text_{p[0]}")
            params_str = json.dumps(p[4], indent=2) if isinstance(p[4], (dict, list)) else p[4]
            new_params = st.text_area("Search Params (JSON)", value=params_str, key=f"params_{p[0]}")
            is_active = st.checkbox("Active", value=p[2], key=f"active_{p[0]}")

            if st.button("Update Profile", key=f"up_{p[0]}"):
                try:
                    params_json = json.loads(new_params)
                    with engine.connect() as conn:
                        conn.execute(text("UPDATE search_profiles SET name=:n, profile_text=:t, search_params=:p, is_active=:a WHERE id=:id"),
                                     {"n": new_name, "t": new_text, "p": json.dumps(params_json), "a": is_active, "id": p[0]})
                        conn.commit()
                    st.success("Profile updated!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    st.subheader("Add New Profile")
    with st.form("new_profile"):
        n_name = st.text_input("Profile Name")
        n_text = st.text_area("Profile Text (Your Bio/Experience)")
        n_params = st.text_area("Search Params (JSON)", value='[{"search_term": "Product Manager", "location": "Toronto, ON", "is_remote": false, "sites": ["linkedin", "indeed", "glassdoor"]}]')
        if st.form_submit_button("Create Profile"):
            try:
                p_json = json.loads(n_params)
                with engine.connect() as conn:
                    conn.execute(text("INSERT INTO search_profiles (user_id, name, profile_text, search_params) VALUES (:u, :n, :t, :p)"),
                                 {"u": user_id, "n": n_name, "t": n_text, "p": json.dumps(p_json)})
                    conn.commit()
                st.success("Profile created!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

def show_jobs():
    st.title("📋 Job Leads")
    user_id = st.session_state.user['id']

    with engine.connect() as conn:
        profiles = conn.execute(text("SELECT id, name FROM search_profiles WHERE user_id = :u"), {"u": user_id}).fetchall()

    if not profiles:
        st.warning("Please create a search profile first.")
        return

    profile_options = {p[1]: p[0] for p in profiles}
    selected_profile_name = st.selectbox("Select Profile", list(profile_options.keys()))
    profile_id = profile_options[selected_profile_name]
    st.session_state.profile_id = profile_id

    # Filtering
    filter_status = st.pills("Filter Status:", ["All", "High Matches", "Approved", "Tailored", "Applied", "Rejected", "Archived"], default="All")

    status_map = {"High Matches": "new", "Approved": "approved", "Tailored": "tailored", "Applied": "applied", "Rejected": "rejected", "Archived": "archived"}

    query = text("""
        SELECT id, title, company, match_score, ai_summary, job_url, status, created_at, matched_at, tailored_at, applied_at
        FROM job_leads
        WHERE profile_id = :pid
        ORDER BY FIELD(status, 'tailored', 'applied', 'new', 'approved', 'rejected', 'archived'), match_score DESC
    """)

    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"pid": profile_id})

    if df.empty:
        st.info("No jobs found for this profile. Run the scout!")
        return

    if filter_status == "High Matches":
        df = df[(df['status'] == 'new') & (df['match_score'] >= 70)]
    elif filter_status != "All":
        df = df[df['status'] == status_map[filter_status]]

    for _, row in df.iterrows():
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            with c1:
                st.subheader(f"{row['title']} @ {row['company']}")
                st.caption(f"Score: {row['match_score']}% | Status: {row['status'].upper()}")
                st.write(f"**AI Insight:** {row['ai_summary']}")
                st.link_button("View Posting", row['job_url'])

                if row['status'] in ['tailored', 'applied']:
                    res_path = f"resumes/{row['id']}_Resume.pdf"
                    cl_path = f"resumes/{row['id']}_CoverLetter.pdf"
                    d_col1, d_col2 = st.columns(2)
                    if os.path.exists(res_path):
                        with open(res_path, "rb") as f:
                            d_col1.download_button("📥 Resume", f, file_name=f"Resume_{row['company']}.pdf", key=f"dl_r_{row['id']}")
                    if os.path.exists(cl_path):
                        with open(cl_path, "rb") as f:
                            d_col2.download_button("📥 Cover Letter", f, file_name=f"CoverLetter_{row['company']}.pdf", key=f"dl_cl_{row['id']}")

            with c2:
                if row['status'] == 'new':
                    if st.button("✅ Approve", key=f"ap_{row['id']}"):
                        with engine.connect() as conn:
                            conn.execute(text("UPDATE job_leads SET status='approved' WHERE id=:id"), {"id": row['id']})
                            conn.commit()
                        st.rerun()
                elif row['status'] == 'tailored':
                    if st.button("🚀 Applied", key=f"ma_{row['id']}"):
                        with engine.connect() as conn:
                            conn.execute(text("UPDATE job_leads SET status='applied', applied_at=CURRENT_TIMESTAMP WHERE id=:id"), {"id": row['id']})
                            conn.commit()
                        st.rerun()

def show_user_settings():
    st.title("⚙️ User Settings")
    user = st.session_state.user
    user_id = user['id']

    with engine.connect() as conn:
        curr_user = conn.execute(text("SELECT name, phone, location, linkedin_url, website_url, header_template FROM users WHERE id = :id"), {"id": user_id}).fetchone()

    with st.form("settings_form"):
        st.subheader("Contact Information")
        new_name = st.text_input("Full Name", value=curr_user[0])
        new_phone = st.text_input("Phone Number", value=curr_user[1] or "")
        new_location = st.text_input("Location (City, State/Prov)", value=curr_user[2] or "")
        new_linkedin = st.text_input("LinkedIn URL", value=curr_user[3] or "")
        new_website = st.text_input("Website/Portfolio URL", value=curr_user[4] or "")

        st.subheader("Resume Header Template")
        st.caption("Use placeholders: {name}, {email}, {phone}, {location}, {linkedin}, {website}")
        default_template = "{name}\n{phone} | {email} | {location}\n{linkedin} | {website}"
        new_template = st.text_area("Header Template", value=curr_user[5] or default_template, height=100)

        if st.form_submit_button("Save Settings"):
            with engine.connect() as conn:
                conn.execute(text("""
                    UPDATE users
                    SET name = :n, phone = :p, location = :l, linkedin_url = :li, website_url = :w, header_template = :h
                    WHERE id = :id
                """), {
                    "n": new_name, "p": new_phone, "l": new_location, "li": new_linkedin, "w": new_website, "h": new_template, "id": user_id
                })
                conn.commit()
            st.success("Settings updated!")
            # Update session state name
            st.session_state.user['name'] = new_name
            st.rerun()

def show_admin():
    st.title("🛡️ Admin Panel")
    with engine.connect() as conn:
        users = conn.execute(text("SELECT id, email, name, role, is_verified FROM users")).fetchall()

    df_users = pd.DataFrame(users, columns=['ID', 'Email', 'Name', 'Role', 'Verified'])
    st.dataframe(df_users)

    st.subheader("Manage User")
    uid = st.number_input("User ID", step=1)
    new_role = st.selectbox("New Role", ["user", "admin"])
    if st.button("Update User Role"):
        with engine.connect() as conn:
            conn.execute(text("UPDATE users SET role = :r WHERE id = :id"), {"r": new_role, "id": uid})
            conn.commit()
        st.success("User updated!")

if __name__ == "__main__":
    main()
