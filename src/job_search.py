import requests
import json
from src.llm_gateway import LLMGateway
import src.config as config

class JobSearchEngine:
    def __init__(self):
        self.api_key = config.SERPAPI_KEY
        self.gateway = LLMGateway()

    def _generate_queries(self, profile: dict) -> list[str]:
        prompt = (
            f"Profile: {json.dumps(profile)}\n"
            f"Generate 3 focused Google Jobs search query strings targeting {config.DEFAULT_LOCATION}. "
            f"Return JSON: {{\"queries\": [\"query1\", \"query2\", \"query3\"]}}"
        )
        sys_prompt = "You are a recruiter generating boolean job search strings. Output valid JSON only."
        data = self.gateway.generate(prompt=prompt, system_prompt=sys_prompt)
        return data.get("queries", [])

    def fetch_jobs(self, profile: dict) -> list[dict]:
        queries = self._generate_queries(profile)
        all_jobs = []
        seen_keys = set()

        for query in queries:
            url = "https://serpapi.com/search.json"
            params = {
                "engine": "google_jobs",
                "q": query,
                "api_key": self.api_key,
                "hl": "en"
            }
            res = requests.get(url, params=params)
            if res.status_code == 200:
                for job in res.json().get("jobs_results", []):
                    dedup_key = f"{job.get('title')}_{job.get('company_name')}"
                    if dedup_key not in seen_keys:
                        seen_keys.add(dedup_key)
                        all_jobs.append(job)
        return all_jobs
