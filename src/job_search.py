import re
import requests
from datetime import date
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import src.config as config

ATS_DOMAINS = "(site:myworkdayjobs.com OR site:boards.greenhouse.io OR site:jobs.lever.co OR site:jobs.ashbyhq.com OR site:smartrecruiters.com)"
LOCATIONS = '("Gurgaon" OR "Gurugram" OR "Noida" OR "Delhi" OR "Bangalore" OR "Bengaluru" OR "Remote" OR "India")'

# How many distinct queries to run per pipeline execution, and how many
# result pages (10 results each) to pull per query. Raising these widens
# the pool but costs more SerpAPI/searchapi credits per run.
MAX_QUERIES = getattr(config, "MAX_SEARCH_QUERIES", 4)
PAGES_PER_QUERY = getattr(config, "SEARCH_PAGES_PER_QUERY", 2)

KNOWN_CITIES = [
    "Gurgaon", "Gurugram", "Noida", "New Delhi", "Delhi", "Bangalore", "Bengaluru",
    "Mumbai", "Pune", "Hyderabad", "Chennai", "Kolkata", "Ahmedabad", "Remote",
    "Hybrid", "Work From Home",
]

_SALARY_PATTERNS = [
    re.compile(r"(?:₹|INR|Rs\.?)?\s*(\d{1,3}(?:\.\d+)?)\s*(?:-|to)\s*(?:₹|INR|Rs\.?)?\s*(\d{1,3}(?:\.\d+)?)\s*L(?:PA|akhs?)\b", re.IGNORECASE),
    re.compile(r"(?:₹|INR|Rs\.?)?\s*(\d{1,3}(?:\.\d+)?)\s*L(?:PA|akhs?)\b", re.IGNORECASE),
    re.compile(r"\$\s*([\d,]{4,7})\s*(?:-|to)\s*\$?\s*([\d,]{4,7})", re.IGNORECASE),
]

_EXPERIENCE_PATTERNS = [
    re.compile(r"(\d{1,2})\s*(?:-|to)\s*(\d{1,2})\s*\+?\s*years?\s*(?:of)?\s*(?:relevant\s*)?experience", re.IGNORECASE),
    re.compile(r"(?:minimum|min\.?|at least)?\s*(\d{1,2})\s*\+?\s*years?\s*(?:of)?\s*(?:relevant\s*)?experience", re.IGNORECASE),
]


def clean_company_name(raw_name: str, url: str) -> str:
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
    haystack = f"{title} {text}"
    for city in KNOWN_CITIES:
        if re.search(rf"\b{re.escape(city)}\b", haystack, re.IGNORECASE):
            return city
    return "Not specified"


def extract_salary_lpa(text: str):
    for pattern in _SALARY_PATTERNS[:1]:
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


def _rotate(items: list, window: int, offset: int) -> list:
    """Pick a different slice of `items` each day so repeated runs surface
    different role/skill combinations instead of the exact same query."""
    if not items:
        return items
    n = len(items)
    if n <= window:
        return items
    start = offset % n
    idxs = [(start + i) % n for i in range(window)]
    return [items[i] for i in idxs]


class JobSearchEngine:
    def __init__(self):
        self.api_key = config.SERPAPI_KEY

    def _build_queries(self, profile: dict) -> list[str]:
        all_roles = profile.get("target_roles", ["Business Analyst", "Data Analyst"])
        all_skills = profile.get("skills", ["Power Platform", "SQL", "Excel"])

        # Rotate which roles/skills are emphasized based on the day of year,
        # so the query set (and therefore the result pool) actually changes
        # day to day instead of being identical on every run.
        day_offset = date.today().toordinal()
        roles = _rotate(all_roles, min(4, len(all_roles)), day_offset)
        skills = _rotate(all_skills, min(4, len(all_skills)), day_offset + 1)

        role_clause = " OR ".join([f'"{r}"' for r in roles[:4]])
        skill_clause = " OR ".join([f'"{s}"' for s in skills[:4]])
        negatives = '-Intern -Director -VP -Head'

        queries = [
            f'{ATS_DOMAINS} intitle:({role_clause}) {LOCATIONS} {negatives}',
            f'{ATS_DOMAINS} ({role_clause}) ({skill_clause}) {LOCATIONS} {negatives}',
        ]

        # One query per individual top skill, broadened beyond the ATS-only
        # domain restriction, to pull in postings the tight query misses.
        for skill in skills[:2]:
            queries.append(f'intitle:({role_clause}) "{skill}" {LOCATIONS} {negatives}')

        return queries[:MAX_QUERIES]

    def _search(self, query: str, start: int = 0) -> list[dict]:
        url = "https://www.searchapi.io/api/v1/search"
        params = {"engine": "google", "q": query, "api_key": self.api_key, "gl": "in", "hl": "en", "num": 15, "start": start}
        res = requests.get(url, params=params, timeout=15)
        if res.status_code in [401, 404]:
            url = "https://serpapi.com/search.json"
            params = {"engine": "google", "q": query, "api_key": self.api_key, "gl": "in", "hl": "en", "start": start}
            res = requests.get(url, params=params, timeout=15)
        if res.status_code != 200:
            return []
        return res.json().get("organic_results", [])

    def fetch_jobs(self, profile: dict) -> list[dict]:
        queries = self._build_queries(profile)
        all_jobs = []
        seen = set()
        for query in queries:
            for page in range(PAGES_PER_QUERY):
                results = self._search(query, start=page * 10)
                if not results:
                    break  # no more pages for this query
                for item in results:
                    link = item.get("link", "")
                    if not link or link in seen:
                        continue
                    raw_title = item.get("title", "")
                    title = re.sub(r"\s*[-|–]\s*(Greenhouse|Lever|Workday|Ashby|SmartRecruiters|Jobs|Careers).*", "", raw_title, flags=re.IGNORECASE).strip()
                    company = clean_company_name(item.get("source", ""), link)
                    snippet = item.get("snippet", "")
                    seen.add(link)

                    full_text = fetch_full_jd(link)
                    jd_text = full_text if full_text else snippet

                    all_jobs.append({
                        "job_id": link,
                        "title": title,
                        "company_name": company,
                        "description": jd_text,
                        "apply_link": link,
                        "location": extract_location(title, jd_text),
                        "salary_range_lpa": extract_salary_lpa(jd_text),
                        "experience_range_years": extract_experience_years(jd_text),
                        "used_full_jd": bool(full_text),
                    })
        return all_jobs
