import re
from src.llm_gateway import LLMGateway

class MatchEngine:
    def __init__(self):
        self.gateway = LLMGateway()

    def evaluate_fit(self, profile: dict, job_title: str, job_desc: str) -> dict:
        cand_exp = float(profile.get("total_years_experience", 3.0))
        cand_skills = [s.lower() for s in profile.get("skills", [])]

        # Grounding Rule: If JD title demands a core programming language not on profile, reject
        t = job_title.lower()
        if "python" in t and "python" not in cand_skills:
            return {"is_viable": False, "match_score": 0, "rejection_reason": "Role demands Python"}
        if "java" in t and "java" not in cand_skills:
            return {"is_viable": False, "match_score": 0, "rejection_reason": "Role demands Java"}

        sys_prompt = f"""
        You are a strict technical recruiter evaluating a candidate against a job description.
        Candidate Experience: {cand_exp} Years.
        Candidate Verified Skills: {profile.get('skills', [])}

        STRICT ACCURACY RULES:
        1. If the job requires a primary tech stack the candidate lacks, score MUST be < 60% and is_viable = false.
        2. Format salary estimate cleanly as '₹X - ₹Y LPA (Est.)'.
        3. Do NOT exaggerate match fit.
        
        Return JSON schema:
        {{
            "is_viable": true/false,
            "match_score": 85,
            "detected_experience": "2–5 Years / Unspecified",
            "salary_range": "₹12 - ₹18 LPA (Est.)",
            "skills_gap": "None" | "Specific Missing Tools"
        }}
        """
        prompt = f"Target Role: {job_title}\nJob Description:\n{job_desc[:2500]}"
        try:
            return self.gateway.generate(prompt=prompt, system_prompt=sys_prompt, temperature=0.1)
        except Exception:
            return {"is_viable": False, "match_score": 0}
