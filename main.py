"""
CareerOps pipeline entry point.

Runs as a GitHub Action every 4 hours. Two phases:
1. process_telegram_inbox() — pull new updates, route to onboarding
   handler or resume-upload handler.
2. run_match_pipeline() — for every user with a resume, parse the
   profile, run onboarding if preferences are missing, and (only when
   onboarding is complete) search and match jobs.
"""
import os
import json
import hashlib
import requests
from pathlib import Path
from datetime import datetime, timedelta, timezone
from pypdf import PdfReader

from src.telegram_ux import TelegramSaaSClient
from src.profiler import extract_user_profile, profile_is_complete
from src.job_search import JobSearchEngine
from src.matcher import MatchEngine
from src.tailor import DocumentTailor
from src.onboarding import (
    start_onboarding_if_needed,
    handle_onboarding_reply,
    inject_save_fn,
)
import src.config as config

STATE_FILE = Path("data/state.json")
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "Pokedash01/CareerOps-AI")

SEEN_JOB_TTL_DAYS = getattr(config, "SEEN_JOB_TTL_DAYS", 14)


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    else:
        state = {}

    state.setdefault("telegram_offset", None)

    seen = state.get("seen_jobs", [])
    if isinstance(seen, list):
        now_iso = datetime.now(timezone.utc).isoformat()
        seen = {job_id: now_iso for job_id in seen}
    state["seen_jobs"] = seen

    state.setdefault("notified_jobs", [])
    state.setdefault("onboarding", {})
    return state


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def is_recently_seen(state: dict, safe_id: str) -> bool:
    last_seen = state["seen_jobs"].get(safe_id)
    if not last_seen:
        return False
    try:
        last_seen_dt = datetime.fromisoformat(last_seen)
    except Exception:
        return False
    return datetime.now(timezone.utc) - last_seen_dt < timedelta(days=SEEN_JOB_TTL_DAYS)


def mark_seen(state: dict, safe_id: str):
    state["seen_jobs"][safe_id] = datetime.now(timezone.utc).isoformat()


def github_raw_link(local_path: Path) -> str:
    clean = str(local_path).replace(os.sep, "/").lstrip("./")
    return f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{clean}"


def extract_pdf_text(pdf_path: Path) -> str:
    try:
        reader = PdfReader(pdf_path)
        return "\n".join([page.extract_text() or "" for page in reader.pages]).strip()
    except Exception:
        return ""


def _append_job_index(user_dir: Path, safe_id: str, job: dict, fit: dict):
    """Append (or update) one entry in the per-user jobs.json index.
    The web dashboard reads this file to show the matched-jobs list —
    it avoids hitting the GitHub Contents API."""
    idx_path = user_dir / "jobs.json"
    try:
        jobs = []
        if idx_path.exists():
            jobs = json.loads(idx_path.read_text(encoding="utf-8"))
    except Exception:
        jobs = []

    entry = {
        "job_id": safe_id,
        "title": job.get("title", "Role"),
        "company_name": job.get("company_name", "Enterprise"),
        "description": job.get("description", "")[:500],
        "apply_link": job.get("apply_link", ""),
        "location": job.get("location", "Not specified"),
        "salary_range_lpa": job.get("salary_range_lpa"),
        "experience_range_years": job.get("experience_range_years"),
        "fit_score": fit.get("match_score", 0),
        "is_viable": fit.get("is_viable", False),
        "rejection_reason": fit.get("rejection_reason"),
        "detected_experience": fit.get("detected_experience"),
        "salary_range": fit.get("salary_range"),
        "skills_gap": fit.get("skills_gap"),
        "ats_report": fit.get("ats_report"),
        "notified": True,
        "seen": True,
        "notified_at": datetime.now(timezone.utc).isoformat(),
    }
    replaced = False
    for i, e in enumerate(jobs):
        if e.get("job_id") == safe_id:
            jobs[i] = entry
            replaced = True
            break
    if not replaced:
        jobs.append(entry)

    idx_path.write_text(json.dumps(jobs, indent=2), encoding="utf-8")


def process_telegram_inbox(bot: TelegramSaaSClient, state: dict):
    """Pull new updates from Telegram, route them to either the resume
    handler, the onboarding handler, or ignore them."""
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {"timeout": 10, "offset": state.get("telegram_offset")}
    try:
        res = requests.get(url, params=params, timeout=15).json()
        for item in res.get("result", []):
            state["telegram_offset"] = item["update_id"] + 1

            chat_id = str(
                (item.get("message") or item.get("callback_query") or {})
                .get("chat", {}).get("id")
                or (item.get("callback_query") or {}).get("from", {}).get("id")
            )

            # 1. Callback query (button press) — drive the onboarding flow.
            cb = item.get("callback_query")
            if cb:
                bot.answer_callback(cb.get("id", ""))
                handle_onboarding_reply(
                    bot, state, chat_id,
                    text=None, callback_data=cb.get("data", ""),
                )
                continue

            msg = item.get("message", {})

            # 2. PDF upload — start (or restart) the resume pipeline.
            if "document" in msg:
                doc = msg["document"]
                if doc.get("file_name", "").lower().endswith(".pdf"):
                    f_info = requests.get(
                        f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getFile?file_id={doc['file_id']}",
                        timeout=15,
                    ).json()
                    file_path = f_info["result"]["file_path"]
                    content = requests.get(
                        f"https://api.telegram.org/file/bot{config.TELEGRAM_BOT_TOKEN}/{file_path}",
                        timeout=30,
                    ).content

                    user_dir = Path(f"data/users/{chat_id}/inputs")
                    user_dir.mkdir(parents=True, exist_ok=True)
                    (user_dir / "resume.pdf").write_bytes(content)

                    # Invalidate the cached profile so a new PDF triggers
                    # a fresh LLM parse. Also reset onboarding.
                    cached_profile = Path(f"data/users/{chat_id}/profile.json")
                    if cached_profile.exists():
                        cached_profile.unlink()
                    state.get("onboarding", {}).pop(chat_id, None)

                    bot.send_message(
                        chat_id,
                        "✅ Resume received. Parsing now — I'll message you "
                        "with the next steps shortly.",
                    )
                continue

            # 3. Plain text — could be an onboarding reply.
            text = msg.get("text", "")
            if text:
                if handle_onboarding_reply(bot, state, chat_id, text=text):
                    continue
    except Exception as e:
        print(f"[Telegram Inbox] Error: {e}")


