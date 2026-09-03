import json
from src.llm_gateway import LLMGateway

class DocumentTailor:
    def __init__(self):
        self.gateway = LLMGateway()

    def generate_assets(self, profile: dict, job: dict, fit: dict) -> dict:
        sys_prompt = """
        You are an elite ATS-resume writer. 
        Output strictly JSON matching this schema:
        {
            "resume_md": "Full markdown resume text here...",
            "cover_letter_md": "Full markdown cover letter text here..."
        }
        Rule: Use the 'terminology_tweaks' to align the candidate's skills with the job description. Do NOT invent fake experience or companies.
        """
        prompt = f"Profile: {json.dumps(profile)}\nJob Title: {job.get('title')} at {job.get('company_name')}\nJob Description: {job.get('description')}\nTweaks: {json.dumps(fit.get('terminology_tweaks'))}\nWrite the tailored Resume and Cover letter in professional Markdown format."
        res = self.gateway.generate(prompt=prompt, system_prompt=sys_prompt, temperature=0.3)
        return json.loads(res)
