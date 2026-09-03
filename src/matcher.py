import re
import json
from src.llm_gateway import LLMGateway

SENIORITY_BLACKLIST = [
    r"\bsenior manager\b", r"\bprincipal\b", r"\bdirector\b", r"\bvp\b",
    r"\bhead of\b", r"\bgroup product manager\b", r"\btech lead\b",
    r"\bengineering manager\b", r"\bgeneral manager\b", r"\blead architect\b",
    r"\bassociate director\b", r"\bavp\b", r"\boperations director\b", r"\bstaff\b"
]

class MatchEngine:
    def __init__(self):
        self.gateway = LLMGateway()

    def evaluate_fit(self, profile: dict, job_title: str, job_desc: str) -> dict:
        t = job_title.lower()
        
        # 1. Deterministic Seniority Filter
        if any(re.search(pat, t) for pat in SENIORITY_BLACKLIST):
            return {"is_viable": False, "match_score": 0, "rejection_reason": "Role title exceeds seniority tier"}

        # Candidate's dynamic anti-targets
        for anti in profile.get("anti_targets", []):
            if anti.lower() in t:
                return {"is_viable": False, "match_score": 0, "rejection_reason": f"Matches anti-target: {anti}"}

        cand_exp = float(profile.get("total_years_experience", 2.0))
        max_exp_cap = cand_exp + 2.0  # Dynamic experience ceiling

        # 2. LLM Deep Evaluation
        sys_prompt = f"""
        You are an executive talent recruiter. Evaluate candidate fit against this job description.
        Candidate has {cand_exp} total years of experience.
        
        Return strict JSON:
        {{
            "is_viable": true/false,
            "rejection_reason": "string (empty if viable)",
            "match_score": 85,
            "detected_experience": "e.g., 3-5 Years",
            "skills_gap": "e.g., Snowflake, Tableau",
            "salary_est": "e.g., ₹12 - ₹16 LPA",
            "match_reason": "1-2 sentences explaining fit and skill overlap."
        }}
        Rule: If JD strictly requires experience > {max_exp_cap} years, set is_viable to false.
        """
        prompt = (
            f"Candidate Competencies: {profile.get('skills', [])}\n"
            f"Target Roles: {profile.get('target_roles', [])}\n\n"
            f"Role: {job_title}\nJD:\n{job_desc[:2500]}"
        )

        try:
            return self.gateway.generate(prompt=prompt, system_prompt=sys_prompt, temperature=0.1)
        except Exception as e:
            print(f"[Matcher] LLM Fit check failed: {e}")
            return {"is_viable": False, "match_score": 0, "rejection_reason": "Evaluation error"}
