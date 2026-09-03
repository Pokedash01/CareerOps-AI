from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from src.llm_gateway import LLMGateway

def sanitize_pdf_text(text: str) -> str:
    if not text:
        return ""
    replacements = {
        "’": "'", "‘": "'", "“": '"', "”": '"',
        "—": "-", "–": "-", "•": "*", "…": "...",
        "\u00a0": " ", "&": "&amp;"
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text

class DocumentTailor:
    def __init__(self):
        self.gateway = LLMGateway()

    def generate_adapted_bullets(self, profile: dict, job_title: str, company: str, job_desc: str) -> dict:
        sys_prompt = """
        Write a concise, 4-paragraph professional cover letter based on the candidate's actual experience.
        Return JSON:
        {
            "cover_letter_paragraphs": [
                "Opening paragraph addressing the specific role and company.",
                "Core experience achievement paragraph with actual metrics.",
                "Secondary skills alignment paragraph.",
                "Professional closing reiterating value and availability."
            ]
        }
        """
        prompt = f"Candidate Profile: {profile}\nTarget Role: {job_title} at {company}\nJD: {job_desc[:2000]}"
        try:
            return self.gateway.generate(prompt=prompt, system_prompt=sys_prompt, temperature=0.2)
        except Exception:
            return {"cover_letter_paragraphs": ["I am writing to express my interest in this position."]}

    def build_pdf_resume(self, filepath: str, profile: dict):
        doc = SimpleDocTemplate(filepath, pagesize=letter, leftMargin=28, rightMargin=28, topMargin=22, bottomMargin=22)
        story = []

        DARK_NAVY = colors.HexColor("#0A2540")
        TEXT_CHARCOAL = colors.HexColor("#1A202C")
        MUTED_GRAY = colors.HexColor("#4A5568")
        BORDER_GRAY = colors.HexColor("#CBD5E1")

        name_style = ParagraphStyle('HN', fontSize=13, leading=15, fontName='Helvetica-Bold', textColor=DARK_NAVY)
        contact_style = ParagraphStyle('HC', fontSize=7.5, leading=10.5, fontName='Helvetica', textColor=MUTED_GRAY, alignment=2)
        sec_style = ParagraphStyle('SH', fontSize=9, leading=11, fontName='Helvetica-Bold', textColor=DARK_NAVY, spaceBefore=4, spaceAfter=1)
        bold_style = ParagraphStyle('LB', fontSize=8, leading=10.5, fontName='Helvetica-Bold', textColor=TEXT_CHARCOAL)
        date_style = ParagraphStyle('RD', fontSize=8, leading=10.5, fontName='Helvetica-Bold', textColor=MUTED_GRAY, alignment=2)
        body_style = ParagraphStyle('BT', fontSize=7.8, leading=10, fontName='Helvetica', textColor=TEXT_CHARCOAL)
        bullet_style = ParagraphStyle('CB', fontSize=7.5, leading=9.5, fontName='Helvetica', textColor=TEXT_CHARCOAL, leftIndent=8, spaceAfter=1)
        grid_style = ParagraphStyle('GC', fontSize=7.8, leading=10, fontName='Helvetica', textColor=TEXT_CHARCOAL)

        # Header
        name = sanitize_pdf_text(profile.get("full_name", "Candidate Name")).upper()
        contact = profile.get("contact", {})
        c_line = sanitize_pdf_text(f"{contact.get('email', '')} | {contact.get('phone', '')} | {contact.get('location', '')}")
        story.append(Table([[Paragraph(name, name_style), Paragraph(c_line, contact_style)]], colWidths=[200, 356]))
        story.append(HRFlowable(width="100%", thickness=1, color=DARK_NAVY, spaceBefore=2, spaceAfter=4))

        # Education
        story.append(Paragraph("EDUCATION", sec_style))
        for edu in profile.get("education", []):
            edu_str = sanitize_pdf_text(f"<b>{edu.get('institution', '')}</b> | {edu.get('degree', '')} | <b>{edu.get('details', '')}</b>")
            story.append(Table([[Paragraph(edu_str, body_style), Paragraph(edu.get('dates', ''), date_style)]], colWidths=[460, 96]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_GRAY, spaceBefore=2, spaceAfter=3))

        # Work Experience
        story.append(Table([[Paragraph("WORK EXPERIENCE", sec_style), Paragraph(f"{profile.get('total_years_experience', '')} Years Experience", date_style)]], colWidths=[430, 126]))
        for exp in profile.get("experience", []):
            exp_title = sanitize_pdf_text(f"<b>{exp.get('company', '')}</b> | {exp.get('role', '')} | {exp.get('location', '')}")
            story.append(Table([[Paragraph(exp_title, bold_style), Paragraph(exp.get('dates', ''), date_style)]], colWidths=[440, 116]))
            for b in exp.get("bullets", []):
                story.append(Paragraph(f"• {sanitize_pdf_text(b)}", bullet_style))
            story.append(Spacer(1, 2))
        story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_GRAY, spaceBefore=1, spaceAfter=3))

        # Skills
        skills = profile.get("skills", [])
        if skills:
            story.append(Paragraph("SKILLS", sec_style))
            chunks = [skills[i:i + 4] for i in range(0, len(skills), 4)]
            table_data = []
            for chunk in chunks:
                row = [Paragraph(f"{'| ' if idx > 0 else ''}{sanitize_pdf_text(s)}", grid_style) for idx, s in enumerate(chunk)]
                while len(row) < 4:
                    row.append(Paragraph("", grid_style))
                table_data.append(row)
            story.append(Table(table_data, colWidths=[135, 145, 135, 141]))

        doc.build(story)

    def build_pdf_cover_letter(self, filepath: str, title: str, company: str, profile: dict, bullets_kit: dict):
        doc = SimpleDocTemplate(filepath, pagesize=letter, leftMargin=40, rightMargin=40, topMargin=35, bottomMargin=35)
        story = []
        NAVY = colors.HexColor("#0B2540")
        body_style = ParagraphStyle('CLB', fontSize=9, leading=13.5, fontName='Helvetica', textColor=colors.HexColor("#1E293B"), spaceBefore=5)
        head_style = ParagraphStyle('CLH', fontSize=14, leading=16, fontName='Helvetica-Bold', textColor=NAVY)
        sub_style = ParagraphStyle('CLS', fontSize=8.5, leading=11, fontName='Helvetica', textColor=colors.HexColor("#475569"))
        subj_style = ParagraphStyle('CLJ', fontSize=9.5, leading=12, fontName='Helvetica-Bold', textColor=NAVY, spaceBefore=4, spaceAfter=4)

        name = sanitize_pdf_text(profile.get("full_name", "Candidate")).upper()
        contact = profile.get("contact", {})
        story.append(Paragraph(name, head_style))
        story.append(Paragraph(sanitize_pdf_text(f"{contact.get('email', '')} | {contact.get('phone', '')} | {contact.get('location', '')}"), sub_style))
        story.append(HRFlowable(width="100%", thickness=1, color=NAVY, spaceBefore=3, spaceAfter=6))
        story.append(Paragraph(f"<b>Date:</b> {datetime.now().strftime('%B %d, %Y')}", body_style))
        story.append(Paragraph(f"<b>Target Role:</b> {sanitize_pdf_text(title)} | <b>Company:</b> {sanitize_pdf_text(company)}", body_style))
        story.append(Paragraph(f"Subject: Application for {sanitize_pdf_text(title)} - {name}", subj_style))
        story.append(Paragraph("Dear Hiring Team,", body_style))

        for p in bullets_kit.get("cover_letter_paragraphs", []):
            story.append(Paragraph(sanitize_pdf_text(p), body_style))

        story.append(Spacer(1, 6))
        story.append(Paragraph(f"Warm regards,<br/><b>{name}</b>", body_style))
        doc.build(story)
