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

    # 2. DOCUMENT TITLE (The "Targeted Role")
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
    if not os.path.exists("profile.txt"):
        print("❌ Error: profile.txt not found.")
        return
        
    with open("profile.txt", "r") as f:
        my_profile = f.read()

    with engine.connect() as conn:
        query = text("SELECT id, title, company, description FROM job_leads WHERE status = 'approved' LIMIT 5")
        jobs = conn.execute(query).fetchall()

        if not jobs:
            print("📭 No approved jobs to tailor.")
            return

        for job_id, title, company, description in jobs:
            print(f"🧵 Building 'Versatile Expert' application for {title} at {company}...")

            # DUAL-THREAT PROMPT: Highlighting Telco scale while maintaining SaaS/Platform versatility
            resume_prompt = f"""
            Task: Write a 1-page Canadian-style resume for {title} at {company}.
            Use my PROFILE: {my_profile}
            Job Context: {description[:2000]}
            
            STRICT FORMATTING RULES:
            - Do NOT include my name, contact info, or the job title in your text (I will add those automatically).
            - Do NOT use markdown (no **, no __, no #, no ---).
            - Use ONLY plain text.
            - Start immediately with the 'PROFESSIONAL SUMMARY' section.
            - Use '-' for bullets.
            
            Strategy: Highlight 'Scale & Complexity' as the primary value, using Telecom as the evidence.
            
            Requirements:
            1. SUMMARY: Position me as a 'Platform & Technical Product Leader' experienced in high-concurrency environments and large-scale digital transformations and highlight telecoms specific experience if the role relates to a telco company.
            2. CORE COMPETENCIES: A list of 6-8 bulleted items and include a mix of:
               - Niche: TM Forum Standards, API Modernization, OSS/BSS Orchestration.
               - Versatile: SaaS Product Strategy, Stakeholder Management, Agile Roadmap Prioritization, AI/ML Integration, ROI Optimization.
            3. EXPERIENCE: 
               - For Deutsche Telekom roles, emphasize the 'Platform' nature of the work (e.g., SaaS Capabilities, Pricing Engines, Latency Reduction).
               - Use phrases like 'High-scale ecosystem' and 'Enterprise-grade infrastructure' to appeal to non-telco tech companies.
            4. FORMAT: Letter size, plain text, reverse chronological
            """

            cl_prompt = f"""
            Write a 3-paragraph cover letter for {title} at {company}.
            Bridge the gap: Explain how managing the complexity of a global Tier-1 Telco platform (DT) 
            has equipped me to solve the most difficult scale and optimization challenges at {company}.
            Focus on the €1.5M savings as a 'Data-Driven Product Win' applicable to any industry.
            """

            try:
                res_resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": resume_prompt}]
                )
                full_resume = res_resp.choices[0].message.content
                
                cl_resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": cl_prompt}]
                )
                full_cl = cl_resp.choices[0].message.content
                
                generate_pdf(f"resumes/{job_id}_Resume.pdf", f"Targeted Resume: {company}", full_resume)
                generate_pdf(f"resumes/{job_id}_CoverLetter.pdf", f"Cover Letter: {company}", full_cl)

                conn.execute(text("UPDATE job_leads SET status = 'applied' WHERE id = :id"), {"id": job_id})
                conn.commit()
                print(f"✅ Application Ready for {company}")

            except Exception as e:
                print(f"❌ Failed to tailor {company}: {e}")

if __name__ == "__main__":
    run_tailor()