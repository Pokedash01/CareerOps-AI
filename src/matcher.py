"""
Job-matcher scoring engine.

The deterministic hard filters (tech stack, location, experience, salary)
are always checked in Python. The LLM scores the softer signals (skills
overlap, role narrative fit). No hardcoded candidate values — everything
comes from the profile dict.
"""
from src.llm_gateway import LLMGateway


# A broad taxonomy of hard-stack keywords. Any role with one of these in
# the title and where the candidate does NOT have that keyword in their
# skills list is rejected immediately. This covers Python/Java/Golang/etc.
# without making it about any specific candidate.
HARD_STACK_KEYWORDS = {
    "python", "java", "golang", "rust", "scala", "kotlin", "swift",
    "ruby", "php", "c++", "c#", ".net", "react", "angular", "vue",
    "node.js", "django", "flask", "spring", "rails", "laravel",
    "android", "ios", "kubernetes", "tensorflow", "pytorch",
}


def _get_salary_expectation_lpa(profile: dict):
    exp = profile.get("salary_expectation")
    if exp is None:
        return None
    if isinstance(exp, dict):
        lo = exp.get("min_lpa")
        hi = exp.get("max_lpa", lo)
        if lo is None:
            return None
        return (float(lo), float(hi if hi is not None else lo))
    try:
        v = float(exp)
        return (v, v)
    except (TypeError, ValueError):
        return None


def _location_matches(job_location: str, preferred_locations: list[str]) -> bool:
    if not preferred_locations:
        return True
    if job_location == "Not specified":
        return True
    job_loc_lower = job_location.lower()
    for pref in preferred_locations:
        pref_lower = pref.lower()
        if pref_lower in job_loc_lower or job_loc_lower in pref_lower:
            return True
        aliases = {
            "gurgaon": "gurugram", "gurugram": "gurgaon",
            "bangalore": "bengaluru", "bengaluru": "bangalore",
            "delhi": "new delhi", "new delhi": "delhi",
        }
        if aliases.get(job_loc_lower) == pref_lower or aliases.get(pref_lower) == job_loc_lower:
            return True
    return False


def _experience_ok(cand_exp: float, exp_range, tolerance: float = 1.0):
    if exp_range is None:
        return True, None
    min_req, _max_req = exp_range
    if cand_exp + tolerance < min_req:
        return False, f"Role requires {min_req:g}+ years, candidate has {cand_exp:g}"
    return True, None


def _salary_ok(salary_range_lpa, expectation_lpa, tolerance: float = 1.0):
    if salary_range_lpa is None or expectation_lpa is None:
        return True, None
    job_max = salary_range_lpa[1]
    cand_min = expectation_lpa[0]
    if job_max + tolerance < cand_min:
        return False, f"Role offers up to {job_max:g} LPA, below expected {cand_min:g} LPA"
    return True, None


class MatchEngine:
    def __init__(self):
        self.gateway = LLMGateway()

    def evaluate_fit(self, profile: dict, job_title: str, job_desc: str,
                     location: str = "Not specified", salary_range_lpa=None,
                     experience_range_years=None) -> dict:
        cand_exp = float(profile.get("total_years_experience", 3.0))
        cand_skills = {s.lower().strip() for s in profile.get("skills", [])}
        preferred_locations = profile.get("preferred_locations", [])
        salary_expectation = _get_salary_expectation_lpa(profile)

        t = job_title.lower()

        # --- Hard stack filter ---
        for kw in HARD_STACK_KEYWORDS:
            if kw in t and kw not in cand_skills:
                return {
                    "is_viable": False,
                    "match_score": 0,
                    "rejection_reason": f"Role demands {kw} (not in profile skills)",
                }

        # --- Location ---
        if not _location_matches(location, preferred_locations):
            return {
                "is_viable": False, "match_score": 0,
                "rejection_reason": f"Location '{location}' not in preferred list",
                "detected_experience": "Not evaluated",
                "salary_range": "Not evaluated",
                "location": location,
            }

        # --- Experience ---
        exp_ok, exp_reason = _experience_ok(cand_exp, experience_range_years)
        if not exp_ok:
            return {
                "is_viable": False, "match_score": 0,
                "rejection_reason": exp_reason,
                "detected_experience": (
                    f"{experience_range_years[0]:g}-{experience_range_years[1]:g} Years"
                    if experience_range_years else "Not stated"
                ),
                "salary_range": "Not evaluated",
                "location": location,
            }

        # --- Salary ---
        sal_ok, sal_reason = _salary_ok(salary_range_lpa, salary_expectation)
        if not sal_ok:
            return {
                "is_viable": False, "match_score": 0,
                "rejection_reason": sal_reason,
                "detected_experience": "Not evaluated",
                "salary_range": (
                    f"₹{salary_range_lpa[0]:g} - ₹{salary_range_lpa[1]:g} LPA"
                    if salary_range_lpa else "Not stated"
                ),
                "location": location,
            }

        # --- LLM soft scoring ---
        salary_fact = (
            f"₹{salary_range_lpa[0]:g} - ₹{salary_range_lpa[1]:g} LPA"
            if salary_range_lpa else "not stated in the JD"
        )
        experience_fact = (
            f"{experience_range_years[0]:g}-{experience_range_years[1]:g} years"
            if experience_range_years else "not stated in the JD"
        )

        sys_prompt = f"""
You are a strict technical recruiter evaluating a candidate against a job description.
Candidate Experience: {cand_exp} Years.
Candidate Verified Skills: {profile.get('skills', [])}

Ground truth already extracted from the real JD page (do not contradict these):
- Location: {location}
- Salary stated in JD: {salary_fact}
- Experience stated in JD: {experience_fact}

STRICT ACCURACY RULES:
1. If the job requires a primary tech stack the candidate lacks, score MUST be < 60% and is_viable = false.
2. If the ground truth above says "not stated in the JD", return the literal string "Not specified in JD" — never guess.
3. Do NOT exaggerate match fit.

Return JSON schema:
{{
    "is_viable": true/false,
    "match_score": 85,
    "detected_experience": "{experience_fact if experience_range_years else 'Not specified in JD'}",
    "salary_range": "{salary_fact if salary_range_lpa else 'Not specified in JD'}",
    "location": "{location}",
    "skills_gap": "None" | "Specific Missing Tools"
}}
"""
        prompt = f"Target Role: {job_title}\nJob Description:\n{job_desc[:2500]}"
        try:
            result = self.gateway.generate(prompt=prompt, system_prompt=sys_prompt, temperature=0.1)
            result.setdefault("location", location)
            return result
        except Exception:
            return {"is_viable": False, "match_score": 0, "location": location}
