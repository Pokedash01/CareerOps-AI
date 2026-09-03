import json
import os
import requests
from pathlib import Path
from pypdf import PdfReader

from src.telegram_ux import TelegramSaaSClient
from src.profiler import extract_user_profile
from src.job_search import JobSearchEngine
from src.matcher import MatchEngine
from src.tailor import DocumentTailor
import src.config as config

STATE_FILE = Path("data/state.json")

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"telegram_offset": None, "seen_jobs": []}

def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))

def extract_text_from_pdf(pdf_path: Path) -> str:
    try:
        reader = PdfReader(pdf_path)
        return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    except Exception as e:
        return ""

def fetch_new_users(bot: TelegramSaaSClient, state: dict):
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {"timeout": 10, "offset": state.get("telegram_offset")}
    try:
        res = requests.get(url, params=params).json()
        for item in res.get("result", []):
            state["telegram_offset"] = item["update_id"] + 1
            message = item.get("message", {})
            chat_id = str(message.get("chat", {}).get("id"))
            
            if "document" in message:
                file_id = message["document"]["file_id"]
                file_info = requests.get(f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}").json()
                file_path = file_info["result"]["file_path"]
                pdf_data = requests.get(f"https://api.telegram.org/file/bot{config.TELEGRAM_BOT_TOKEN}/{file_path}").content
                
                user_dir = Path(f"data/users/{chat_id}/inputs")
                user_dir.mkdir(parents=True, exist_ok=True)
                (user_dir / "resume.pdf").write_bytes(pdf_data)
                
                profile_path = Path(f"data/users/{chat_id}/profile.json")
                if profile_path.exists(): profile_path.unlink()
                bot.send_message(chat_id, "✅ Resume received and parsed! Your CareerOps engine is now hunting.")
    except Exception as e:
        pass

def run_engine(bot: TelegramSaaSClient, state: dict):
    searcher = JobSearchEngine()
    matcher = MatchEngine()
    tailor = DocumentTailor()
    users_dir = Path("data/users")
    
    if not users_dir.exists(): return
        
    for user_folder in users_dir.iterdir():
        if not user_folder.is_dir(): continue
        chat_id = user_folder.name
        pdf_path = user_folder / "inputs" / "resume.pdf"
        
        if not pdf_path.exists(): continue
            
        resume_text = extract_text_from_pdf(pdf_path)
        if not resume_text: continue
        profile = extract_user_profile(chat_id, resume_text)
        
        jobs = searcher.fetch_jobs(profile)
        for job in jobs:
            job_id = job.get("job_id")
            if job_id in state["seen_jobs"]: continue
                
            fit = matcher.evaluate_fit(profile, job.get("description", ""))
            if fit.get("is_viable") and fit.get("match_score", 0) >= config.MIN_MATCH_SCORE:
                assets = tailor.generate_assets(profile, job, fit)
                out_dir = user_folder / "outputs" / job_id
                out_dir.mkdir(parents=True, exist_ok=True)
                
                resume_md = out_dir / "Tailored_Resume.md"
                cl_md = out_dir / "Cover_Letter.md"
                resume_md.write_text(assets.get("resume_md", ""), encoding="utf-8")
                cl_md.write_text(assets.get("cover_letter_md", ""), encoding="utf-8")
                
                bot.deliver_assets(chat_id, job.get("title"), str(resume_md), str(cl_md))
            state["seen_jobs"].append(job_id)

if __name__ == "__main__":
    bot = TelegramSaaSClient()
    state = load_state()
    fetch_new_users(bot, state)
    run_engine(bot, state)
    save_state(state)
