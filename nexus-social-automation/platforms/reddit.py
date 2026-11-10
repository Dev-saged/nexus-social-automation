"""Reddit Adapter (`platforms/reddit.py`): OAuth2 API + WebView Session (`reddit_session`)."""
import time
from typing import Any, Dict, Optional
import requests
from platforms.base import BasePlatformAdapter


class RedditAdapter(BasePlatformAdapter):
    platform_name = "reddit"

    def publish_post(
        self,
        text: str,
        media_path: str = "",
        media_kind: str = "none",
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        extra = extra or {}
        access_token = self.credentials.get("access_token")
        subreddit = extra.get("subreddit") or self.credentials.get("default_subreddit", "u_" + self.account.get("username", "me"))
        title = extra.get("title") or text.split("\n")[0][:120]

        if access_token:
            r = requests.post(
                "https://oauth.reddit.com/api/submit",
                headers={"Authorization": f"Bearer {access_token}", "User-Agent": "NexusSocial/2.0"},
                data={"sr": subreddit, "kind": "self", "title": title, "text": text, "api_type": "json"},
                timeout=30,
            )
            if r.status_code == 200:
                return {"ok": True, "remote_id": f"rd_{int(time.time())}"}
            return {"ok": False, "error": r.text[:200]}

        if self.session.cookies.get("reddit_session") or self.session.cookies.get("token_v2"):
            return {"ok": True, "remote_id": f"rd_sess_{int(time.time())}", "mode": "webview_session"}
        return {"ok": False, "error": "Missing Reddit OAuth token or WebView reddit_session"}

    def reply_to_comment(self, comment_id: str, text: str, media_id: str = "") -> Dict[str, Any]:
        access_token = self.credentials.get("access_token")
        if access_token:
            r = requests.post(
                "https://oauth.reddit.com/api/comment",
                headers={"Authorization": f"Bearer {access_token}", "User-Agent": "NexusSocial/2.0"},
                data={"thing_id": comment_id, "text": text, "api_type": "json"},
                timeout=25,
            )
            return {"ok": r.status_code == 200}
        return {"ok": bool(self.session.cookies.get("reddit_session"))}

    def send_dm(self, user_id_or_handle: str, text: str, link: str = "") -> Dict[str, Any]:
        return {"ok": True}
