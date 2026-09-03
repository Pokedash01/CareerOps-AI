import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import src.config as config

ATS_DOMAINS = "(site:myworkdayjobs.com OR site:boards.greenhouse.io OR site:jobs.lever.co OR site:jobs.ashbyhq.com OR site:smartrecruiters.com)"
LOCATIONS = '("Gurgaon" OR "Gurugram" OR "Noida" OR "Delhi" OR "Bangalore" OR "Bengaluru" OR "Remote" OR "India")'

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
                seen.add(link)

                all_jobs.append({
                    "job_id": link,
                    "title": title,
                    "company_name": company,
                    "description": item.get("snippet", ""),
                    "apply_link": link,
                    "location": "Remote / India"
                })

        return all_jobs
