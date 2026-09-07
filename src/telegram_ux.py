"""
Telegram UX helpers.

The bot is read-only from the user's perspective: it sends messages and
PDFs, and edits one in-flight onboarding message. All edits go through
Telegram's editMessageText API so the conversation history stays clean
(no back-to-back "Question 1" / "Question 2" messages).
"""
import json
import requests
import src.config as config


class TelegramSaaSClient:
    def __init__(self):
        self.base_url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"

    def _post(self, method: str, payload: dict, timeout: int = 10):
        return requests.post(
            f"{self.base_url}/{method}",
            json=payload,
            timeout=timeout,
        )

    def send_message(self, chat_id: str, text: str) -> int:
        """Send a plain Markdown message. Returns the message_id (for later
        edits) or 0 on failure."""
        res = self._post("sendMessage", {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        })
        if res.status_code == 200:
            try:
                return int(res.json().get("result", {}).get("message_id", 0))
            except Exception:
                return 0
        return 0

    def edit_message_text(self, chat_id: str, message_id: int, text: str,
                          reply_markup: dict = None) -> bool:
        """Edit a message in place. Returns True on success.
        Used by the onboarding flow to render the next question in the
        same message the user is already looking at."""
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        if reply_markup is not None:
            payload["reply_markup"] = json.dumps(reply_markup)
        res = self._post("editMessageText", payload)
        return res.status_code == 200

    def answer_callback(self, callback_query_id: str) -> None:
        """Acknowledge a button press so the loading state on the user's
        client goes away. Telegram shows a spinner until this is called."""
        self._post("answerCallbackQuery", {"callback_query_id": callback_query_id})

    def send_html(self, chat_id: str, html: str, disable_preview: bool = True) -> int:
        """Send an HTML-formatted message (used for the new-match notification
        card with bold + inline links)."""
        res = self._post("sendMessage", {
            "chat_id": chat_id,
            "text": html,
            "parse_mode": "HTML",
            "disable_web_page_preview": disable_preview,
        })
        if res.status_code == 200:
            try:
                return int(res.json().get("result", {}).get("message_id", 0))
            except Exception:
                return 0
        return 0

    def deliver_assets(self, chat_id: str, job_title: str, company: str,
                       resume_path: str, cl_path: str):
        """Send resume + cover letter as Telegram document attachments."""
        caption = (
            f"🎯 *High Match Found!*\n\n"
            f"*Role:* {job_title}\n*Company:* {company}\n\n"
            f"Attached are your ATS-tailored documents."
        )
        with open(resume_path, "rb") as doc:
            requests.post(
                f"{self.base_url}/sendDocument",
                data={"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"},
                files={"document": doc},
                timeout=30,
            )
        with open(cl_path, "rb") as doc:
            requests.post(
                f"{self.base_url}/sendDocument",
                data={"chat_id": chat_id},
                files={"document": doc},
                timeout=30,
            )

    # -----------------------------------------------------------------
    # Inline keyboard builders (for onboarding confirmation / field pick)
    # -----------------------------------------------------------------

    @staticmethod
    def confirm_edit_keyboard() -> dict:
        return {
            "inline_keyboard": [[
                {"text": "✅ Confirm", "callback_data": "onb:confirm"},
                {"text": "✏️ Edit", "callback_data": "onb:edit_menu"},
            ]],
        }

    @staticmethod
    def field_picker_keyboard() -> dict:
        return {
            "inline_keyboard": [
                [{"text": "📍 Locations", "callback_data": "onb:edit:preferred_locations"}],
                [{"text": "💼 Target roles", "callback_data": "onb:edit:target_roles"}],
                [{"text": "🚫 Roles to avoid", "callback_data": "onb:edit:anti_targets"}],
                [{"text": "💰 Salary", "callback_data": "onb:edit:salary_expectation"}],
                [{"text": "🎓 Internships", "callback_data": "onb:edit:open_to_internship"}],
                [{"text": "↩️ Back to review", "callback_data": "onb:edit:back"}],
            ],
        }
