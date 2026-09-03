import json
from src.llm_gateway import LLMGateway

class MatchEngine:
    def __init__(self):
        self.gateway = LLMGateway()

    def evaluate_fit(self, profile: dict, job_desc: str) -> dict:
        sys_prompt = """
        You are a strict technical recruiter evaluating a candidate against a job description.
        Return strict JSON:
        {
            "is_viable": true/false,
            "rejection_reason": "string (empty if viable)",
            "match_score": 85,
            "terminology_tweaks": {"user_phrase": "jd_keyword"}
        }
        Strict Rule: Extract the minimum years of experience from the JD. If the candidate's 'total_years_experience' is significantly lower, 'is_viable' must be false.
        """
        prompt = f"Candidate Profile:\n{json.dumps(profile)}\n\nJob Description:\n{job_desc}"
        return self.gateway.generate(prompt=prompt, system_prompt=sys_prompt, temperature=0.1)
