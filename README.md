# 🫏 WerkEsel: Multi-User Job Assistant

WerkEsel is a powerful, AI-driven job assistant that automates the process of finding, scoring, and tailoring applications for job leads. This version introduces **Multi-User support**, **Multi-Profile management**, and **Server-Side Orchestration**.

## 🚀 New Features

- **Multi-User Authentication**: Support for Email/Password registration (with bcrypt hashing) and Google OAuth login.
- **Email Verification**: Integration with AWS SES to send and verify account codes.
- **Search Profiles**: Users can create multiple independent search profiles (e.g., "Fullstack Dev" vs "DevOps Lead"). Each profile has its own:
    - **Experience Text**: Customized bio/experience used for AI matching and tailoring.
    - **Search Parameters**: Keywords, location, remote status, and specific job sites (LinkedIn, Indeed, Glassdoor).
- **Server-Side Orchestration**: A central `run_all.py` script that processes all active profiles across all users.
- **Admin Panel**: Built-in interface for administrators to manage users and system roles.
- **Automated Migrations**: The system automatically updates existing database schemas to support the new multi-profile architecture.

---

## 🛠️ Setup & Implementation

### 1. Prerequisites
- Python 3.10+
- MySQL Database
- OpenAI API Key
- AWS Account (for SES email verification)
- Google Cloud Project (for Google Login)

### 2. Environment Variables (.env)
Create a `.env` file in the root directory with the following variables:

```env
# Database
DB_USER=your_db_user
DB_PASS=your_db_password
DB_HOST=your_db_host
DB_NAME=your_db_name

# OpenAI
OPENAI_API_KEY=your_openai_key

# AWS SES (Email)
AWS_SES_REGION=us-east-1
AWS_SES_SENDER=verified_sender@example.com
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret

# Google OAuth
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_PROJECT_ID=your_google_project_id
REDIRECT_URI=http://localhost:8501
SECRET_KEY=your_super_secret_key
```

### 3. Installation
```bash
pip install -r requirements.txt
```

### 4. Database Initialization
The system can initialize and migrate itself automatically via Python logic. However, for manual setup or auditing, a standalone `migration.sql` file is provided in the root directory.

To manually initialize the database:
```bash
mysql -u your_user -p your_db_name < migration.sql
```

### 5. Running the Application
**Streamlit Dashboard (UI):**
```bash
streamlit run app.py
```

**Manual Execution:**
The "Jobs" tab in the dashboard provides manual triggers to:
- **Run Scout Now**: Find new jobs for the selected profile.
- **Run Matcher Now**: Analyze matches for unscored jobs.
- **Run Tailor Now**: Generate application PDFs for approved jobs.

**Global Processing Cycle (Server-Side):**
To run the scout, matcher, and tailor for all active profiles (e.g., via cron), execute:
```bash
python run_all.py
```
Or use the provided shell script:
```bash
bash process.sh
```

---

## 🔑 Authentication Flows

### Email/Password
1. **Signup**: User registers with name, email, and password.
2. **Verification**: A 6-digit code is sent via AWS SES.
3. **Verify**: User enters the code in the "Verify Email" tab.
4. **Login**: Once verified, the user can log in.

### Google Login
- Integrated via `streamlit-google-auth` (with custom patch for production stability).
- **Requirements**:
    - `client_secret.json` file in the root directory (or path set via `GOOGLE_CREDS_PATH`).
    - Environment variables: `REDIRECT_URI`, `SECRET_KEY`.
- **Configuration (Google Cloud Console)**:
    - **Authorized JavaScript Origins**: `https://tefinitely.com`
    - **Authorized Redirect URIs**: `https://tefinitely.com/werkesel/`
    - Ensure the OAuth consent screen is set to "Production" or add your email as a test user.

---

## 📂 Database Schema Evolution

The system automatically manages the following tables:

- **`users`**: Stores credentials, roles, and verification status.
- **`search_profiles`**: Links users to their specific job search parameters and experience bios.
- **`job_leads`**: Now includes a `profile_id` and a unique constraint on `(job_id, profile_id)`, allowing the same job to be tracked independently across different profiles.

---

## 🛠️ Troubleshooting & Tips

### Missing Descriptions (especially LinkedIn)
If you run the scout on a server (AWS, DigitalOcean, etc.), LinkedIn may block the scraper, resulting in jobs with "NULL" descriptions.
- **Symptoms**: Scout reports success but Matcher says "No valid jobs found" (due to missing descriptions).
- **Solutions**:
    - Run the scout manually from a desktop/laptop and sync the database.
    - Use residential proxies if your scraping library supports them.
    - Focus on Indeed and Glassdoor, which are generally more server-friendly.

### OpenAI API Errors (401)
If you see `Incorrect API key provided`, ensure your `.env` file contains a real OpenAI key and not the placeholder `your_openai_key_here`.

---

## 🏗️ Technical Architecture

1. **`app.py`**: The main Streamlit interface for user interaction and profile management.
2. **`auth.py`**: Centralized authentication logic (Hashing, Google Auth, SES).
3. **`scout.py`**: Uses `python-jobspy` to scrape leads based on profile parameters.
4. **`matcher.py`**: Uses OpenAI `gpt-4o-mini` to score jobs against profile experience.
5. **`tailor.py`**: Generates customized PDF resumes and cover letters.
6. **`run_all.py`**: The master orchestrator for server-side automation.

---

*WerkEsel: Because searching for jobs shouldn't feel like manual labor.* 🫏
