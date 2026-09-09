"""
Onboarding state machine.

A new user (or any user with a profile missing preference fields) gets
walked through a one-question-at-a-time conversation. We edit the same
Telegram message in place after each reply so the chat history stays
clean. State is per-chat_id, persisted in data/state.json so the
pipeline can resume the conversation across separate cron runs.
"""
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from src.profiler import missing_fields, REQUIRED_PREFERENCE_FIELDS
from src.github_sync import sync_profile_to_github


# Reference to the main pipeline's save_state function, injected on import
# by main.py to avoid a circular import.
_save_state_fn = None


def _load_onboarding(state: dict) -> dict:
    state.setdefault("onboarding", {})
    return state["onboarding"]


def _persist(state: dict) -> None:
    if _save_state_fn is not None:
        _save_state_fn(state)


def inject_save_fn(fn) -> None:
    global _save_state_fn
    _save_state_fn = fn


def _save_profile_field(chat_id: str, field: str, value) -> None:
    profile_path = Path(f"data/users/{chat_id}/profile.json")
    if profile_path.exists():
        try:
            data = json.loads(profile_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    else:
        data = {}
        profile_path.parent.mkdir(parents=True, exist_ok=True)
    data[field] = value
    profile_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# --------------------------------------------------------------------
# Stage transitions
# --------------------------------------------------------------------

def start_onboarding_if_needed(bot, state: dict, chat_id: str, profile: dict) -> bool:
    if not missing_fields(profile):
        return False
    ob = _load_onboarding(state)
    user_state = ob.get(chat_id, {})
    if user_state.get("stage") == "reviewing":
        return True
    if user_state.get("stage") == "asking":
        return True
    queue = list(missing_fields(profile))
    ob[chat_id] = {
        "stage": "asking",
        "queue": queue,
        "answers": {},
        "message_id": None,
        "editing_field": None,
        "last_seen_update": datetime.now(timezone.utc).isoformat(),
    }
    _persist(state)
    _ask_next(bot, state, chat_id)
    return True


def _ask_next(bot, state: dict, chat_id: str) -> None:
    ob = _load_onboarding(state)
    user_state = ob.get(chat_id, {})
    queue = user_state.get("queue", [])
    if not queue:
        _show_review(bot, state, chat_id)
        return
    field = queue[0]
    text = _render_question(field)
    if user_state.get("message_id"):
        bot.edit_message_text(chat_id, user_state["message_id"], text, reply_markup=None)
    else:
        msg_id = bot.send_message(chat_id, text)
        user_state["message_id"] = msg_id
    _persist(state)


def _show_review(bot, state: dict, chat_id: str) -> None:
    ob = _load_onboarding(state)
    user_state = ob[chat_id]
    profile = _load_full_profile(chat_id)
    text = _render_profile_review(profile)
    keyboard = bot.confirm_edit_keyboard()
    bot.edit_message_text(chat_id, user_state["message_id"], text, reply_markup=keyboard)
    user_state["stage"] = "reviewing"
    _persist(state)


# --------------------------------------------------------------------
# Reply routing
# --------------------------------------------------------------------

def handle_onboarding_reply(bot, state: dict, chat_id: str,
                              text: str, callback_data: str = None) -> bool:
    ob = _load_onboarding(state)
    user_state = ob.get(chat_id)
    if not user_state:
        return False
    if user_state.get("stage") == "done":
        return False

    if callback_data:
        return _handle_callback(bot, state, chat_id, callback_data)

    stage = user_state.get("stage")
    if stage == "asking":
        return _handle_answer(bot, state, chat_id, text)
    if stage == "reviewing":
        return True
    return False


def _handle_callback(bot, state: dict, chat_id: str, callback_data: str) -> bool:
    ob = _load_onboarding(state)
    user_state = ob[chat_id]

    if callback_data == "onb:confirm":
        user_state["stage"] = "done"
        bot.edit_message_text(
            chat_id, user_state["message_id"],
            "🎉 *Profile saved!* The engine will start matching you to "
            "real jobs on the next run. You'll get a Telegram message "
            "for every high-fit role.",
            reply_markup=None,
        )
        # Sync the onboarding state to GitHub so the web dashboard sees it immediately
        try:
            sync_profile_to_github(chat_id, _load_full_profile(chat_id))
        except Exception as e:
            print(f"[Onboarding] GitHub sync for profile after confirm failed: {e}")
        _persist(state)
        return True

    if callback_data == "onb:edit_menu":
        bot.edit_message_text(
            chat_id, user_state["message_id"],
            "Which field would you like to update?",
            reply_markup=bot.field_picker_keyboard(),
        )
        _persist(state)
        return True

    if callback_data == "onb:edit:back":
        _show_review(bot, state, chat_id)
        return True

    if callback_data.startswith("onb:edit:"):
        field = callback_data.split(":", 2)[2]
        if field not in REQUIRED_PREFERENCE_FIELDS:
            return True
        user_state["editing_field"] = field
        user_state["queue"] = [field] + [f for f in user_state.get("queue", []) if f != field]
        user_state["stage"] = "asking"
        _ask_next(bot, state, chat_id)
        _persist(state)
        return True

    return False


def _handle_answer(bot, state: dict, chat_id: str, text: str) -> bool:
    ob = _load_onboarding(state)
    user_state = ob[chat_id]
    field = user_state["queue"][0]

    value = _parse_answer(field, text)
    if value is None:
        msg_id = user_state["message_id"]
        bot.edit_message_text(
            chat_id, msg_id,
            f"{_render_question(field)}\n\n"
            f"_Couldn't understand that. Please try again with the format above._",
            reply_markup=None,
        )
        return True

    _save_profile_field(chat_id, field, value)
    # Sync the updated profile to GitHub so the web dashboard sees it immediately
    try:
        profile = _load_full_profile(chat_id)
        sync_profile_to_github(chat_id, profile)
    except Exception as e:
        print(f"[Onboarding] GitHub sync for profile failed: {e}")

    user_state["answers"][field] = value
    user_state["queue"].pop(0)

    if not user_state["queue"]:
        _show_review(bot, state, chat_id)
    else:
        next_field = user_state["queue"][0]
        prev_label = _field_label(field)
        text = (
            f"✅ *Got it — {prev_label} updated.*\n\n"
            f"{_render_question(next_field)}"
        )
        bot.edit_message_text(chat_id, user_state["message_id"], text, reply_markup=None)
    _persist(state)
    return True


# --------------------------------------------------------------------
# Question rendering & answer parsing
# --------------------------------------------------------------------

_FIELD_LABELS = {
    "preferred_locations": "Preferred Locations",
    "target_roles": "Target Roles",
    "anti_targets": "Blocklisted Roles",
    "salary_expectation": "Salary Expectation",
    "open_to_internship": "Open to Internship",
}


def _field_label(field: str) -> str:
    return _FIELD_LABELS.get(field, field)


def _render_question(field: str) -> str:
    if field == "preferred_locations":
        return (
            "📍 *Where are you open to working?*\n\n"
            "Reply with cities or regions, comma-separated.\n"
            "Examples:\n"
            "  • `Delhi NCR, Remote, Bangalore`\n"
            "  • `San Francisco, Remote`\n"
            "  • `London`"
        )
    if field == "target_roles":
        return (
            "💼 *What role(s) are you targeting?*\n\n"
            "Reply with role titles, comma-separated.\n"
            "Examples:\n"
            "  • `Data Analyst, Business Analyst, Power BI Developer`\n"
            "  • `Product Manager`\n"
            "  • `Senior Software Engineer`"
        )
    if field == "anti_targets":
        return (
            "🚫 *Are there any role types or seniority levels you want to avoid?*\n\n"
            "Reply with keywords to exclude, comma-separated.\n"
            "Examples:\n"
            "  • `Director, VP, Head of`\n"
            "  • `Intern, Junior`\n"
            "  • `Sales`\n\n"
            "Reply `none` if you want everything."
        )
    if field == "salary_expectation":
        return (
            "💰 *What salary are you targeting?*\n\n"
            "Reply with a number in your local currency.\n"
            "Examples:\n"
            "  • `16 LPA`\n"
            "  • `15-20 LPA`\n"
            "  • `$120,000`\n\n"
            "Reply `skip` to leave this unset for now."
        )
    if field == "open_to_internship":
        return (
            "🎓 *Are you open to internship roles?*\n\n"
            "Reply `yes` or `no`."
        )
    return f"Please provide: {field}"


def _parse_answer(field: str, text: str):
    cleaned = text.strip()
    if not cleaned:
        return None
    if field == "preferred_locations":
        locs = [s.strip() for s in cleaned.split(",") if s.strip()]
        return locs if locs else None
    if field == "target_roles":
        roles = [s.strip() for s in cleaned.split(",") if s.strip()]
        return roles if roles else None
    if field == "anti_targets":
        if cleaned.lower() in ("none", "no", "n/a", "skip"):
            return []
        items = [s.strip() for s in cleaned.split(",") if s.strip()]
        return items
    if field == "salary_expectation":
        if cleaned.lower() in ("skip", "none", "n/a"):
            return None
        m = re.search(
            r"(\d+(?:\.\d+)?)\s*[-–to]+\s*(\d+(?:\.\d+)?)\s*(lpa|lakhs?)?",
            cleaned, re.IGNORECASE,
        )
        if m:
            lo, hi = float(m.group(1)), float(m.group(2))
            return {"min_lpa": min(lo, hi), "max_lpa": max(lo, hi)}
        m = re.search(r"(\d+(?:\.\d+)?)\s*(lpa|lakhs?)?", cleaned, re.IGNORECASE)
        if m:
            v = float(m.group(1))
            return {"min_lpa": v, "max_lpa": v}
        return None
    if field == "open_to_internship":
        if cleaned.lower() in ("yes", "y", "true", "1", "sure", "open to it"):
            return True
        if cleaned.lower() in ("no", "n", "false", "0", "nope"):
            return False
        return None
    return None


# --------------------------------------------------------------------
# Profile review
# --------------------------------------------------------------------

def _load_full_profile(chat_id: str) -> dict:
    profile_path = Path(f"data/users/{chat_id}/profile.json")
    if profile_path.exists():
        try:
            return json.loads(profile_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _render_profile_review(profile: dict) -> str:
    lines = ["📋 *Here's your profile — please review:*", ""]
    lines.append(f"*Name:* {profile.get('full_name', '—')}")
    lines.append(f"*Experience:* {profile.get('total_years_experience', '—')} years")
    lines.append(f"*Seniority:* {profile.get('seniority_tier', '—')}")
    contact = profile.get("contact", {}) or {}
    if contact.get("location"):
        lines.append(f"*Based in:* {contact['location']}")
    if profile.get("skills"):
        lines.append(
            f"*Skills:* {', '.join(profile['skills'][:8])}"
            f"{' …' if len(profile['skills']) > 8 else ''}"
        )
    lines.append("")
    if profile.get("preferred_locations"):
        lines.append(f"📍 *Locations:* {', '.join(profile['preferred_locations'])}")
    if profile.get("target_roles"):
        lines.append(f"💼 *Target Roles:* {', '.join(profile['target_roles'])}")
    if profile.get("anti_targets"):
        lines.append(f"🚫 *Avoiding:* {', '.join(profile['anti_targets'])}")
    else:
        lines.append("🚫 *Avoiding:* (none)")
    se = profile.get("salary_expectation")
    if isinstance(se, dict):
        lines.append(
            f"💰 *Salary:* ₹{se.get('min_lpa', '?')} – ₹{se.get('max_lpa', '?')} LPA"
        )
    elif se:
        lines.append(f"💰 *Salary:* {se} LPA")
    else:
        lines.append("💰 *Salary:* not set")
    lines.append(
        f"🎓 *Open to internships:* {'Yes' if profile.get('open_to_internship') else 'No'}"
    )
    lines.append("")
    lines.append("Tap *Confirm* if everything looks right, or *Edit* to update a field.")
    return "\n".join(lines)
