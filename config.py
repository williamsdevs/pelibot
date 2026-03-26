import os
from dotenv import load_dotenv

load_dotenv()


def _required(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise ValueError(f"Missing required environment variable: {key}")
    return value


TELEGRAM_BOT_TOKEN = _required("TELEGRAM_BOT_TOKEN")

_raw_ids = os.getenv("ALLOWED_USER_IDS", "")
ALLOWED_USER_IDS: set[int] = (
    {int(uid.strip()) for uid in _raw_ids.split(",") if uid.strip()}
    if _raw_ids.strip()
    else set()
)

QB_HOST = os.getenv("QB_HOST", "http://localhost")
QB_PORT = int(os.getenv("QB_PORT", "8080"))
QB_USERNAME = os.getenv("QB_USERNAME", "admin")
QB_PASSWORD = os.getenv("QB_PASSWORD", "adminadmin")
QB_DOWNLOAD_PATH = os.getenv("QB_DOWNLOAD_PATH", "/downloads")

JACKETT_URL = os.getenv("JACKETT_URL", "http://localhost:9117")
JACKETT_API_KEY = os.getenv("JACKETT_API_KEY", "")

TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")

STORAGE_CHANNEL_ID = int(os.getenv("STORAGE_CHANNEL_ID", "0"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

_raw_admins = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: set[int] = (
    {int(uid.strip()) for uid in _raw_admins.split(",") if uid.strip()}
    if _raw_admins.strip() else set()
)

FREE_DOWNLOADS_PER_MONTH = int(os.getenv("FREE_DOWNLOADS_PER_MONTH", "5"))
PREMIUM_PRICE_STARS = int(os.getenv("PREMIUM_PRICE_STARS", "100"))

# Torrent categories (Jackett/Newznab)
CATEGORY_MOVIES = "2000"
CATEGORY_SERIES = "5000"

MAX_SEARCH_RESULTS = 10
