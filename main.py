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
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "Pokedash01/CareerOps-AI")

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

def github_raw_link(local_path: Path) -> str:
    clean = str(local_path).replace(os.sep, "/").lstrip("./")
    return f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{clean}"

def extract_pdf_text(pdf_path: Path) -> str:
    try:
        reader = PdfReader(pdf_path)
        return "\n".join([page.extract_text() or "" for page in reader.pages]).strip()
    except Exception:
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
                    
                    # Wipe profile cache so new PDF forces full re-extraction
                    cached = Path(f"data/users/{chat_id}/profile.json")
                    if cached.exists():
                        cached.unlink()
                        
                    bot.send_message(chat_id, "✅ Resume received. Matching roles against your experience.")
    except Exception as e:
        print(f"[Telegram Inbox] Error: {e}")

def run_match_pipeline(bot: TelegramSaaSClient, state: dict):
    users_root = Path("data/users")
    if not users_root.exists():
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

        resume_text = extract_pdf_text(pdf_file)
        if not resume_text:
            continue

        profile = extract_user_profile(chat_id, resume_text)
        cand_name = profile.get("full_name", "Candidate")
        first_name = cand_name.split()[0]

        jobs = searcher.fetch_jobs(profile)
        print(f"[Pipeline] Evaluating {len(jobs)} candidate listings for {cand_name}...")

        for idx, job in enumerate(jobs, 1):
            raw_id = job.get("job_id") or job.get("apply_link")
            safe_id = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:16]

            if safe_id in state["seen_jobs"]:
                continue

            title = job.get("title", "Role")
            company = job.get("company_name", "Enterprise")
            desc = job.get("description", "")

            fit = matcher.evaluate_fit(profile, title, desc)
            score = fit.get("match_score", 0)
            viable = fit.get("is_viable", False)

            print(f"[{idx}/{len(jobs)}] '{title}' @ '{company}' -> Viable: {viable} | Score: {score}%")

            if viable and score >= config.MIN_MATCH_SCORE:
                bullets = tailor.generate_adapted_bullets(profile, title, company, desc)
                out_dir = user_dir / "outputs" / safe_id
                out_dir.mkdir(parents=True, exist_ok=True)

                pdf_resume = out_dir / f"Resume_{company}_{safe_id}.pdf"
                pdf_cl = out_dir / f"CoverLetter_{company}_{safe_id}.pdf"

                tailor.build_pdf_resume(str(pdf_resume), profile)
                tailor.build_pdf_cover_letter(str(pdf_cl), title, company, profile, bullets)

                resume_url = github_raw_link(pdf_resume)
                cl_url = github_raw_link(pdf_cl)
                exp_req = fit.get("detected_experience", "2–5 Years / Unspecified")
                sal_range = fit.get("salary_range", "₹12 - ₹18 LPA (Est.)")
                gaps = fit.get("skills_gap", "None")

                # Exact single-message card matching target template
                msg = (
                    f"🎯 <b>New High-Fit Role Matched for {first_name}! (V2) </b>\n\n"
                    f"📌 <b>Role:</b> {title}\n"
                    f"🏢 <b>Company:</b> {company}\n"
                    f"📍 <b>Location:</b> {job.get('location', 'Remote')}\n"
                    f"⏳ <b>Experience Required:</b> {exp_req}\n"
                    f"💰 <b>Salary Range:</b> {sal_range}\n"
                    f"📊 <b>Fit Score:</b> {score}%\n"
                    f"⚠️ <b>Skill Gap:</b> {gaps}\n\n"
                    f"🔗 <a href='{job.get('apply_link')}'><b>Apply Directly on Portal</b></a>\n"
                    f"📄 <a href='{resume_url}'><b>Download Resume PDF</b></a>\n"
                    f"📝 <a href='{cl_url}'><b>Download Cover Letter PDF</b></a>\n\n"
                    f"<i>Links go live within ~1 min once pushed to repo.</i>"
                )

                # Send ONLY ONE message with link preview disabled
                requests.post(
                    f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": msg,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True
                    },
                    timeout=10
                )

            state["seen_jobs"].append(safe_id)

if __name__ == "__main__":
    tg_bot = TelegramSaaSClient()
    pipeline_state = load_state()
    process_telegram_inbox(tg_bot, pipeline_state)
    run_match_pipeline(tg_bot, pipeline_state)
    save_state(pipeline_state)
