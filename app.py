import streamlit as st
import os
import json
import pandas as pd
import scout
import matcher
import tailor
from sqlalchemy import text, bindparam
from dotenv import load_dotenv
from streamlit_google_auth import Authenticate

# --- CONFIG ---
load_dotenv()

import auth
from importlib import metadata
import requests
from db_utils import engine, setup_db

RESUME_DIR = "resumes"
os.makedirs(RESUME_DIR, exist_ok=True)

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

    # Generate google_credentials.json if needed
    creds_path = "google_credentials.json"
    if not os.path.exists(creds_path) and os.getenv("GOOGLE_CLIENT_ID"):
        import json
        creds = {
            "web": {
                "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                "project_id": os.getenv("GOOGLE_PROJECT_ID", "werkesel"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                "redirect_uris": [os.getenv("REDIRECT_URI", "http://localhost:8501")]
            }
        }
        with open(creds_path, "w") as f:
            json.dump(creds, f)

    # Google Auth Setup
    authenticator = Authenticate(
        secret_credentials_path=creds_path,
        cookie_name="werkesel_auth",
        cookie_key=os.getenv("SECRET_KEY", "werkesel_cookie_key"),
        redirect_uri=os.getenv("REDIRECT_URI", "http://localhost:8501")
    )

    # Check if user is already authenticated via Google
    authenticator.check_authentification()
    if st.session_state.get('connected'):
        user_info = {
            'email': st.session_state['user_info'].get('email'),
            'sub': st.session_state['user_info'].get('sub'),
            'name': st.session_state['user_info'].get('name')
        }
        user = auth.get_or_create_google_user(engine, user_info)
        st.session_state.user = user
        st.rerun()

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
        st.write("Sign in with your Google account to continue.")
        authenticator.login()

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
        p_id, p_name, p_active, p_text, p_params = p
        # Handle JSON or dict
        params = p_params if isinstance(p_params, list) else json.loads(p_params or "[]")
        # For simplicity in UI, we'll edit the first search query in the list
        main_q = params[0] if params else {}

        with st.expander(f"Profile: {p_name} {'(Active)' if p_active else '(Inactive)'}"):
            new_name = st.text_input("Name", value=p_name, key=f"name_{p_id}")
            new_text = st.text_area("Profile Text (Your Experience)", value=p_text, key=f"text_{p_id}", height=200)

            st.subheader("Search Parameters")
            q_term = st.text_input("Search Term", value=main_q.get('search_term', 'Product Manager'), key=f"term_{p_id}")
            q_loc = st.text_input("Location", value=main_q.get('location', 'Toronto, ON'), key=f"loc_{p_id}")
            q_remote = st.checkbox("Remote Only", value=main_q.get('is_remote', False), key=f"rem_{p_id}")

            col1, col2, col3 = st.columns(3)
            q_wanted = col1.number_input("Results Wanted", value=main_q.get('results_wanted', 20), step=1, key=f"want_{p_id}")
            q_hours = col2.number_input("Hours Old", value=main_q.get('hours_old', 24), step=1, key=f"hours_{p_id}")
            q_country = col3.text_input("Country (Indeed)", value=main_q.get('country_indeed', 'canada'), key=f"country_{p_id}")

            q_sites = st.multiselect("Job Sites", ["linkedin", "indeed", "glassdoor"], default=main_q.get('sites', ["linkedin", "indeed", "glassdoor"]), key=f"sites_{p_id}")

            is_active = st.checkbox("Active", value=p_active, key=f"active_{p_id}")

            if st.button("Update Profile", key=f"up_{p_id}"):
                updated_params = [{
                    "search_term": q_term,
                    "location": q_loc,
                    "is_remote": q_remote,
                    "results_wanted": q_wanted,
                    "hours_old": q_hours,
                    "country_indeed": q_country,
                    "sites": q_sites
                }]
                with engine.connect() as conn:
                    conn.execute(text("UPDATE search_profiles SET name=:n, profile_text=:t, search_params=:p, is_active=:a WHERE id=:id"),
                                 {"n": new_name, "t": new_text, "p": json.dumps(updated_params), "a": is_active, "id": p_id})
                    conn.commit()
                st.success("Profile updated!")
                st.rerun()

    st.subheader("Add New Profile")
    with st.container(border=True):
        n_name = st.text_input("Profile Name", key="new_p_name")
        n_text = st.text_area("Profile Text (Your Bio/Experience)", key="new_p_text")

        st.subheader("Default Search Query")
        c1, c2 = st.columns(2)
        n_term = c1.text_input("Search Term", value="Product Manager", key="new_p_term")
        n_loc = c2.text_input("Location", value="Toronto, ON", key="new_p_loc")
        n_remote = st.checkbox("Remote Only", value=False, key="new_p_remote")
        n_sites = st.multiselect("Job Sites", ["linkedin", "indeed", "glassdoor"], default=["linkedin", "indeed", "glassdoor"], key="new_p_sites")

        if st.button("Create Profile"):
            n_params = [{
                "search_term": n_term,
                "location": n_loc,
                "is_remote": n_remote,
                "results_wanted": 20,
                "hours_old": 24,
                "country_indeed": "canada",
                "sites": n_sites
            }]
            with engine.connect() as conn:
                conn.execute(text("INSERT INTO search_profiles (user_id, name, profile_text, search_params) VALUES (:u, :n, :t, :p)"),
                             {"u": user_id, "n": n_name, "t": n_text, "p": json.dumps(n_params)})
                conn.commit()
            st.success("Profile created!")
            st.rerun()

def show_jobs():
    st.title("📋 Job Leads")
    user_id = st.session_state.user['id']

    with engine.connect() as conn:
        profiles = conn.execute(text("SELECT id, name, search_params FROM search_profiles WHERE user_id = :u"), {"u": user_id}).fetchall()

    if not profiles:
        st.warning("Please create a search profile first.")
        return

    profile_data = {p[1]: {"id": p[0], "params": p[2]} for p in profiles}
    selected_profile_name = st.selectbox("Select Profile", list(profile_data.keys()))
    profile_id = profile_data[selected_profile_name]["id"]
    profile_params = profile_data[selected_profile_name]["params"]
    st.session_state.profile_id = profile_id

    # --- MANUAL TRIGGERS ---
    t1, t2, t3 = st.columns(3)
    if t1.button("🔍 Run Scout Now", use_container_width=True):
        with st.spinner("Scouting for new jobs..."):
            params = profile_params if isinstance(profile_params, list) else json.loads(profile_params or "[]")
            new_count = scout.run_scout_for_profile(profile_id, selected_profile_name, params)
            st.success(f"Scout complete! Added {new_count} new entries.")
            st.rerun()

    if t2.button("🧠 Run Matcher Now", use_container_width=True):
        with st.spinner("Analyzing matches with OpenAI..."):
            scored = matcher.run_matcher(profile_id=profile_id)
            st.success(f"Matcher complete! Scored {scored} jobs.")
            st.rerun()

    if t3.button("🧵 Run Tailor Now", use_container_width=True):
        with st.spinner("Generating tailored PDFs..."):
            tailored = tailor.run_tailor(profile_id=profile_id)
            st.success(f"Tailor complete! Generated {tailored} applications.")
            st.rerun()

    st.divider()

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
