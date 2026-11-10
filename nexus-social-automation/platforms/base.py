"""
Unified Base Platform Adapter (`platforms/base.py`) supporting both
Official OAuth/Graph Tokens AND One-Tap WebView Session Cookies captured from the Android APK.
"""
from typing import Any, Dict, List, Optional
import requests


class BasePlatformAdapter:
    platform_name: str = "base"

    def __init__(self, credentials: Dict[str, Any], account_row: Optional[Dict[str, Any]] = None):
        self.credentials = credentials or {}
        self.account = account_row or {}
        self.session = requests.Session()
        # Apply captured cookies if linked via Android APK WebView Bridge
        raw_cookies = self.credentials.get("cookie_string", "")
        if raw_cookies:
            for pair in raw_cookies.split(";"):
                if "=" in pair:
                    k, v = pair.strip().split("=", 1)
                    self.session.cookies.set(k.strip(), v.strip())
        ua = self.credentials.get(
            "user_agent",
            "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36",
        )
        self.session.headers.update({"User-Agent": ua})

    def publish_post(
        self,
        text: str,
        media_path: str = "",
        media_kind: str = "none",
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    def reply_to_comment(self, comment_id: str, text: str, media_id: str = "") -> Dict[str, Any]:
        raise NotImplementedError

    def send_dm(self, user_id_or_handle: str, text: str, link: str = "") -> Dict[str, Any]:
        raise NotImplementedError

    def fetch_recent_interactions(self, since_cursor: str = "") -> List[Dict[str, Any]]:
        """Polls new comments and DMs for Offline Catch-Up Sync."""
        return []
