import os
import json
from dotenv import load_dotenv
from sqlalchemy import text
from openai import OpenAI
from db_utils import engine

# --- CONFIG ---
# Load the variables from the .env file
load_dotenv()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def run_matcher(profile_id=None):
    """Runs the matcher for new jobs. Optionally filtered by profile_id."""
    with engine.connect() as conn:
        # We only want jobs that have a description to read
        sql = """
            SELECT jl.id, jl.title, jl.company, jl.description, sp.profile_text
            FROM job_leads jl
            JOIN search_profiles sp ON jl.profile_id = sp.id
            WHERE jl.match_score IS NULL
            AND jl.description IS NOT NULL
        """
        params = {}
        if profile_id:
            sql += " AND jl.profile_id = :pid"
            params["pid"] = profile_id

        sql += " LIMIT 20"

        jobs = conn.execute(text(sql), params).fetchall()

    if not jobs:
        print("🙌 No new valid jobs to match.")
        return 0

    print(f"🧠 Processing {len(jobs)} jobs with OpenAI...")
    scored_count = 0

    for i, job in enumerate(jobs, 1):
        db_id, title, company, description, profile_text = job
        print(f"   [{i}/{len(jobs)}] Analyzing: {title} @ {company} (ID: {db_id})")
        
        # Slicing safely: if description is None, use empty string
        clean_desc = (description or "")[:4000]
        if not clean_desc.strip():
            print(f"   ⚠️ Skipping: Job description is empty for ID {db_id}")
            continue

        prompt = f"""
        You are an expert technical recruiter. Analyze the following Job Description against the Candidate Profile.
        
        CANDIDATE PROFILE:
        {profile_text}
        
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
                    text("UPDATE job_leads SET match_score = :score, ai_summary = :summary, matched_at = CURRENT_TIMESTAMP WHERE id = :id"),
                    {"score": result.get('score', 0), "summary": result.get('summary', 'No summary'), "id": db_id}
                )
                conn.commit()
            print(f"✅ Scored {title}: {result.get('score')}%")
            scored_count += 1

        except Exception as e:
            print(f"❌ Error scoring {title}: {e}")
            # Mark it with a 0 so we don't keep trying to process a broken record
            with engine.connect() as conn:
                conn.execute(text("UPDATE job_leads SET match_score = 0 WHERE id = :id"), {"id": db_id})
                conn.commit()

    return scored_count

if __name__ == "__main__":
    run_matcher()
