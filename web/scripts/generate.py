"""
On-demand tailored resume generator.

Invoked by /api/generate (Vercel serverless). Reads the candidate's
profile from GitHub CDN, calls the LLM to generate tailored content,
builds a PDF with ReportLab, and emits base64 PDF data as JSON to stdout.

Usage:
    python generate.py '{"jobId": "abc", "jobTitle": "...", "company": "..."}'
"""
import sys
import json
import os
import re
import requests
from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle

GITHUB_REPO = os.environ.get("GITHUB_REPO", "Pokedash01/CareerOps-AI")
CHAT_ID = os.environ.get("DASHBOARD_CHAT_ID", "1368681854")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")


def sanitize(text: str) -> str:
    if not text:
        return ""
    for old, new in [
        ("'", "'"), ("'", "'"), ('"', '"'), ('"', '"'),
        ("—", "-"), ("–", "-"), ("•", "*"), ("…", "..."),
        (" ", " "), ("&", "&amp;"),
    ]:
        text = text.replace(old, new)
    return text


def llm_generate(prompt: str, system_prompt: str) -> dict:
    if GEMINI_KEY:
        import google.genai as genai
        genai.configure(api_key=GEMINI_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(
            [{"text": system_prompt}, {"text": prompt}],
            generation_config={"temperature": 0.2, "response_mime_type": "application/json"},
        )
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw).strip().rstrip("`")
        return json.loads(raw)
    elif GROQ_KEY:
        import groq
        client = groq.Groq(api_key=GROQ_KEY)
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)
    else:
        raise RuntimeError("No LLM API key configured (GEMINI_API_KEY or GROQ_API_KEY)")


SYSTEM_PROMPT = """You are a resume tailoring assistant. Return ONLY valid JSON, no markdown fences:
{
  "summary": "2-3 sentence tailored professional summary",
  "skills_ordered": ["skill1", "skill2"],
  "experience": [{"company": "exact company name", "bullets": ["bullet1", "bullet2"]}],
  "jd_keywords": ["keyword1", "keyword2"]
}"""


def build_pdf(profile: dict, tailored: dict, output_buf: BytesIO):
    doc = SimpleDocTemplate(
        output_buf, pagesize=letter,
        leftMargin=28, rightMargin=28, topMargin=22, bottomMargin=22,
    )
    story = []

    NAVY = colors.HexColor("#0A2540")
    TEXT = colors.HexColor("#1A202C")
    MUTED = colors.HexColor("#4A5568")
    BORDER = colors.HexColor("#CBD5E1")

    ns  = ParagraphStyle('N',  fontSize=13, leading=15, fontName='Helvetica-Bold', textColor=NAVY)
    cs  = ParagraphStyle('C',  fontSize=7.5, leading=10.5, fontName='Helvetica', textColor=MUTED, alignment=2)
    ss  = ParagraphStyle('S',  fontSize=9, leading=11, fontName='Helvetica-Bold', textColor=NAVY, spaceBefore=4, spaceAfter=1)
    bs  = ParagraphStyle('B',  fontSize=8, leading=10.5, fontName='Helvetica-Bold', textColor=TEXT)
    ds  = ParagraphStyle('D',  fontSize=8, leading=10.5, fontName='Helvetica-Bold', textColor=MUTED, alignment=2)
    body= ParagraphStyle('BT', fontSize=7.8, leading=10, fontName='Helvetica', textColor=TEXT)
    bul = ParagraphStyle('BU', fontSize=7.5, leading=9.5, fontName='Helvetica', textColor=TEXT, leftIndent=8, spaceAfter=1)
    grid= ParagraphStyle('G',  fontSize=7.8, leading=10, fontName='Helvetica', textColor=TEXT)
    smry= ParagraphStyle('SM', fontSize=7.8, leading=10.5, fontName='Helvetica', textColor=TEXT, spaceAfter=3)

    name = sanitize(profile.get("full_name", "Candidate")).upper()
    contact = profile.get("contact", {})
    c_line = sanitize(f"{contact.get('email','')} | {contact.get('phone','')} | {contact.get('location','')}")
    story.append(Table([[Paragraph(name, ns), Paragraph(c_line, cs)]], colWidths=[200, 356]))
    story.append(HRFlowable(width="100%", thickness=1, color=NAVY, spaceBefore=2, spaceAfter=4))

    if tailored.get("summary"):
        story.append(Paragraph("SUMMARY", ss))
        story.append(Paragraph(sanitize(tailored["summary"]), smry))

    story.append(Paragraph("EDUCATION", ss))
    for edu in profile.get("education", []):
        edu_str = sanitize(f"<b>{edu.get('institution','')}</b> | {edu.get('degree','')} | <b>{edu.get('details','')}</b>")
        story.append(Table([[Paragraph(edu_str, body), Paragraph(edu.get('dates',''), ds)]], colWidths=[460, 96]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceBefore=2, spaceAfter=3))

    story.append(Table([[
        Paragraph("WORK EXPERIENCE", ss),
        Paragraph(f"{profile.get('total_years_experience','')} Years Experience", ds),
    ]], colWidths=[430, 126]))

    for exp in tailored.get("experience", profile.get("experience", [])):
        exp_title = sanitize(f"<b>{exp.get('company','')}</b> | {exp.get('role','')}")
        story.append(Table([[Paragraph(exp_title, bs), Paragraph(exp.get('dates',''), ds)]], colWidths=[440, 116]))
        for b in exp.get("bullets", []):
            story.append(Paragraph(f"• {sanitize(b)}", bul))
        story.append(Spacer(1, 2))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceBefore=1, spaceAfter=3))

    skills = tailored.get("skills_ordered", profile.get("skills", []))
    if skills:
        story.append(Paragraph("SKILLS", ss))
        chunks = [skills[i:i+4] for i in range(0, len(skills), 4)]
        table_data = []
        for chunk in chunks:
            row = [Paragraph(f"{'| ' if idx > 0 else ''}{sanitize(s)}", grid) for idx, s in enumerate(chunk)]
            while len(row) < 4:
                row.append(Paragraph("", grid))
            table_data.append(row)
        story.append(Table(table_data, colWidths=[135, 145, 135, 141]))

    doc.build(story)


def main():
    args = json.loads(sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read())
    job_id = args.get("jobId", "unknown")
    job_title = args.get("jobTitle", "Role")
    company = args.get("company", "Company")

    # Fetch profile from GitHub CDN
    profile_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/data/users/{CHAT_ID}/profile.json"
    profile = requests.get(profile_url, timeout=10).json()

    # Generate tailored content
    prompt = f"Candidate Profile:\n{json.dumps(profile)}\n\nRole: {job_title} at {company}\n\nJob Description:\n{args.get('jobDesc', '')[:3000]}"
    tailored = llm_generate(prompt, SYSTEM_PROMPT)

    # Build PDF
    buf = BytesIO()
    build_pdf(profile, tailored, buf)
    b64 = buf.getvalue().hex()
    filename = f"Resume_{company.replace(' ', '_')}_{job_id}.pdf"

    result = {
        "url": f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/data/users/{CHAT_ID}/outputs/{job_id}/{filename}",
        "filename": filename,
        "b64": b64,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
