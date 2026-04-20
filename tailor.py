import os
import json
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from openai import OpenAI
from fpdf import FPDF

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

os.makedirs("resumes", exist_ok=True)

def generate_pdf(filename, title, content):
    pdf = FPDF(format='letter')
    pdf.add_page()
    
    font_path = "fonts/DejaVuSans.ttf"
    if os.path.exists(font_path):
        pdf.add_font("DejaVu", "", font_path)
        pdf.add_font("DejaVu", "B", font_path)
        body_font = "DejaVu"
    else:
        body_font = "helvetica"

    # 1. HEADER (Eben's Info)
    pdf.set_font(body_font, "B", 18)
    pdf.cell(0, 10, "EBEN VAN ELLEWEE", align='L', new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_font(body_font, size=9)
    #contact_info = "647-749-5428 | ebenvanellewee@gmail.com | Toronto, ON | linkedin.com/in/ebenvanellewee"
    contact_info = "ebenvanellewee@gmail.com | linkedin.com/in/ebenvanellewee"
    pdf.cell(0, 5, contact_info, align='L', new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_draw_color(100, 100, 100) 
    pdf.line(10, pdf.get_y() + 2, 205, pdf.get_y() + 2)
    pdf.ln(8)

    # 2. DOCUMENT TITLE (The "Targeted Role") - Skip if empty
    if title:
        pdf.set_font(body_font, "B", 11)
        pdf.set_text_color(60, 60, 60)
        pdf.cell(0, 10, title.upper(), align='L', new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
    
    # 3. FINAL CLEANING (Removing Markdown and HTML)
    clean_text = str(content)
    replacements = {
        "**": "", "__": "", "#": "", "---": "", # Strip Markdown
        "&amp;": "&", "": "-", "–": "-", "—": "-"
    }
    for old, new in replacements.items():
        clean_text = clean_text.replace(old, new)
    
    # Remove any leading/trailing whitespace the AI might have added
    clean_text = clean_text.strip()

    # 4. BODY CONTENT
    pdf.set_font(body_font, size=10)
    pdf.multi_cell(0, 6, text=clean_text) 
    
    pdf.output(filename)
def run_tailor():
    with engine.connect() as conn:
        query = text("""
            SELECT jl.id, jl.job_id, jl.title, jl.company, jl.description, sp.profile_text
            FROM job_leads jl
            JOIN search_profiles sp ON jl.profile_id = sp.id
            WHERE jl.status = 'approved'
            LIMIT 5
        """)
        jobs = conn.execute(query).fetchall()

        if not jobs:
            print("📭 No approved jobs to tailor.")
            return

        for db_id, job_id, title, company, description, my_profile in jobs:
            print(f"🧵 Tailoring application for {title} at {company}...")

            combined_prompt = f"""
            Task: Write a 1-page Canadian-style resume and a 3-paragraph cover letter for {title} at {company}.
            
            CANDIDATE PROFILE:
            {my_profile}
            
            JOB CONTEXT:
            {description[:3000]}
            
            RESUME GUIDELINES:
            - Highlight 'Scale & Complexity' using Telecom as evidence.
            - Position me as a 'Platform & Technical Product Leader'.
            - Include competencies: API Modernization, OSS/BSS Orchestration, SaaS Product Strategy, Stakeholder Management, Agile, ROI Optimization.
            - Emphasize the 'Platform' nature of Deutsche Telekom work (Pricing Engines, Latency Reduction).
            - STRICT: No personal info, no markdown, plain text ONLY, start with 'PROFESSIONAL SUMMARY', use '-' for bullets.

            COVER LETTER GUIDELINES:
            - Highlight suitability based on required skills and my achievements.
            - FOCUS: If the role is relevant to large Telco, emphasize that experience.
            - Bridge the gap: Show how global Tier-1 Telco platform complexity equips me for challenges at {company}.
            - Mention the €1.5M savings as a data-driven win.

            RETURN ONLY A JSON OBJECT with these keys:
            "resume": (The plain text resume content)
            "cover_letter": (The plain text cover letter content)
            """

            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": combined_prompt}],
                    response_format={ "type": "json_object" }
                )
                
                result = json.loads(response.choices[0].message.content)
                full_resume = result.get("resume", "")
                full_cl = result.get("cover_letter", "")
                
                # Use db_id for file naming to be consistent with app.py's expected patterns
                # Pass empty title for Resume as requested
                generate_pdf(f"resumes/{db_id}_Resume.pdf", "", full_resume)
                generate_pdf(f"resumes/{db_id}_CoverLetter.pdf", f"Cover Letter: {company}", full_cl)

                conn.execute(text("UPDATE job_leads SET status = 'tailored', tailored_at = CURRENT_TIMESTAMP WHERE id = :id"), {"id": db_id})
                conn.commit()
                print(f"✅ Application Ready for {company}")

            except Exception as e:
                print(f"❌ Failed to tailor {company}: {e}")

if __name__ == "__main__":
    run_tailor()