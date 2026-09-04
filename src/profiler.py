import re
import json
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


# ---------------------------------------------------------------------------
# Grounding helpers: everything the model produces has to be traceable back
# to something the candidate actually wrote in their profile. We don't trust
# the model's word for it — we check.
# ---------------------------------------------------------------------------

_NUMBER_RE = re.compile(r"\d[\d,]*\.?\d*\%?")


def _extract_numbers(text: str) -> set:
    """Pull out every numeric token (1200, 20,000, 25%, 9.3, etc.)."""
    if not text:
        return set()
    return {n.replace(",", "") for n in _NUMBER_RE.findall(text)}


def _source_number_pool(profile: dict) -> set:
    """All numbers that legitimately exist anywhere in the candidate's own profile."""
    pool = set()
    for exp in profile.get("experience", []):
        for b in exp.get("bullets", []):
            pool |= _extract_numbers(b)
    for edu in profile.get("education", []):
        pool |= _extract_numbers(edu.get("details", ""))
    pool |= _extract_numbers(str(profile.get("total_years_experience", "")))
    return pool


def _bullet_is_grounded(bullet: str, source_bullets: list, global_number_pool: set) -> bool:
    """
    A rewritten bullet is only accepted if:
    1. It doesn't contain any number that isn't present somewhere in the
       candidate's real bullets (no invented/inflated metrics), and
    2. It shares enough vocabulary with at least one source bullet that it's
       plausibly a rewrite of something real, not a fabrication.
    """
    bullet_numbers = _extract_numbers(bullet)
    if not bullet_numbers.issubset(global_number_pool):
        return False

    bullet_words = set(re.findall(r"[a-zA-Z]{4,}", bullet.lower()))
    if not source_bullets:
        return False
    best_overlap = max(
        len(bullet_words & set(re.findall(r"[a-zA-Z]{4,}", sb.lower()))) / max(len(bullet_words), 1)
        for sb in source_bullets
    )
    return best_overlap >= 0.25


def _skills_are_grounded(skills_ordered: list, source_skills: list) -> bool:
    source_set = {s.strip().lower() for s in source_skills}
    return all(s.strip().lower() in source_set for s in skills_ordered) and \
        set(s.strip().lower() for s in skills_ordered) == source_set


