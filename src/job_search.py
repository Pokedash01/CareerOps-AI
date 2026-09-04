import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import src.config as config

ATS_DOMAINS = "(site:myworkdayjobs.com OR site:boards.greenhouse.io OR site:jobs.lever.co OR site:jobs.ashbyhq.com OR site:smartrecruiters.com)"
LOCATIONS = '("Gurgaon" OR "Gurugram" OR "Noida" OR "Delhi" OR "Bangalore" OR "Bengaluru" OR "Remote" OR "India")'

# Cities we can confidently recognize in JD text. Extend as needed.
KNOWN_CITIES = [
    "Gurgaon", "Gurugram", "Noida", "New Delhi", "Delhi", "Bangalore", "Bengaluru",
    "Mumbai", "Pune", "Hyderabad", "Chennai", "Kolkata", "Ahmedabad", "Remote",
    "Hybrid", "Work From Home",
]

_SALARY_PATTERNS = [
    # 12-18 LPA / 12 to 18 LPA / ₹12-₹18 LPA
    re.compile(r"(?:₹|INR|Rs\.?)?\s*(\d{1,3}(?:\.\d+)?)\s*(?:-|to)\s*(?:₹|INR|Rs\.?)?\s*(\d{1,3}(?:\.\d+)?)\s*L(?:PA|akhs?)\b", re.IGNORECASE),
    # 15 LPA (single figure)
    re.compile(r"(?:₹|INR|Rs\.?)?\s*(\d{1,3}(?:\.\d+)?)\s*L(?:PA|akhs?)\b", re.IGNORECASE),
    # $100,000 - $130,000
    re.compile(r"\$\s*([\d,]{4,7})\s*(?:-|to)\s*\$?\s*([\d,]{4,7})", re.IGNORECASE),
]

_EXPERIENCE_PATTERNS = [
    # "3-5 years", "3 to 5 years of experience"
    re.compile(r"(\d{1,2})\s*(?:-|to)\s*(\d{1,2})\s*\+?\s*years?\s*(?:of)?\s*(?:relevant\s*)?experience", re.IGNORECASE),
    # "5+ years", "minimum 5 years", "at least 5 years"
    re.compile(r"(?:minimum|min\.?|at least)?\s*(\d{1,2})\s*\+?\s*years?\s*(?:of)?\s*(?:relevant\s*)?experience", re.IGNORECASE),
]


def clean_company_name(raw_name: str, url: str) -> str:
    """Cleans up run-on company names like Squircleitconsultingservicespvtltd."""
    try:
        domain = urlparse(url).netloc.lower()
        parts = domain.split(".")
        candidate = parts[0] if parts[0] not in ["boards", "jobs", "www"] else parts[1]
        candidate = re.sub(r"(it|consulting|services|pvt|ltd|inc|llc|tech).*", "", candidate, flags=re.IGNORECASE)
        candidate = candidate.replace("-", " ").strip().title()
        if len(candidate) >= 3:
            return candidate
    except Exception:
        pass
    cleaned = re.sub(r"(pvt|ltd|services|consulting|technologies).*", "", raw_name, flags=re.IGNORECASE)
    return cleaned.strip().title() or raw_name


def fetch_full_jd(url: str, timeout: int = 10) -> str:
    """
    Fetches the real job description page. Falls back to empty string on
    any failure (blocked, JS-rendered page, timeout, etc.) - callers should
    fall back to the search snippet in that case rather than fabricate data.
    """
    headers = {"User-Agent": "Mozilla/5.0 (compatible; CareerOpsBot/1.0)"}
    try:
        res = requests.get(url, headers=headers, timeout=timeout)
        if res.status_code != 200:
            return ""
        soup = BeautifulSoup(res.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text)
        return text[:8000]
    except Exception:
        return ""


def extract_location(title: str, text: str) -> str:
    """Deterministic location extraction from real JD/title text.
    Returns 'Not specified' rather than guessing - callers must treat that
    as unknown, not as a match or a mismatch."""
    haystack = f"{title} {text}"
    for city in KNOWN_CITIES:
        if re.search(rf"\b{re.escape(city)}\b", haystack, re.IGNORECASE):
            return city
    return "Not specified"


