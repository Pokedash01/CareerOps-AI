import json
from pathlib import Path
from src.llm_gateway import LLMGateway

SYSTEM_PROMPT = """
You are an expert resume parser. Extract candidate details from the resume into valid JSON.
CRITICAL: Do NOT omit any work experience, bullets, or metrics.

Schema:
{
    "full_name": "Full Name",
    "contact": {
        "email": "email",
        "phone": "phone",
        "location": "location",
        "links": "portfolio/linkedin"
    },
    "total_years_experience": 3.5,
    "seniority_tier": "Mid",
    "education": [
        {
            "institution": "Institution name",
            "degree": "Degree name",
            "details": "GPA / honors",
            "dates": "dates"
        }
    ],
    "experience": [
        {
            "company": "Company Name",
            "role": "Job Title",
            "location": "Location",
            "dates": "Dates",
            "summary": "Summary",
            "bullets": ["Bullet 1 with exact numbers", "Bullet 2 with exact numbers"]
        }
    ],
    "skills": ["Skill 1", "Skill 2"],
    "certifications": ["Cert 1"],
    "target_roles": ["Role 1", "Role 2"],
    "anti_targets": ["Excluded fields"]
}
"""

def extract_user_profile(user_id: str, raw_text: str) -> dict:
    profile_path = Path(f"data/users/{user_id}/profile.json")
    if profile_path.exists():
        try:
            data = json.loads(profile_path.read_text(encoding="utf-8"))
            if data.get("full_name") and data.get("experience"):
                return data
        except Exception:
            pass

    gateway = LLMGateway()
    profile = gateway.generate(prompt=raw_text, system_prompt=SYSTEM_PROMPT)
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    return profile
