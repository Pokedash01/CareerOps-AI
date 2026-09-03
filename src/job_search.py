import requests
import json
from src.llm_gateway import LLMGateway
import src.config as config

class JobSearchEngine:
    def __init__(self):
        self.api_key = config.SERPAPI_KEY
        self.gateway = LLMGateway()

    def _generate_queries(self, profile: dict) -> list[str]:
        prompt = f"Profile: {json.dumps(profile)}\nGenerate 3 Google Jobs search strings for this candidate targeting {config.DEFAULT_LOCATION}. Output JSON: {{\"queries\": [\"query1\", \"query2\", \"query3\"]}}"
        sys_prompt = "You are a recruiter formulating targeted boolean job search queries. Output strictly JSON."
        res = self.gateway.generate(prompt=prompt, system_prompt=sys_prompt)
        return json.loads(res).get("queries", [])

    def fetch_jobs(self, profile: dict) -> list[dict]:
        queries = self._generate_queries(profile)
        all_jobs = []
        seen_job_ids = set()

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
                jobs = res.json().get("jobs_results", [])
                for job in jobs:
                    if job.get("job_id") not in seen_job_ids:
                        seen_job_ids.add(job.get("job_id"))
                        all_jobs.append(job)
        return all_jobs