def extract_salary_lpa(text: str):
    """Returns (min_lpa, max_lpa) as floats if a salary figure is genuinely
    present in the JD text, else None. Never invents a number."""
    for pattern in _SALARY_PATTERNS[:1]:  # range pattern first
        m = pattern.search(text)
        if m:
            try:
                lo, hi = float(m.group(1)), float(m.group(2))
                return (min(lo, hi), max(lo, hi))
            except Exception:
                continue
    m = _SALARY_PATTERNS[1].search(text)
    if m:
        try:
            v = float(m.group(1))
            return (v, v)
        except Exception:
            pass
    return None


def extract_experience_years(text: str):
    """Returns (min_years, max_years) if the JD states a requirement,
    else None. Never guesses."""
    m = _EXPERIENCE_PATTERNS[0].search(text)
    if m:
        try:
            lo, hi = float(m.group(1)), float(m.group(2))
            return (min(lo, hi), max(lo, hi))
        except Exception:
            pass
    m = _EXPERIENCE_PATTERNS[1].search(text)
    if m:
        try:
            v = float(m.group(1))
            return (v, v)
        except Exception:
            pass
    return None


class JobSearchEngine:
    def __init__(self):
        self.api_key = config.SERPAPI_KEY

    def _build_queries(self, profile: dict) -> list[str]:
        target_roles = profile.get("target_roles", ["Business Analyst", "Data Analyst"])
        skills = profile.get("skills", ["Power Platform", "SQL", "Excel"])
        role_clause = " OR ".join([f'"{r}"' for r in target_roles[:3]])
        skill_clause = " OR ".join([f'"{s}"' for s in skills[:3]])
        negatives = '-Intern -Director -VP -Head'
        return [
            f'{ATS_DOMAINS} intitle:({role_clause}) {LOCATIONS} {negatives}',
            f'{ATS_DOMAINS} ({role_clause}) ({skill_clause}) {LOCATIONS} {negatives}'
        ]

    def fetch_jobs(self, profile: dict) -> list[dict]:
        queries = self._build_queries(profile)
        all_jobs = []
        seen = set()
        for query in queries:
            url = "https://www.searchapi.io/api/v1/search"
            params = {"engine": "google", "q": query, "api_key": self.api_key, "gl": "in", "hl": "en", "num": 15}
            res = requests.get(url, params=params, timeout=15)
            if res.status_code in [401, 404]:
                url = "https://serpapi.com/search.json"
                params = {"engine": "google", "q": query, "api_key": self.api_key, "gl": "in", "hl": "en"}
                res = requests.get(url, params=params, timeout=15)
            if res.status_code != 200:
                continue
            for item in res.json().get("organic_results", []):
                link = item.get("link", "")
                if not link or link in seen:
                    continue
                raw_title = item.get("title", "")
                title = re.sub(r"\s*[-|–]\s*(Greenhouse|Lever|Workday|Ashby|SmartRecruiters|Jobs|Careers).*", "", raw_title, flags=re.IGNORECASE).strip()
                company = clean_company_name(item.get("source", ""), link)
                snippet = item.get("snippet", "")
                seen.add(link)

                # Try to get the real JD; fall back to the search snippet if
                # the page can't be fetched (blocked, JS-rendered, etc.)
                full_text = fetch_full_jd(link)
                jd_text = full_text if full_text else snippet
                used_full_jd = bool(full_text)

                all_jobs.append({
                    "job_id": link,
                    "title": title,
                    "company_name": company,
                    "description": jd_text,
                    "apply_link": link,
                    "location": extract_location(title, jd_text),
                    "salary_range_lpa": extract_salary_lpa(jd_text),
                    "experience_range_years": extract_experience_years(jd_text),
                    "used_full_jd": used_full_jd,
                })
        return all_jobs
