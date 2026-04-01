import os
import json
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from openai import OpenAI

# --- CONFIG ---
# Load the variables from the .env file
load_dotenv()
# Build the URL dynamically
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")

DB_URL = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
engine = create_engine(DB_URL)

def get_master_profile():
    if not os.path.exists("profile.txt"):
        with open("profile.txt", "w") as f: f.write("Add your experience here")
    with open("profile.txt", "r") as f:
        return f.read()

def run_matcher():
    profile = get_master_profile()
    
    with engine.connect() as conn:
        # We only want jobs that have a description to read
        query = text("""
            SELECT id, title, company, description 
            FROM job_leads 
            WHERE match_score IS NULL 
            AND description IS NOT NULL 
            LIMIT 10
        """)
        jobs = conn.execute(query).fetchall()

    if not jobs:
        print("🙌 No new valid jobs to match.")
        return

    print(f"🧠 Processing {len(jobs)} jobs with OpenAI...")

    for job in jobs:
        job_id, title, company, description = job
        
        # Slicing safely: if description is None, use empty string
        clean_desc = (description or "")[:4000]

        prompt = f"""
        You are an expert technical recruiter. Analyze the following Job Description against the Candidate Profile.
        
        CANDIDATE PROFILE:
        {profile}
        
        JOB DESCRIPTION:
        Title: {title}
        Company: {company}
        Description: {clean_desc} 

        RETURN ONLY A JSON OBJECT with these keys:
        "score": (0-100 integer)
        "summary": (1-sentence explanation)
        """

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={ "type": "json_object" }
            )
            
            res_content = response.choices[0].message.content
            result = json.loads(res_content)
            
            with engine.connect() as conn:
                conn.execute(
                    text("UPDATE job_leads SET match_score = :score, ai_summary = :summary WHERE id = :id"),
                    {"score": result.get('score', 0), "summary": result.get('summary', 'No summary'), "id": job_id}
                )
                conn.commit()
            print(f"✅ Scored {title}: {result.get('score')}%")

        except Exception as e:
            print(f"❌ Error scoring {title}: {e}")
            # Mark it with a 0 so we don't keep trying to process a broken record
            with engine.connect() as conn:
                conn.execute(text("UPDATE job_leads SET match_score = 0 WHERE id = :id"), {"id": job_id})
                conn.commit()

if __name__ == "__main__":
    run_matcher()
