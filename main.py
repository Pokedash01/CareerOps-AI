import os
import json
import hashlib
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

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"telegram_offset": None, "seen_jobs": []}

def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")

def extract_pdf_text(pdf_path: Path) -> str:
    try:
        reader = PdfReader(pdf_path)
        text = "\n".join([page.extract_text() or "" for page in reader.pages]).strip()
        print(f"[PDF] Extracted {len(text)} characters from {pdf_path.name}")
        return text
    except Exception as e:
        print(f"[PDF] Extraction failed for {pdf_path}: {e}")
        return ""

def process_telegram_inbox(bot: TelegramSaaSClient, state: dict):
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {"timeout": 10, "offset": state.get("telegram_offset")}
    
    try:
        res = requests.get(url, params=params).json()
        for item in res.get("result", []):
            state["telegram_offset"] = item["update_id"] + 1
            msg = item.get("message", {})
            chat_id = str(msg.get("chat", {}).get("id"))
            
            if "document" in msg:
                doc = msg["document"]
                if doc.get("file_name", "").lower().endswith(".pdf"):
                    f_info = requests.get(f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getFile?file_id={doc['file_id']}").json()
                    file_path = f_info["result"]["file_path"]
                    content = requests.get(f"https://api.telegram.org/file/bot{config.TELEGRAM_BOT_TOKEN}/{file_path}").content
                    
                    user_dir = Path(f"data/users/{chat_id}/inputs")
                    user_dir.mkdir(parents=True, exist_ok=True)
                    (user_dir / "resume.pdf").write_bytes(content)
                    
                    cached_profile = Path(f"data/users/{chat_id}/profile.json")
                    if cached_profile.exists():
                        cached_profile.unlink()
                        
                    bot.send_message(chat_id, "✅ *Resume received and indexed!* CareerOps is actively matching you with roles.")
                    print(f"[Telegram] Saved new resume for user {chat_id}")
                else:
                    bot.send_message(chat_id, "⚠️ Please upload your resume as a standard *.PDF* document.")
            
            elif "text" in msg:
                bot.send_message(
                    chat_id, 
                    "👋 *Welcome to CareerOps AI!*\n\nPlease upload your *Resume (as a PDF)* directly in this chat to begin automated matching."
                )
    except Exception as e:
        print(f"[Telegram Inbox] Update polling failed: {e}")

def run_match_pipeline(bot: TelegramSaaSClient, state: dict):
    users_root = Path("data/users")
    if not users_root.exists():
        print("[Pipeline] No user directory found.")
        return

    searcher = JobSearchEngine()
    matcher = MatchEngine()
    tailor = DocumentTailor()

    for user_dir in users_root.iterdir():
        if not user_dir.is_dir():
            continue
        chat_id = user_dir.name
        pdf_file = user_dir / "inputs" / "resume.pdf"
        if not pdf_file.exists():
            continue

        print(f"\n--- Processing Candidate {chat_id} ---")
        resume_text = extract_pdf_text(pdf_file)
        if not resume_text:
            continue

        profile = extract_user_profile(chat_id, resume_text)
        print(f"[Profile] Experience: {profile.get('total_years_experience')} yrs | Pivots: {profile.get('pivot_trajectories')}")
        
        jobs = searcher.fetch_jobs(profile)
        print(f"[Job Search] Found {len(jobs)} total jobs to evaluate across all queries.")

        matched_count = 0
        for idx, job in enumerate(jobs, 1):
            raw_id = job.get("job_id") or f"{job.get('title')}_{job.get('company_name')}"
            safe_id = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:16]

            title = job.get('title', 'Unknown Title')
            company = job.get('company_name', 'Unknown Company')

            if safe_id in state["seen_jobs"]:
                continue

            fit = matcher.evaluate_fit(profile, job.get("description", ""))
            score = fit.get("match_score", 0)
            viable = fit.get("is_viable", False)
            reason = fit.get("rejection_reason", "Score below threshold")

            print(f"[{idx}/{len(jobs)}] '{title}' at '{company}' -> Viable: {viable} | Score: {score}/100")

            if viable and score >= config.MIN_MATCH_SCORE:
                print(f"🎯 MATCH CONFIRMED ({score}%). Tailoring resume & cover letter...")
                assets = tailor.generate_assets(profile, job, fit)
                
                out_dir = user_dir / "outputs" / safe_id
                out_dir.mkdir(parents=True, exist_ok=True)
                
                resume_file = out_dir / "Tailored_Resume.md"
                cl_file = out_dir / "Cover_Letter.md"
                resume_file.write_text(assets.get("resume_md", ""), encoding="utf-8")
                cl_file.write_text(assets.get("cover_letter_md", ""), encoding="utf-8")

                bot.deliver_assets(
                    chat_id=chat_id,
                    job_title=title,
                    company=company,
                    resume_path=str(resume_file),
                    cl_path=str(cl_file)
                )
                print(f"📦 Delivered files to Telegram user {chat_id}")
                matched_count += 1
            else:
                if not viable:
                    print(f"   ↳ Disqualified: {reason}")

            state["seen_jobs"].append(safe_id)

        print(f"--- Finished Candidate {chat_id}: {matched_count} high-match jobs delivered ---\n")

if __name__ == "__main__":
    tg_bot = TelegramSaaSClient()
    pipeline_state = load_state()
    
    process_telegram_inbox(tg_bot, pipeline_state)
    run_match_pipeline(tg_bot, pipeline_state)
    
    save_state(pipeline_state)
