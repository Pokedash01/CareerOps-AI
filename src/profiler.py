"""
Resume profiler + preference schema.

extract_user_profile() runs once per user, returns a dict conforming to the
Profile shape. The bot uses REQUIRED_PREFERENCE_FIELDS to decide whether
onboarding is needed; missing_fields() returns the list of fields that
still need to be collected from the user.
"""
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
    "anti_targets": ["Excluded fields"],
    "preferred_locations": ["City 1", "Remote"],
    "salary_expectation": null,
    "open_to_internship": false,
    "open_to_training_programs": false
}

For preference fields (target_roles, anti_targets, preferred_locations,
salary_expectation, open_to_internship, open_to_training_programs):
if the resume does not make the answer unambiguous, return the empty/zero
value ([] for arrays, null for salary, false for booleans). The bot will
then ask the user for the missing field via Telegram.
"""

# Fields the user must explicitly set (in resume or via onboarding) before
# the matching pipeline can run. The values that come purely from the
# resume text (name, experience, skills) are NOT in this list.
REQUIRED_PREFERENCE_FIELDS = (
    "preferred_locations",
    "target_roles",
    "anti_targets",
    "salary_expectation",
    "open_to_internship",
)


def _has_value(field: str, profile: dict) -> bool:
    v = profile.get(field)
    if v is None:
        return False
    if isinstance(v, (list, str)):
        return len(v) > 0
    if isinstance(v, dict):
        return any(v.values())
    if isinstance(v, bool):
        # Booleans: only "true" counts as filled. The user has to either
        # say yes or no — never assume "no" means "filled".
        return v is True
    return True


def missing_fields(profile: dict) -> list:
    """Return the list of REQUIRED_PREFERENCE_FIELDS that are not set.
    Empty list means the profile is complete and the pipeline can run."""
    return [f for f in REQUIRED_PREFERENCE_FIELDS if not _has_value(f, profile)]


def profile_is_complete(profile: dict) -> bool:
    return not missing_fields(profile)


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
