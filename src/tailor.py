import os
import re
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from src.llm_gateway import LLMGateway

class DocumentTailor:
    def __init__(self):
        self.gateway = LLMGateway()

    def generate_adapted_bullets(self, profile: dict, job_title: str, company: str, job_desc: str) -> dict:
        sys_prompt = """
        You are an elite ATS resume optimizer. 
        Adapt the candidate's existing experience bullets to highlight keywords from the target JD.
        CRITICAL RULES:
        1. Keep the exact companies, titles, and dates provided by the candidate.
        2. Never fabricate companies, credentials, metrics, or factual claims.
        3. Return JSON containing adapted bullets mapped by company index, and tailored cover letter paragraphs:
        {
            "adapted_experience": [
                {
                    "company": "Company Name",
                    "bullets": ["Adapted bullet 1", "Adapted bullet 2"]
                }
            ],
            "cover_letter_paragraphs": [
                "Targeted opening demonstrating alignment with company and role.",
                "Primary experience alignment paragraph connecting candidate skills to JD.",
                "Secondary experience / impact paragraph highlighting delivery and metrics.",
                "Professional closing expressing enthusiasm and availability."
            ]
        }
        """
        prompt = (
            f"Candidate Work Experience:\n{profile.get('experience', [])}\n\n"
            f"Target Role: {job_title} at {company}\n"
            f"Target JD:\n{job_desc[:2500]}"
        )
        return self.gateway.generate(prompt=prompt, system_prompt=sys_prompt, temperature=0.2)

    def build_pdf_resume(self, filepath: str, profile: dict, bullets_kit: dict):
        doc = SimpleDocTemplate(filepath, pagesize=letter, leftMargin=28, rightMargin=28, topMargin=22, bottomMargin=22)
        story = []

        DARK_NAVY = colors.HexColor("#0A2540")
        TEXT_CHARCOAL = colors.HexColor("#1A202C")
        MUTED_GRAY = colors.HexColor("#4A5568")
        BORDER_GRAY = colors.HexColor("#CBD5E1")

        name_style = ParagraphStyle('HeaderName', fontSize=13, leading=15, fontName='Helvetica-Bold', textColor=DARK_NAVY)
        contact_style = ParagraphStyle('HeaderContact', fontSize=7.5, leading=10.5, fontName='Helvetica', textColor=MUTED_GRAY, alignment=2)
        section_head_style = ParagraphStyle('SectionHead', fontSize=9, leading=11, fontName='Helvetica-Bold', textColor=DARK_NAVY, spaceBefore=4, spaceAfter=1)
        left_bold_style = ParagraphStyle('LeftBold', fontSize=8, leading=10.5, fontName='Helvetica-Bold', textColor=TEXT_CHARCOAL)
        right_date_style = ParagraphStyle('RightDate', fontSize=8, leading=10.5, fontName='Helvetica-Bold', textColor=MUTED_GRAY, alignment=2)
        body_style = ParagraphStyle('BodyText', fontSize=7.8, leading=10, fontName='Helvetica', textColor=TEXT_CHARCOAL)
        role_desc_style = ParagraphStyle('RoleDesc', fontSize=7.8, leading=9.8, fontName='Helvetica-Oblique', textColor=TEXT_CHARCOAL, spaceAfter=1)
        subhead_style = ParagraphStyle('SubCategoryHead', fontSize=8, leading=10, fontName='Helvetica-Bold', textColor=DARK_NAVY, spaceBefore=2, spaceAfter=1)
        bullet_style = ParagraphStyle('CompactBullet', fontSize=7.5, leading=9.5, fontName='Helvetica', textColor=TEXT_CHARCOAL, leftIndent=8, spaceAfter=1)
        grid_cell_style = ParagraphStyle('GridCell', fontSize=7.8, leading=10, fontName='Helvetica', textColor=TEXT_CHARCOAL)

        # 1. Dynamic Contact Header
        full_name = profile.get("full_name", "Candidate Name").upper()
        contact = profile.get("contact", {})
        contact_str = f"{contact.get('email', '')} | {contact.get('phone', '')} | {contact.get('location', '')} | {contact.get('links', '')}"

        header_table = Table([
            [Paragraph(full_name, name_style), Paragraph(contact_str, contact_style)]
        ], colWidths=[200, 356])
        header_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0)]))
        story.append(header_table)
        story.append(HRFlowable(width="100%", thickness=1, color=DARK_NAVY, spaceBefore=2, spaceAfter=4))

        # 2. Dynamic Education
        education = profile.get("education", [])
        if education:
            story.append(Paragraph("EDUCATION", section_head_style))
            for edu in education:
                edu_text = f"<b>{edu.get('institution', '')}</b> | {edu.get('degree', '')} | <b>{edu.get('details', '')}</b>"
                edu_table = Table([[Paragraph(edu_text, body_style), Paragraph(edu.get('dates', ''), right_date_style)]], colWidths=[460, 96])
                edu_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0)]))
                story.append(edu_table)
            story.append(Spacer(1, 2))
            story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_GRAY, spaceBefore=1, spaceAfter=3))

        # 3. Dynamic Work Experience
        cand_exp = profile.get("experience", [])
        adapted_exp_map = {item.get("company", "").lower(): item.get("bullets", []) for item in bullets_kit.get("adapted_experience", [])}

        if cand_exp:
            exp_header = Table([[
                Paragraph("WORK EXPERIENCE", section_head_style),
                Paragraph(f"{profile.get('total_years_experience', '')} Years Experience", right_date_style)
            ]], colWidths=[430, 126])
            exp_header.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'BOTTOM'), ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0)]))
            story.append(exp_header)

            for exp in cand_exp:
                comp = exp.get("company", "")
                role = exp.get("role", "")
                loc = exp.get("location", "")
                dates = exp.get("dates", "")
                summary = exp.get("summary", "")

                title_table = Table([[
                    Paragraph(f"<b>{comp}</b> | {role} | {loc}", left_bold_style),
                    Paragraph(dates, right_date_style)
                ]], colWidths=[440, 116])
                title_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0)]))
                story.append(title_table)

                if summary:
                    story.append(Paragraph(summary, role_desc_style))

                bullets = adapted_exp_map.get(comp.lower(), exp.get("bullets", []))
                for b in bullets:
                    story.append(Paragraph(f"• {b}", bullet_style))
                story.append(Spacer(1, 2))

            story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_GRAY, spaceBefore=1, spaceAfter=3))

        # 4. Dynamic Skills Grid
        skills = profile.get("skills", [])
        if skills:
            story.append(Paragraph("SKILLS", section_head_style))
            # Format skills into dynamic 4-column rows
            chunks = [skills[i:i + 4] for i in range(0, len(skills), 4)]
            skills_table_data = []
            for chunk in chunks:
                row = []
                for idx, skill in enumerate(chunk):
                    prefix = "| " if idx > 0 else ""
                    row.append(Paragraph(f"{prefix}{skill}", grid_cell_style))
                while len(row) < 4:
                    row.append(Paragraph("", grid_cell_style))
                skills_table_data.append(row)

            skills_table = Table(skills_table_data, colWidths=[135, 145, 135, 141])
            skills_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0)]))
            story.append(skills_table)
            story.append(Spacer(1, 2))
            story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_GRAY, spaceBefore=1, spaceAfter=3))

        # 5. Dynamic Certifications Grid
        certs = profile.get("certifications", [])
        if certs:
            story.append(Paragraph("CERTIFICATIONS", section_head_style))
            cert_chunks = [certs[i:i + 2] for i in range(0, len(certs), 2)]
            cert_table_data = []
            for chunk in cert_chunks:
                row = [Paragraph(chunk[0], grid_cell_style)]
                row.append(Paragraph(f"| {chunk[1]}" if len(chunk) > 1 else "", grid_cell_style))
                cert_table_data.append(row)

            certs_table = Table(cert_table_data, colWidths=[280, 276])
            certs_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0)]))
            story.append(certs_table)

        doc.build(story)

    def build_pdf_cover_letter(self, filepath: str, title: str, company: str, profile: dict, bullets_kit: dict):
        doc = SimpleDocTemplate(filepath, pagesize=letter, leftMargin=40, rightMargin=40, topMargin=35, bottomMargin=35)
        story = []
        NAVY = colors.HexColor("#0B2540")
        body_style = ParagraphStyle('CLBody', fontSize=9, leading=13.5, fontName='Helvetica', textColor=colors.HexColor("#1E293B"), spaceBefore=5)
        header_style = ParagraphStyle('CLHead', fontSize=14, leading=16, fontName='Helvetica-Bold', textColor=NAVY)
        sub_style = ParagraphStyle('CLSub', fontSize=8.5, leading=11, fontName='Helvetica', textColor=colors.HexColor("#475569"))
        subj_style = ParagraphStyle('CLSubj', fontSize=9.5, leading=12, fontName='Helvetica-Bold', textColor=NAVY, spaceBefore=4, spaceAfter=4)

        full_name = profile.get("full_name", "Candidate Name")
        contact = profile.get("contact", {})
        contact_str = f"{contact.get('email', '')} | {contact.get('phone', '')} | {contact.get('location', '')}"

        story.append(Paragraph(full_name.upper(), header_style))
        story.append(Paragraph(contact_str, sub_style))
        story.append(Spacer(1, 3))
        story.append(HRFlowable(width="100%", thickness=1, color=NAVY, spaceAfter=6))
        story.append(Paragraph(f"<b>Date:</b> {datetime.now().strftime('%B %d, %Y')}", body_style))
        story.append(Paragraph(f"<b>Target Role:</b> {title} | <b>Company:</b> {company}", body_style))
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"Subject: Application for {title} - {full_name}", subj_style))
        story.append(Paragraph("Dear Hiring Team,", body_style))

        for p in bullets_kit.get("cover_letter_paragraphs", []):
            story.append(Paragraph(p, body_style))

        story.append(Spacer(1, 6))
        story.append(Paragraph(f"Warm regards,<br/><b>{full_name}</b>", body_style))
        doc.build(story)
