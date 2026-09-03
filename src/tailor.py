import json
from src.llm_gateway import LLMGateway

class DocumentTailor:
    def __init__(self):
        self.gateway = LLMGateway()

    def generate_assets(self, profile: dict, job: dict, fit: dict) -> dict:
        sys_prompt = """
        You are an ATS resume optimization expert. Produce a targeted resume and cover letter.
        Return strict JSON:
        {
            "resume_md": "Full markdown resume text...",
            "cover_letter_md": "Full markdown cover letter text..."
        }
        Rule: Adopt terms from 'terminology_tweaks' where functionally equivalent. Never fabricate credentials.
        """
        prompt = (
            f"Profile: {json.dumps(profile)}\n"
            f"Role: {job.get('title')} at {job.get('company_name')}\n"
            f"Job Description: {job.get('description')}\n"
            f"Tweaks: {json.dumps(fit.get('terminology_tweaks', {}))}"
        )
        return self.gateway.generate(prompt=prompt, system_prompt=sys_prompt, temperature=0.3)
