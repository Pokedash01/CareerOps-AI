import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import src.config as config

ATS_DOMAINS = "(site:myworkdayjobs.com OR site:boards.greenhouse.io OR site:jobs.lever.co OR site:jobs.ashbyhq.com OR site:smartrecruiters.com)"
NEGATIVES = '-"Senior Manager" -Director -VP -Intern -Lead -Head'
LOCATIONS = '("Gurgaon" OR "Gurugram" OR "Noida" OR "Delhi" OR "Bangalore" OR "Bengaluru" OR "Remote" OR "India")'

def extract_company_from_url(url: str) -> str:
    try:
        domain = urlparse(url).netloc.lower()
        path = urlparse(url).path.lower()
        parts = domain.split(".")
        if any(ats in domain for ats in ["greenhouse.io", "lever.co", "ashbyhq.com", "smartrecruiters.com"]):
            if parts[0] not in ["boards", "job-boards", "jobs", "www"]:
                return parts[0].replace("-", " ").capitalize()
            elif len(path.split("/")) > 1:
                return path.split("/")[1].replace("-", " ").capitalize()
        elif "myworkdayjobs.com" in domain:
            return parts[0].split("-")[0].replace("-", " ").capitalize()
    except Exception:
        pass
    return "Enterprise Portal"

def fetch_portal_description(url: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            return " ".join(soup.stripped_strings)[:4000]
    except Exception:
        pass
    return ""

class JobSearchEngine:
    def __init__(self):
        self.api_key = config.SERPAPI_KEY

    def _build_queries(self, profile: dict) -> list[str]:
        target_roles = profile.get("target_roles", ["Analyst", "Developer"])
        skills = profile.get("skills", ["SQL", "Python"])
        
        # Build clean boolean groups dynamically from candidate profile
        role_clause = " OR ".join([f'"{r}"' for r in target_roles[:3]])
        skill_clause = " OR ".join([f'"{s}"' for s in skills[:3]])

        return [
            f'{ATS_DOMAINS} intitle:({role_clause}) {LOCATIONS} {NEGATIVES}',
            f'{ATS_DOMAINS} ({role_clause}) ({skill_clause}) {LOCATIONS} {NEGATIVES}'
        ]

    def fetch_jobs(self, profile: dict) -> list[dict]:
        queries = self._build_queries(profile)
        all_jobs = []
        seen_links = set()

        for query in queries:
            print(f"[Job Search] Querying ATS: {query[:85]}...")
            url = "https://www.searchapi.io/api/v1/search"
            params = {
                "engine": "google",
                "q": query,
                "api_key": self.api_key,
                "gl": "in",
                "hl": "en",
                "num": 20
            }
            
            res = requests.get(url, params=params, timeout=15)
            # Fallback to SerpApi structure if needed
            if res.status_code in [401, 404]:
                url = "https://serpapi.com/search.json"
                params = {"engine": "google", "q": query, "api_key": self.api_key, "gl": "in", "hl": "en"}
                res = requests.get(url, params=params, timeout=15)

            if res.status_code != 200:
                print(f"[Job Search] API HTTP {res.status_code}: {res.text[:120]}")
                continue

            data = res.json()
            organic_results = data.get("organic_results", [])
            print(f"[Job Search] Returned {len(organic_results)} direct ATS listings.")

            for item in organic_results:
                link = item.get("link", "")
                if not link or link in seen_links:
                    continue

                raw_title = item.get("title", "")
                title = re.sub(r"\s*[-|–]\s*(Greenhouse|Lever|Workday|Ashby|SmartRecruiters|Jobs|Careers).*", "", raw_title, flags=re.IGNORECASE).strip()
                snippet = item.get("snippet", "")
                company = extract_company_from_url(link)
                seen_links.add(link)

                full_desc = snippet
                if len(snippet) < 250:
                    fetched = fetch_portal_description(link)
                    if fetched:
                        full_desc = fetched

                all_jobs.append({
                    "job_id": link,
                    "title": title,
                    "company_name": company,
                    "description": full_desc,
                    "apply_link": link,
                    "location": "India / Remote"
                })

        return all_jobs
