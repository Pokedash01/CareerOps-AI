import json
from pathlib import Path
from src.llm_gateway import LLMGateway

SYSTEM_PROMPT = """
You are an executive talent intelligence parser. Analyze the resume text and convert it into a complete, structured JSON profile.
Extract actual candidate information without fabricating any details.

Output strict JSON matching this exact schema:
{
    "full_name": "Candidate Full Name",
    "contact": {
        "email": "email@domain.com",
        "phone": "+1234567890",
        "location": "City, Country",
        "links": "Portfolio / LinkedIn links"
    },
    "total_years_experience": 3.5,
    "education": [
        {
            "institution": "University / College Name",
            "degree": "Degree and Major",
            "details": "GPA / Honors / Key Coursework",
            "dates": "Start - End Date"
        }
    ],
    "experience": [
        {
            "company": "Company Name",
            "role": "Job Title",
            "location": "City, Country",
            "dates": "Start - End Date",
            "summary": "High level scope/responsibility",
            "bullets": [
                "Key achievement with exact metrics",
                "Project or deliverable detail"
            ]
        }
    ],
    "skills": ["Skill 1", "Skill 2", "Skill 3", "Skill 4"],
    "certifications": ["Certification 1", "Certification 2"],
    "target_roles": ["Role 1", "Role 2", "Role 3"],
    "anti_targets": ["Excluded domain 1", "Excluded domain 2"]
}
"""

def extract_user_profile(user_id: str, raw_text: str) -> dict:
    profile_path = Path(f"data/users/{user_id}/profile.json")
    if profile_path.exists():
        try:
            return json.loads(profile_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    gateway = LLMGateway()
    profile = gateway.generate(prompt=raw_text, system_prompt=SYSTEM_PROMPT)
    
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    return profile
