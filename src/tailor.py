import re
import json
import math
from collections import Counter
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


# ---------------------------------------------------------------------------
# ATS scoring: this section ports the core matching logic popularized by
# resume-matcher (github.com/srbhr/resume-matcher) — parse resume + JD text,
# extract the JD's salient keywords, vectorize both with TF-IDF, score their
# cosine similarity, then report matched/missing keywords plus a handful of
# ATS-parseability checks. It's implemented here with no external
# dependencies (no sklearn/textacy) so it drops straight into this file and
# runs fast enough to score both the *original* and *tailored* resume every
# time a document is generated.
# ---------------------------------------------------------------------------

_ATS_STOPWORDS = frozenset("""
a an the and or but if while with without within into onto for of to in on at by from as is are was were be
been being do does did doing have has had having this that these those it its it's their they he she we you
your yours our ours i me my mine will would should could can may might must shall not no nor so than then
there here when where why how all any both each few more most other some such only own same too very just
etc across per via using use used able ability including include includes required requires requirement
requirements responsibilities responsible role roles job description years experience strong excellent
looking seeking candidate candidates team teams work working ensure ensuring plus preferred nice new also
""".split())

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.#/\-]{1,}")


def _tokenize(text: str) -> list:
    if not text:
        return []
    return [
        t.lower().strip(".-")
        for t in _TOKEN_RE.findall(text)
        if t.lower() not in _ATS_STOPWORDS and len(t) > 1
    ]