class DocumentTailor:
    def __init__(self):
        self.gateway = LLMGateway()

    # -----------------------------------------------------------------
    # Core tailoring call: reframes existing experience toward the JD
    # instead of appending keywords or writing generic filler.
    # -----------------------------------------------------------------
    def generate_tailored_content(self, profile: dict, job_title: str, company: str, job_desc: str) -> dict:
        sys_prompt = """
You are a resume/cover-letter tailoring assistant. Your job is to REFRAME the
candidate's real, existing experience so it speaks directly to the target
role. You never invent new experience.

Hard rules (breaking any of these is a failure):
1. Do not invent employers, titles, dates, tools, certifications, or metrics
   that are not present in the candidate profile below.
2. Every number in your output (hours, %, headcount, dollar amounts, dates)
   must come from the exact source bullet it is derived from. Never add,
   round up, combine, or increase a number.
3. You MAY: reorder bullets/skills by relevance to the JD, rewrite a
   bullet's wording/emphasis/action verb to use the JD's terminology,
   combine two of the candidate's own related bullets into one sharper
   bullet, or write a summary connecting existing experience to the role -
   as long as every underlying fact stays traceable to the source profile.
4. If the JD wants a skill/tool the candidate has not listed, do not claim
   it. You may point to an adjacent/transferable skill the candidate
   genuinely has, framed honestly as transferable - not as direct experience.
5. Do not add skills to the skills list that are not already in the
   candidate's profile. You may only reorder the existing list.
6. No generic filler ("I am excited to apply", "I am a hard worker",
   "proven track record") unless immediately followed by the specific
   evidence that backs it up.
7. Select and prioritize the 4-6 most relevant bullets per role for the
   resume rather than dumping every bullet - relevance to the JD decides
   the cut, not recency alone.

Return ONLY this JSON, no markdown fences, no preamble:
{
  "jd_keywords": ["top 6-10 requirements/skills extracted from the JD"],
  "summary": "2-3 sentence professional summary, tailored to this role, built only from facts in the profile",
  "skills_ordered": ["candidate's own skills list, reordered most-to-least relevant to the JD - same items, no additions/removals"],
  "experience": [
    {
      "company": "must exactly match a company name from the profile",
      "bullets": ["4-6 bullets selected/reordered/rewritten from that company's source bullets - same facts, sharper framing"]
    }
  ],
  "cover_letter_paragraphs": [
    "Opening paragraph naming the specific role/company and 1 concrete reason of genuine fit drawn from the profile.",
    "Paragraph built around 1-2 of the candidate's strongest, most JD-relevant achievements with their real metrics.",
    "Paragraph connecting the candidate's actual skills/tools to the JD's stated requirements - name the overlaps explicitly.",
    "Closing paragraph, specific and low on filler, reiterating fit and availability."
  ]
}
"""
        prompt = (
            f"Candidate Profile (JSON):\n{json.dumps(profile)}\n\n"
            f"Target Role: {job_title} at {company}\n\n"
            f"Job Description:\n{job_desc[:3000]}"
        )
        try:
            raw = self.gateway.generate(prompt=prompt, system_prompt=sys_prompt, temperature=0.2)
            tailored = raw if isinstance(raw, dict) else json.loads(raw)
        except Exception:
            tailored = {}

        return self._validate_and_merge(profile, tailored)

    # -----------------------------------------------------------------
    # Grounding pass: anything that fails the fact-check is discarded and
    # we fall back to the candidate's original wording for that piece,
    # rather than rejecting the whole response.
    # -----------------------------------------------------------------
    def _validate_and_merge(self, profile: dict, tailored: dict) -> dict:
        number_pool = _source_number_pool(profile)
        source_exp_by_company = {e.get("company", "").strip().lower(): e for e in profile.get("experience", [])}

        merged_experience = []
        for exp in profile.get("experience", []):
            company_key = exp.get("company", "").strip().lower()
            source_bullets = exp.get("bullets", [])

            candidate_entry = next(
                (te for te in tailored.get("experience", [])
                 if te.get("company", "").strip().lower() == company_key),
                None
            )

            if candidate_entry:
                accepted = [
                    b for b in candidate_entry.get("bullets", [])
                    if _bullet_is_grounded(b, source_bullets, number_pool)
                ]
            else:
                accepted = []

            merged_experience.append({
                **exp,
                "bullets": accepted if accepted else source_bullets,
            })

        skills_ordered = tailored.get("skills_ordered", [])
        if not _skills_are_grounded(skills_ordered, profile.get("skills", [])):
            skills_ordered = profile.get("skills", [])

        summary = tailored.get("summary", "")
        if summary and not _extract_numbers(summary).issubset(number_pool):
            summary = ""  # drop a summary that invents a metric rather than trying to fix it

        cover_paragraphs = tailored.get("cover_letter_paragraphs", [])
        if not cover_paragraphs:
            cover_paragraphs = [
                "I am writing to express my interest in this position, and to share how my experience "
                "lines up with what you're looking for."
            ]

        return {
            "summary": summary,
            "skills_ordered": skills_ordered,
            "experience": merged_experience,
            "cover_letter_paragraphs": cover_paragraphs,
            "jd_keywords": tailored.get("jd_keywords", []),
        }

    # -----------------------------------------------------------------
    # PDF builders - now render the tailored (and validated) content.
    # -----------------------------------------------------------------
    def build_pdf_resume(self, filepath: str, profile: dict, tailored: dict = None):
        tailored = tailored or {}
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
        summary_style = ParagraphStyle('SM', fontSize=7.8, leading=10.5, fontName='Helvetica', textColor=TEXT_CHARCOAL, spaceAfter=3)

        # Header
        name = sanitize_pdf_text(profile.get("full_name", "Candidate Name")).upper()
        contact = profile.get("contact", {})
        c_line = sanitize_pdf_text(f"{contact.get('email', '')} | {contact.get('phone', '')} | {contact.get('location', '')}")
        story.append(Table([[Paragraph(name, name_style), Paragraph(c_line, contact_style)]], colWidths=[200, 356]))
        story.append(HRFlowable(width="100%", thickness=1, color=DARK_NAVY, spaceBefore=2, spaceAfter=4))

        # Professional summary (only if it survived grounding validation)
        summary = tailored.get("summary")
        if summary:
            story.append(Paragraph("SUMMARY", sec_style))
            story.append(Paragraph(sanitize_pdf_text(summary), summary_style))

        # Education
        story.append(Paragraph("EDUCATION", sec_style))
        for edu in profile.get("education", []):
            edu_str = sanitize_pdf_text(f"<b>{edu.get('institution', '')}</b> | {edu.get('degree', '')} | <b>{edu.get('details', '')}</b>")
            story.append(Table([[Paragraph(edu_str, body_style), Paragraph(edu.get('dates', ''), date_style)]], colWidths=[460, 96]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_GRAY, spaceBefore=2, spaceAfter=3))

        # Work Experience (tailored + validated bullets, falls back to originals per-role)
        story.append(Table([[Paragraph("WORK EXPERIENCE", sec_style), Paragraph(f"{profile.get('total_years_experience', '')} Years Experience", date_style)]], colWidths=[430, 126]))
        experience_entries = tailored.get("experience") or profile.get("experience", [])
        for exp in experience_entries:
            exp_title = sanitize_pdf_text(f"<b>{exp.get('company', '')}</b> | {exp.get('role', '')} | {exp.get('location', '')}")
            story.append(Table([[Paragraph(exp_title, bold_style), Paragraph(exp.get('dates', ''), date_style)]], colWidths=[440, 116]))
            for b in exp.get("bullets", []):
                story.append(Paragraph(f"• {sanitize_pdf_text(b)}", bullet_style))
            story.append(Spacer(1, 2))
        story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_GRAY, spaceBefore=1, spaceAfter=3))

        # Skills (reordered by relevance, never re-worded/added-to)
        skills = tailored.get("skills_ordered") or profile.get("skills", [])
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
