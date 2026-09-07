"""Engine configuration. Read environment vars once at import time."""
import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

MIN_MATCH_SCORE = 75

# How long a job "counts" as recently-seen before the pipeline will
# re-evaluate it.
SEEN_JOB_TTL_DAYS = int(os.getenv("SEEN_JOB_TTL_DAYS", "14"))

# Set to "1" to dump every search query + result count to the pipeline
# log. Useful for debugging why a particular role isn't surfacing.
DEBUG_SEARCH = os.getenv("DEBUG_SEARCH", "").strip().lower() in ("1", "true", "yes")
