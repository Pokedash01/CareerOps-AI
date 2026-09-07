"""
Job search engine.

All user-specific values come from the profile dict — never from hardcoded
constants. Engine-level choices (ATS domains, training platform exclusions,
aggregator site bans) are constant and stay here.
"""
import re
import requests
from datetime import date
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import src.config as config

# --------------------------------------------------------------------
# Engine constants (NOT user-specific)
# --------------------------------------------------------------------

ATS_DOMAINS = (
    "(site:myworkdayjobs.com OR site:boards.greenhouse.io OR "
    "site:jobs.lever.co OR site:jobs.ashbyhq.com OR "
    "site:smartrecruiters.com)"
)

# Training/course platforms that return as organic results for skill
# searches but are not real job postings.
TRAINING_EXCLUSIONS = (
    "-site:udemy.com -site:udacity.com -site:coursera.org "
    "-site:linkedin.com/learning -site:skillshare.com "
    "-site:pluralsight.com -site:edx.org -site: codecademy.com "
    "-site:simplilearn.com -site:greatlearning.com "
    "-site:intellipaat.com -site:upgrad.com -site:scaler.com "
    "-site:naukri.com/learning -site:邪眼.info -site:邪眼.blog "
    "-site:邪眼.io -site:邪眼.dev"
)

AGGREGATOR_EXCLUSIONS = (
    "-site:indeed.com -site:in.indeed.com -site:naukri.com "
    "-site:linkedin.com -site:glassdoor.com -site:glassdoor.co.in "
    "-site:shine.com -site:timesjobs.com -site:foundit.in "
    "-site:monsterindia.com -site:instahyre.com"
)

_LISTING_PAGE_MARKERS = re.compile(
    r"(indeed\.[a-z.]+/(jobs|q-)|naukri\.com/[\w-]*-jobs(-in-[\w-]+)?(?:/|\?|$)|"
    r"linkedin\.com/jobs/search|glassdoor\.co\.?in/Job/|glassdoor\.com/Job/|"
    r"shine\.com/job-search|timesjobs\.com/job-search|foundit\.in/search|"
    r"monsterindia\.com/search)",
    re.IGNORECASE,
)

MAX_QUERIES = getattr(config, "MAX_SEARCH_QUERIES", 4)
PAGES_PER_QUERY = getattr(config, "SEARCH_PAGES_PER_QUERY", 2)