def run_match_pipeline(bot: TelegramSaaSClient, state: dict):
    """For each user with a resume, parse the profile, run onboarding if
    preference fields are missing, and (only when onboarding is complete)
    search and match jobs."""
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

        ob = state.get("onboarding", {})
        in_onboarding = bool(ob.get(chat_id))
        if in_onboarding or not profile_is_complete(profile):
            started = start_onboarding_if_needed(bot, state, chat_id, profile)
            if started:
                cand_name = profile.get("full_name", "Candidate")
                print(f"[Pipeline] {cand_name} ({chat_id}) is in onboarding — skipping matching this run.")
                continue

        cand_name = profile.get("full_name", "Candidate")
        first_name = cand_name.split()[0]

        jobs = searcher.fetch_jobs(profile)
        print(f"[Pipeline] Evaluating {len(jobs)} candidate listings for {cand_name}...")

        skipped_recent = 0
        for idx, job in enumerate(jobs, 1):
            raw_id = job.get("job_id") or job.get("apply_link")
            safe_id = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:16]

            if is_recently_seen(state, safe_id):
                skipped_recent += 1
                continue

            title = job.get("title", "Role")
            company = job.get("company_name", "Enterprise")
            desc = job.get("description", "")

            fit = matcher.evaluate_fit(
                profile, title, desc,
                location=job.get("location", "Not specified"),
                salary_range_lpa=job.get("salary_range_lpa"),
                experience_range_years=job.get("experience_range_years"),
            )
            score = fit.get("match_score", 0)
            viable = fit.get("is_viable", False)
            reason = fit.get("rejection_reason")

            status_line = f"[{idx}/{len(jobs)}] '{title}' @ '{company}' -> Viable: {viable} | Score: {score}%"
            if reason:
                status_line += f" | Filtered: {reason}"
            print(status_line)

            already_notified = safe_id in state["notified_jobs"]

            if viable and score >= config.MIN_MATCH_SCORE and not already_notified:
                try:
                    tailored = tailor.generate_tailored_content(profile, title, company, desc)
                except Exception as e:
                    print(f"[Tailor] Failed to generate tailored content for '{title}' @ '{company}': {e}")
                    mark_seen(state, safe_id)
                    continue

                out_dir = user_dir / "outputs" / safe_id
                out_dir.mkdir(parents=True, exist_ok=True)

                pdf_resume = out_dir / f"Resume_{company}_{safe_id}.pdf"
                pdf_cl = out_dir / f"CoverLetter_{company}_{safe_id}.pdf"

                tailor.build_pdf_resume(str(pdf_resume), profile, tailored=tailored)
                tailor.build_pdf_cover_letter(str(pdf_cl), title, company, profile, tailored)

                # Update the per-user jobs.json index that the dashboard reads
                _append_job_index(user_dir, safe_id, job, fit)

                resume_url = github_raw_link(pdf_resume)
                cl_url = github_raw_link(pdf_cl)
                exp_req = fit.get("detected_experience", "Not specified in JD")
                sal_range = fit.get("salary_range", "Not specified in JD")
                gaps = fit.get("skills_gap", "None")

                msg = (
                    f"🎯 <b>New High-Fit Role Matched for {first_name}!</b>\n\n"
                    f"📌 <b>Role:</b> {title}\n"
                    f"🏢 <b>Company:</b> {company}\n"
                    f"📍 <b>Location:</b> {job.get('location', 'Not specified')}\n"
                    f"⏳ <b>Experience Required:</b> {exp_req}\n"
                    f"💰 <b>Salary Range:</b> {sal_range}\n"
                    f"📊 <b>Fit Score:</b> {score}%\n"
                    f"⚠️ <b>Skill Gap:</b> {gaps}\n\n"
                    f"🔗 <a href='{job.get('apply_link')}'><b>Apply Directly on Portal</b></a>\n"
                    f"📄 <a href='{resume_url}'><b>Download Resume PDF</b></a>\n"
                    f"📝 <a href='{cl_url}'><b>Download Cover Letter PDF</b></a>\n\n"
                    f"<i>Links go live within ~1 min once pushed to repo.</i>"
                )

                bot.send_html(chat_id, msg, disable_preview=True)
                state["notified_jobs"].append(safe_id)

            mark_seen(state, safe_id)

        if skipped_recent:
            print(f"[Pipeline] Skipped {skipped_recent} listing(s) evaluated within the last {SEEN_JOB_TTL_DAYS} days.")


if __name__ == "__main__":
    tg_bot = TelegramSaaSClient()
    pipeline_state = load_state()
    inject_save_fn(save_state)
    process_telegram_inbox(tg_bot, pipeline_state)
    run_match_pipeline(tg_bot, pipeline_state)
    save_state(pipeline_state)
