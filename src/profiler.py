import json
from pathlib import Path
from src.llm_gateway import LLMGateway

SYSTEM_PROMPT = """
You are an executive talent intelligence headhunter. Parse the provided resume text.
Extract years of experience, core competencies, and identify realistic career pivot roles.
Return strict JSON matching this schema:
{
    "total_years_experience": 4.5,
    "core_competencies": ["Tool A", "Skill B"],
    "pivot_trajectories": ["Role A", "Role B"],
    "seniority_ceiling": "Mid-Level",
    "anti_targets": ["Cold Sales", "Customer Support"]
}
"""

def extract_user_profile(user_id: str, raw_text: str) -> dict:
    profile_path = Path(f"data/users/{user_id}/profile.json")
    if profile_path.exists():
        return json.loads(profile_path.read_text(encoding="utf-8"))

    gateway = LLMGateway()
    profile = gateway.generate(prompt=raw_text, system_prompt=SYSTEM_PROMPT)
    
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    return profile