# Used only for parsing JDs (extracting location from raw text) — not
# used to build queries or filter results.
KNOWN_CITIES = [
    "Gurgaon", "Gurugram", "Noida", "New Delhi", "Delhi",
    "Bangalore", "Bengaluru", "Mumbai", "Pune", "Hyderabad",
    "Chennai", "Kolkata", "Ahmedabad", "Remote", "Hybrid",
    "Work From Home", "San Francisco", "New York", "London",
    "Singapore", "Dubai",
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


# --------------------------------------------------------------------
# Post-fetch filters (run after get, before scoring)
# --------------------------------------------------------------------

def is_training_url(url: str) -> bool:
    if not url:
        return False
    tlds = [
        "udemy.com", "udacity.com", "coursera.org", "linkedin.com/learning",
        "skillshare.com", "pluralsight.com", "edx.org", "codecademy.com",
        "simplilearn.com", "greatlearning.com", "intellipaat.com",
        "upgrad.com", "scaler.com", "naukri.com/learning",
    ]
    l = url.lower()
    return any(t in l for t in tlds)


def is_training_title(title: str) -> bool:
    if not title:
        return False
    t = title.lower()
    return any(
        kw in t for kw in [
            "course", "tutorial", "learn ", " training ",
            "certification program", "bootcamp", " from scratch",
        ]
    )


def is_training_content(title: str, snippet: str) -> bool:
    if is_training_title(title):
        return True
    t = (title + " " + snippet).lower()
    return any(
        kw in t for kw in [
            "enroll now", "limited seats", "apply now for free",
            "100% placement", "live project", "download syllabus",
            "course curriculum", "course fee",
        ]
    )


def is_specific_job_link(url: str) -> bool:
    if not url:
        return False
    if _LISTING_PAGE_MARKERS.search(url):
        return False
    if re.search(r"[?&](q|k|keywords)=", url, re.IGNORECASE) and "myworkdayjobs" not in url.lower():
        return False
    return True


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------

def _infer_country_gl(profile: dict) -> str:
    """Pick Google locale (gl) from preferred locations. Any non-India
    city or 'Remote' without India suggests a US/global candidate."""
    locs = [l.lower() for l in profile.get("preferred_locations", [])]
    india_signals = {"india", "delhi", "gurgaon", "gurugram", "bangalore",
                     "bengaluru", "mumbai", "pune", "chennai", "hyderabad",
                     "kolkata", "noida"}
    if locs and not any(s in " ".join(locs) for s in india_signals):
        return "us"
    return "in"


def clean_company_name(raw_name: str, url: str) -> str:
    try:
        domain = urlparse(url).netloc.lower()
        parts = domain.split(".")
        candidate = parts[0] if parts[0] not in ("boards", "jobs", "www") else parts[1]
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
    if not items:
        return items
    n = len(items)
    if n <= window:
        return items
    start = offset % n
    idxs = [(start + i) % n for i in range(window)]
    return [items[i] for i in idxs]


# --------------------------------------------------------------------
# Query builder
# --------------------------------------------------------------------

class JobSearchEngine:
    def __init__(self):
        self.api_key = config.SERPAPI_KEY

    def _build_queries(self, profile: dict) -> list[str]:
        all_roles = profile.get("target_roles", [])
        all_skills = profile.get("skills", [])
        all_locations = profile.get("preferred_locations", [])

        if not all_roles:
            print("[JobSearch] No target_roles in profile — refusing to run with empty query set.")
            return []

        # Build the location clause
        if all_locations:
            loc_parts = " OR ".join(f'"{l}"' for l in all_locations[:6])
            loc_clause = f"({loc_parts})"
        else:
            loc_clause = '"Remote" OR "Work From Home"'

        # Build the negative clause from anti_targets and preferences
        negatives = []
        for kw in profile.get("anti_targets", []):
            negatives.append(f"-{kw}")
        if not profile.get("open_to_internship", False):
            negatives.append("-Intern")
        neg_clause = " ".join(negatives) if negatives else ""

        # Rotate roles/skills day-to-day so the result pool actually changes
        day_offset = date.today().toordinal()
        roles = _rotate(all_roles, min(4, len(all_roles)), day_offset)
        skills = _rotate(all_skills, min(4, len(all_skills)), day_offset + 1)

        role_clause = " OR ".join([f'"{r}"' for r in roles[:4]])
        skill_clause = " OR ".join([f'"{s}"' for s in skills[:4]])

        queries = []

        # ATS-only queries (highest precision)
        queries.append(
            f"{ATS_DOMAINS} intitle:({role_clause}) {loc_clause} {neg_clause}".strip()
        )
        if skills:
            queries.append(
                f"{ATS_DOMAINS} ({role_clause}) ({skill_clause}) {loc_clause} {neg_clause}".strip()
            )

        # Broadened skill queries (include non-ATS sites, exclude aggregators)
        broadened = f"intitle:({role_clause}) ({skill_clause}) {loc_clause} {neg_clause} {AGGREGATOR_EXCLUSIONS}"
        if not profile.get("open_to_training_programs", False):
            broadened += f" {TRAINING_EXCLUSIONS}"
        queries.append(broadened.strip())

        if config.DEBUG_SEARCH:
            for q in queries[:MAX_QUERIES]:
                print(f"[JobSearch] Query: {q}")

        return queries[:MAX_QUERIES]

    def _search(self, query: str, start: int = 0) -> list[dict]:
        gl = _infer_country_gl(self)
        params = {
            "engine": "google", "q": query,
            "api_key": self.api_key,
            "gl": gl, "hl": "en",
            "num": 15, "start": start,
        }
        url = "https://www.searchapi.io/api/v1/search"
        res = requests.get(url, params=params, timeout=15)
        if res.status_code in [401, 404]:
            url = "https://serpapi.com/search.json"
            params = {"engine": "google", "q": query, "api_key": self.api_key,
                      "gl": gl, "hl": "en", "start": start}
            res = requests.get(url, params=params, timeout=15)
        if res.status_code != 200:
            return []
        return res.json().get("organic_results", [])

    def fetch_jobs(self, profile: dict) -> list[dict]:
        queries = self._build_queries(profile)
        if not queries:
            return []

        all_jobs = []
        seen = set()

        for query in queries:
            for page in range(PAGES_PER_QUERY):
                results = self._search(query, start=page * 10)
                if not results:
                    break
                for item in results:
                    link = item.get("link", "")
                    if not link or link in seen:
                        continue
                    if not is_specific_job_link(link):
                        seen.add(link)
                        continue

                    title = item.get("title", "")
                    snippet = item.get("snippet", "")

                    # Training filter
                    if is_training_url(link) or is_training_title(title) or is_training_content(title, snippet):
                        seen.add(link)
                        continue

                    seen.add(link)
                    raw_title = re.sub(
                        r"\s*[-|–]\s*(Greenhouse|Lever|Workday|Ashby|SmartRecruiters|Jobs|Careers).*",
                        "", title, flags=re.IGNORECASE,
                    ).strip()

                    full_text = fetch_full_jd(link)
                    jd_text = full_text if full_text else snippet

                    all_jobs.append({
                        "job_id": link,
                        "title": raw_title,
                        "company_name": clean_company_name(item.get("source", ""), link),
                        "description": jd_text,
                        "apply_link": link,
                        "location": extract_location(raw_title, jd_text),
                        "salary_range_lpa": extract_salary_lpa(jd_text),
                        "experience_range_years": extract_experience_years(jd_text),
                        "used_full_jd": bool(full_text),
                    })

        return all_jobs
