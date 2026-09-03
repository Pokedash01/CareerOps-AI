import requests
import src.config as config

class TelegramSaaSClient:
    def __init__(self):
        self.base_url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"

    def send_message(self, chat_id: str, text: str):
        requests.post(
            f"{self.base_url}/sendMessage", 
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        )

    def deliver_assets(self, chat_id: str, job_title: str, company: str, resume_path: str, cl_path: str):
        caption = f"🎯 *High Match Found!*\n\n*Role:* {job_title}\n*Company:* {company}\n\nAttached are your ATS-tailored documents."
        with open(resume_path, "rb") as doc:
            requests.post(
                f"{self.base_url}/sendDocument", 
                data={"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"}, 
                files={"document": doc}
            )
        with open(cl_path, "rb") as doc:
            requests.post(
                f"{self.base_url}/sendDocument", 
                data={"chat_id": chat_id}, 
                files={"document": doc}
            )
