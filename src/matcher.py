import json
from src.llm_gateway import LLMGateway

class MatchEngine:
    def __init__(self):
        self.gateway = LLMGateway()

    def evaluate_fit(self, profile: dict, job_desc: str) -> dict:
        sys_prompt = """
        You are a strict technical recruiter. Output strict JSON:
        {
            "is_viable": true/false,
            "rejection_reason": "string (leave empty if viable)",
            "match_score": 85,
            "terminology_tweaks": {"candidate_skill": "jd_keyword"}
        }
        CRITICAL RULE: Parse the JD for minimum years of experience. If the Candidate's 'total_years_experience' is less than the strict requirement, "is_viable" MUST be false. Do not give false hope.
        """
        prompt = f"Candidate Profile:\n{json.dumps(profile)}\n\nJob Description:\n{job_desc}"
        res = self.gateway.generate(prompt=prompt, system_prompt=sys_prompt, temperature=0.1)
        return json.loads(res)
