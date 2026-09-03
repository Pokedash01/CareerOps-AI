import json
from pathlib import Path
from src.llm_gateway import LLMGateway

SYSTEM_PROMPT = """
You are an expert executive headhunter. Parse the provided resume text.
Extract their exact total years of experience, core competencies, and infer realistic pivot roles.
Output strict JSON matching this schema:
{
    "total_years_experience": 5.5,
    "core_competencies": ["Python", "SharePoint", "Agile"],
    "pivot_trajectories": ["Product Analyst", "Operations Tech"],
    "seniority_ceiling": "Mid-Level",
    "anti_targets": ["Cold Sales", "HR"]
}
"""

def extract_user_profile(user_id: str, raw_text: str) -> dict:
    profile_path = Path(f"data/users/{user_id}/profile.json")
    if profile_path.exists():
        return json.loads(profile_path.read_text(encoding="utf-8"))

    gateway = LLMGateway()
    response = gateway.generate(prompt=raw_text, system_prompt=SYSTEM_PROMPT)
    profile = json.loads(response)
    
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    return profile
