"""
Central Configuration for Nexus Social Automation (Termux + Android APK).
Works with zero external dependencies (built-in .env loader) or python-dotenv.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_env_file():
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    _load_env_file()

DATA_DIR = Path(os.getenv("NEXUS_DATA_DIR", str(Path.home() / ".nexus_social")))
DATA_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR = DATA_DIR / "media_vault"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
SESSIONS_DIR = DATA_DIR / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "nexus_social.db"
SECRET_KEY_PATH = DATA_DIR / "secret.key"

HOST = os.getenv("NEXUS_HOST", "127.0.0.1")
PORT = int(os.getenv("NEXUS_PORT", "5050"))
TIMEZONE = os.getenv("NEXUS_TIMEZONE", "Asia/Gaza")

DEFAULT_OPERATION_MODE = os.getenv("DEFAULT_OPERATION_MODE", "SMART_HYBRID")

SUPPORTED_PLATFORMS = [
    "instagram",
    "facebook",
    "threads",
    "x_twitter",
    "linkedin",
    "tiktok",
    "youtube",
    "telegram",
    "bluesky",
    "reddit",
    "pinterest",
    "mastodon",
]

PLATFORM_LOGIN_URLS = {
    "instagram": "https://www.instagram.com/accounts/login/",
    "facebook": "https://m.facebook.com/login/",
    "threads": "https://www.threads.net/login",
    "x_twitter": "https://x.com/i/flow/login",
    "linkedin": "https://www.linkedin.com/login",
    "tiktok": "https://www.tiktok.com/login",
    "youtube": "https://studio.youtube.com/",
    "telegram": "https://web.telegram.org/k/",
    "bluesky": "https://bsky.app/",
    "reddit": "https://www.reddit.com/login/",
    "pinterest": "https://www.pinterest.com/login/",
    "mastodon": "https://mastodon.social/auth/sign_in",
}

SCHEDULER_CONFIG = {
    "active_window_start": "08:00",
    "active_window_end": "23:00",
    "jitter_minutes": 15,
    "default_video_slots": ["09:00", "14:00", "18:30"],
    "default_post_slots": ["10:00", "15:00", "20:00"],
    "max_daily_videos_per_account": 2,
    "max_daily_posts_per_account": 4,
    "catchup_min_delay_sec": 35,
    "catchup_max_delay_sec": 90,
    "retry_backoff_seconds": [60, 300, 900, 3600, 10800],
}

RATE_LIMITS_PER_HOUR = {
    "publish": 5,
    "comment_reply": 25,
    "dm_send": 20,
    "target_engage": 12,
}
