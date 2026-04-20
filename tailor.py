import os
import json
from dotenv import load_dotenv
from sqlalchemy import text
from openai import OpenAI
from fpdf import FPDF
from db_utils import engine

# --- CONFIG ---
# Load the variables from the .env file
load_dotenv()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY")) 

os.makedirs("resumes", exist_ok=True)

def generate_pdf(filename, title, content, user_info):
    pdf = FPDF(format='letter')
    pdf.add_page()
    
    font_path = "fonts/DejaVuSans.ttf"
    if os.path.exists(font_path):
        pdf.add_font("DejaVu", "", font_path)
        pdf.add_font("DejaVu", "B", font_path)
        body_font = "DejaVu"
    else:
        body_font = "helvetica"

    # 1. HEADER (Dynamic based on user settings)
    template = user_info.get('header_template') or "{name}\n{email}"
    placeholders = {
        "{name}": user_info.get('name', ''),
        "{email}": user_info.get('email', ''),
        "{phone}": user_info.get('phone', ''),
        "{location}": user_info.get('location', ''),
        "{linkedin}": user_info.get('linkedin_url', ''),
        "{website}": user_info.get('website_url', '')
    }
    
    header_text = template
    for key, val in placeholders.items():
        header_text = header_text.replace(key, str(val or ""))

    lines = header_text.split('\n')
    for i, line in enumerate(lines):
        if i == 0:
            pdf.set_font(body_font, "B", 18)
            pdf.cell(0, 10, line.upper(), align='L', new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.set_font(body_font, size=9)
            pdf.cell(0, 5, line, align='L', new_x="LMARGIN", new_y="NEXT")
    
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
def run_tailor(profile_id=None):
    """Runs the tailor for approved jobs. Optionally filtered by profile_id."""
    with engine.connect() as conn:
        sql = """
            SELECT jl.id, jl.job_id, jl.title, jl.company, jl.description, sp.profile_text,
                   u.name, u.email, u.phone, u.location, u.linkedin_url, u.website_url, u.header_template
            FROM job_leads jl
            JOIN search_profiles sp ON jl.profile_id = sp.id
            JOIN users u ON sp.user_id = u.id
            WHERE jl.status = 'approved'
        """
        params = {}
        if profile_id:
            sql += " AND jl.profile_id = :pid"
            params["pid"] = profile_id

        sql += " LIMIT 5"

        jobs = conn.execute(text(sql), params).fetchall()

        if not jobs:
            print("📭 No approved jobs to tailor.")
            return 0

        tailored_count = 0
        for job in jobs:
            db_id, job_id, title, company, description, my_profile, u_name, u_email, u_phone, u_loc, u_li, u_web, u_header = job

            user_info = {
                "name": u_name, "email": u_email, "phone": u_phone,
                "location": u_loc, "linkedin_url": u_li, "website_url": u_web,
                "header_template": u_header
            }
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
                generate_pdf(f"resumes/{db_id}_Resume.pdf", "", full_resume, user_info)
                generate_pdf(f"resumes/{db_id}_CoverLetter.pdf", f"Cover Letter: {company}", full_cl, user_info)

                conn.execute(text("UPDATE job_leads SET status = 'tailored', tailored_at = CURRENT_TIMESTAMP WHERE id = :id"), {"id": db_id})
                conn.commit()
                print(f"✅ Application Ready for {company}")
                tailored_count += 1

            except Exception as e:
                print(f"❌ Failed to tailor {company}: {e}")

    return tailored_count

if __name__ == "__main__":
    run_tailor()