def _ngrams(tokens: list, n: int) -> list:
    return [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


class ATSScorer:
    """
    Dependency-free re-implementation of resume-matcher's ATS pipeline:

        JD text    ---> keyword/phrase extraction ---+
                                                       |--> TF-IDF vectors --> cosine similarity --> match score (0-100)
        Resume text -------------------------------- -+
                              |
                matched vs. missing JD keywords  ---> keyword highlighting
                              |
                  ATS parseability checks         ---> formatting suggestions

    Nothing here calls an LLM — it's the same lexical/statistical scoring
    resume-matcher's engine uses, which is what makes it cheap enough to run
    before *and* after every tailoring pass so we can show the delta.
    """

    TOP_KEYWORDS = 20

    # ---- text extraction ---------------------------------------------------
    def _profile_text(self, profile: dict) -> str:
        parts = []
        for exp in profile.get("experience", []):
            parts.append(exp.get("role", ""))
            parts.extend(exp.get("bullets", []))
        for edu in profile.get("education", []):
            parts.append(edu.get("degree", ""))
            parts.append(edu.get("details", ""))
        parts.extend(profile.get("skills", []))
        return "\n".join(p for p in parts if p)

    def _tailored_text(self, profile: dict, tailored: dict) -> str:
        parts = [tailored.get("summary", "")]
        experience = tailored.get("experience") or profile.get("experience", [])
        for exp in experience:
            parts.append(exp.get("role", ""))
            parts.extend(exp.get("bullets", []))
        parts.extend(tailored.get("skills_ordered") or profile.get("skills", []))
        return "\n".join(p for p in parts if p)

    # ---- keyword extraction -------------------------------------------------
    def extract_jd_keywords(self, job_desc: str, top_n: int = TOP_KEYWORDS) -> list:
        """
        Frequency-weighted unigram + bigram extraction over the JD — the same
        idea as resume-matcher's key-term extraction step: surface the
        phrases that recur and read like requirements/skills, filtering out
        boilerplate via the stopword list above.
        """
        tokens = _tokenize(job_desc)
        if not tokens:
            return []
        unigram_counts = Counter(tokens)
        bigram_counts = Counter(_ngrams(tokens, 2))
        # Bigrams made of two real words tend to be more specific signals
        # ("machine learning" beats either word alone), so weight them up -
        # but only keep a bigram if it actually recurs; a one-off pairing
        # from a long sentence is usually noise, not a real requirement.
        scored = [(phrase, freq) for phrase, freq in unigram_counts.items()]
        scored += [(phrase, freq * 1.4) for phrase, freq in bigram_counts.items() if freq >= 2]
        scored.sort(key=lambda x: x[1], reverse=True)

        keywords = []
        for phrase, _ in scored:
            # Skip a unigram fully covered by a higher/equal-weight bigram
            # already kept (e.g. drop lone "learning" once "machine
            # learning" is in the list), but never drop it in favor of a
            # single one-off bigram.
            covering_bigram = next((kw for kw in keywords if " " in kw and phrase in kw.split()), None)
            if covering_bigram:
                continue
            keywords.append(phrase)
            if len(keywords) >= top_n:
                break
        return keywords

    # ---- TF-IDF + cosine similarity -----------------------------------------
    def _tfidf(self, docs: list) -> list:
        """Minimal TF-IDF over a small doc set (here: just resume vs. JD)."""
        doc_tokens = [_tokenize(d) for d in docs]
        df = Counter()
        for tokens in doc_tokens:
            df.update(set(tokens))
        n_docs = len(docs)
        vectors = []
        for tokens in doc_tokens:
            tf = Counter(tokens)
            vec = {}
            for term, count in tf.items():
                idf = math.log((n_docs + 1) / (df[term] + 1)) + 1
                vec[term] = (count / max(len(tokens), 1)) * idf
            vectors.append(vec)
        return vectors

    def _cosine(self, vec_a: dict, vec_b: dict) -> float:
        if not vec_a or not vec_b:
            return 0.0
        common = set(vec_a) & set(vec_b)
        dot = sum(vec_a[t] * vec_b[t] for t in common)
        mag_a = math.sqrt(sum(v * v for v in vec_a.values()))
        mag_b = math.sqrt(sum(v * v for v in vec_b.values()))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    def match_score(self, resume_text: str, job_desc: str) -> float:
        vec_resume, vec_jd = self._tfidf([resume_text, job_desc])
        return round(self._cosine(vec_resume, vec_jd) * 100, 1)

    # ---- keyword coverage -----------------------------------------------------
    def keyword_coverage(self, resume_text: str, jd_keywords: list) -> dict:
        resume_lower = resume_text.lower()
        resume_tokens = set(_tokenize(resume_text))
        matched, missing = [], []
        for kw in jd_keywords:
            hit = (kw in resume_lower) if " " in kw else (kw in resume_tokens)
            (matched if hit else missing).append(kw)
        coverage_pct = round(100 * len(matched) / max(len(jd_keywords), 1), 1)
        return {"matched": matched, "missing": missing, "coverage_pct": coverage_pct}

    # ---- ATS parseability checks ------------------------------------------------
    def format_checks(self, profile: dict) -> list:
        """Structural checks, not content checks — things an ATS parser trips
        on regardless of how well-written the resume is."""
        issues = []
        contact = profile.get("contact", {})
        if not contact.get("email"):
            issues.append("Missing email address - most ATS parsers require one to file the application.")
        if not contact.get("phone"):
            issues.append("Missing phone number.")
        if not profile.get("full_name"):
            issues.append("Missing candidate name.")
        for exp in profile.get("experience", []):
            if not exp.get("dates"):
                issues.append(f"'{exp.get('company', 'A role')}' is missing dates - ATS timelines rely on parseable start/end dates.")
            if not exp.get("bullets"):
                issues.append(f"'{exp.get('company', 'A role')}' has no bullet points to parse.")
        if len(profile.get("skills", [])) < 5:
            issues.append("Fewer than 5 skills listed - ATS keyword matching favors an explicit skills section.")
        return issues

    # ---- top-level report -----------------------------------------------------
    def build_report(self, profile: dict, tailored: dict, job_desc: str) -> dict:
        jd_keywords = self.extract_jd_keywords(job_desc)

        original_text = self._profile_text(profile)
        tailored_text = self._tailored_text(profile, tailored)

        before = self.match_score(original_text, job_desc)
        after = self.match_score(tailored_text, job_desc)

        coverage = self.keyword_coverage(tailored_text, jd_keywords)
        format_issues = self.format_checks(profile)

        suggestions = []
        if coverage["missing"]:
            shown = ", ".join(coverage["missing"][:8])
            suggestions.append(
                f"Consider weaving in these JD terms where you genuinely have the experience: {shown}."
            )
        if after < 40:
            suggestions.append("Overall keyword overlap with the JD is low - double check this role is a close fit before applying.")
        suggestions.extend(format_issues)

        return {
            "match_score_before": before,
            "match_score_after": after,
            "score_delta": round(after - before, 1),
            "jd_keywords": jd_keywords,
            "matched_keywords": coverage["matched"],
            "missing_keywords": coverage["missing"],
            "keyword_coverage_pct": coverage["coverage_pct"],
            "format_issues": format_issues,
            "suggestions": suggestions,
        }


class DocumentTailor:
    def __init__(self):
        self.gateway = LLMGateway()
        self.ats_scorer = ATSScorer()

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

        merged = self._validate_and_merge(profile, tailored)

        # ATS scoring pass: score the candidate's original profile and the
        # validated/grounded tailored content against the JD, so we can show
        # a before/after match score plus keyword coverage - independent of
        # (and a check on) whatever the LLM claims about "jd_keywords".
        try:
            merged["ats_report"] = self.ats_scorer.build_report(profile, merged, job_desc)
        except Exception:
            merged["ats_report"] = None

        return merged

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
        ATS_GREEN = colors.HexColor("#0F7B4E")
        ATS_AMBER = colors.HexColor("#B7791F")
        ATS_BG = colors.HexColor("#F1F5F9")

        name_style = ParagraphStyle('HN', fontSize=13, leading=15, fontName='Helvetica-Bold', textColor=DARK_NAVY)
        contact_style = ParagraphStyle('HC', fontSize=7.5, leading=10.5, fontName='Helvetica', textColor=MUTED_GRAY, alignment=2)
        sec_style = ParagraphStyle('SH', fontSize=9, leading=11, fontName='Helvetica-Bold', textColor=DARK_NAVY, spaceBefore=4, spaceAfter=1)
        bold_style = ParagraphStyle('LB', fontSize=8, leading=10.5, fontName='Helvetica-Bold', textColor=TEXT_CHARCOAL)
        date_style = ParagraphStyle('RD', fontSize=8, leading=10.5, fontName='Helvetica-Bold', textColor=MUTED_GRAY, alignment=2)
        body_style = ParagraphStyle('BT', fontSize=7.8, leading=10, fontName='Helvetica', textColor=TEXT_CHARCOAL)
        bullet_style = ParagraphStyle('CB', fontSize=7.5, leading=9.5, fontName='Helvetica', textColor=TEXT_CHARCOAL, leftIndent=8, spaceAfter=1)
        grid_style = ParagraphStyle('GC', fontSize=7.8, leading=10, fontName='Helvetica', textColor=TEXT_CHARCOAL)
        summary_style = ParagraphStyle('SM', fontSize=7.8, leading=10.5, fontName='Helvetica', textColor=TEXT_CHARCOAL, spaceAfter=3)
        ats_style = ParagraphStyle('ATS', fontSize=7.3, leading=9.8, fontName='Helvetica', textColor=TEXT_CHARCOAL)
        ats_score_style = ParagraphStyle('ATSS', fontSize=9, leading=11, fontName='Helvetica-Bold', textColor=DARK_NAVY)

        # Header
        name = sanitize_pdf_text(profile.get("full_name", "Candidate Name")).upper()
        contact = profile.get("contact", {})
        c_line = sanitize_pdf_text(f"{contact.get('email', '')} | {contact.get('phone', '')} | {contact.get('location', '')}")
        story.append(Table([[Paragraph(name, name_style), Paragraph(c_line, contact_style)]], colWidths=[200, 356]))
        story.append(HRFlowable(width="100%", thickness=1, color=DARK_NAVY, spaceBefore=2, spaceAfter=4))

        # ATS match score strip (only if a report was computed successfully)
        ats_report = tailored.get("ats_report")
        if ats_report:
            score = ats_report.get("match_score_after", 0)
            delta = ats_report.get("score_delta", 0)
            score_color = ATS_GREEN if score >= 60 else ATS_AMBER
            delta_txt = f" (+{delta} pts vs. original)" if delta > 0 else ""
            missing = ats_report.get("missing_keywords", [])[:6]
            missing_txt = sanitize_pdf_text(", ".join(missing)) if missing else "none - strong keyword coverage"
            ats_table = Table(
                [[
                    Paragraph(f'<font color="{score_color.hexval()}">ATS MATCH SCORE: {score}/100</font>{sanitize_pdf_text(delta_txt)}', ats_score_style),
                    Paragraph(f"Missing JD keywords to consider: {missing_txt}", ats_style),
                ]],
                colWidths=[170, 386],
            )
            ats_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), ATS_BG),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER_GRAY),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            story.append(ats_table)
            story.append(Spacer(1, 4))

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

    # -----------------------------------------------------------------
    # Standalone ATS report - mirrors resume-matcher's dedicated
    # "Resume Scoring & Keyword Highlighting" screen: match score,
    # matched/missing JD keywords, and format-parseability suggestions,
    # as its own one-page PDF the candidate can review independently
    # of the resume/cover-letter documents.
    # -----------------------------------------------------------------
    def build_pdf_ats_report(self, filepath: str, job_title: str, company: str, profile: dict, tailored: dict):
        ats_report = (tailored or {}).get("ats_report")
        doc = SimpleDocTemplate(filepath, pagesize=letter, leftMargin=40, rightMargin=40, topMargin=35, bottomMargin=35)
        story = []

        NAVY = colors.HexColor("#0B2540")
        GREEN = colors.HexColor("#0F7B4E")
        AMBER = colors.HexColor("#B7791F")
        MUTED = colors.HexColor("#475569")
        BORDER_GRAY = colors.HexColor("#CBD5E1")

        head_style = ParagraphStyle('RH', fontSize=14, leading=16, fontName='Helvetica-Bold', textColor=NAVY)
        sub_style = ParagraphStyle('RS', fontSize=9, leading=12, fontName='Helvetica', textColor=MUTED)
        sec_style = ParagraphStyle('RSec', fontSize=10, leading=12, fontName='Helvetica-Bold', textColor=NAVY, spaceBefore=8, spaceAfter=3)
        body_style = ParagraphStyle('RB', fontSize=9, leading=13, fontName='Helvetica', textColor=colors.HexColor("#1E293B"))
        score_style = ParagraphStyle('RScore', fontSize=22, leading=24, fontName='Helvetica-Bold')
        chip_style = ParagraphStyle('Chip', fontSize=8.3, leading=12, fontName='Helvetica', textColor=colors.HexColor("#1E293B"))

        name = sanitize_pdf_text(profile.get("full_name", "Candidate"))
        story.append(Paragraph(f"ATS Match Report — {sanitize_pdf_text(name)}", head_style))
        story.append(Paragraph(f"{sanitize_pdf_text(job_title)} at {sanitize_pdf_text(company)}", sub_style))
        story.append(HRFlowable(width="100%", thickness=1, color=NAVY, spaceBefore=4, spaceAfter=8))

        if not ats_report:
            story.append(Paragraph("ATS scoring could not be computed for this document.", body_style))
            doc.build(story)
            return

        score = ats_report.get("match_score_after", 0)
        before = ats_report.get("match_score_before", 0)
        delta = ats_report.get("score_delta", 0)
        score_color = GREEN if score >= 60 else AMBER

        score_style.textColor = score_color
        story.append(Paragraph(f"{score}<font size=11>/100</font>", score_style))
        story.append(Paragraph(
            sanitize_pdf_text(f"Original resume scored {before}/100 against this JD - tailoring moved it by {delta:+} pts."),
            sub_style
        ))

        story.append(Paragraph("MATCHED KEYWORDS", sec_style))
        matched = ats_report.get("matched_keywords", [])
        story.append(Paragraph(sanitize_pdf_text(", ".join(matched)) if matched else "None found.", chip_style))

        story.append(Paragraph("MISSING KEYWORDS", sec_style))
        missing = ats_report.get("missing_keywords", [])
        story.append(Paragraph(
            sanitize_pdf_text(", ".join(missing)) if missing else "None - full keyword coverage.",
            chip_style
        ))

        suggestions = ats_report.get("suggestions", [])
        if suggestions:
            story.append(Paragraph("SUGGESTIONS", sec_style))
            for s in suggestions:
                story.append(Paragraph(f"• {sanitize_pdf_text(s)}", body_style))

        doc.build(story)
