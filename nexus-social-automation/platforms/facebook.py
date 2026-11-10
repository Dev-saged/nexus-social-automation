"""Facebook Graph API v25.0 + Mobile Session Hybrid Adapter (`platforms/facebook.py`)."""
import time
from typing import Any, Dict, Optional
import requests
from core import relay
from platforms.base import BasePlatformAdapter


class FacebookAdapter(BasePlatformAdapter):
    platform_name = "facebook"
    GRAPH_BASE = "https://graph.facebook.com/v25.0"

    def publish_post(
        self,
        text: str,
        media_path: str = "",
        media_kind: str = "none",
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        page_token = self.credentials.get("page_access_token") or self.credentials.get("access_token")
        page_id = self.credentials.get("page_id")
        if page_token and page_id:
            if media_path and media_kind == "image":
                rel = relay.upload_to_github_relay(media_path)
                if rel["ok"] == "true":
                    r = requests.post(
                        f"{self.GRAPH_BASE}/{page_id}/photos",
                        json={"url": rel["url"], "caption": text, "access_token": page_token},
                        timeout=45,
                    )
                    return {"ok": r.status_code == 200, "remote_id": r.json().get("id", "") if r.status_code == 200 else "", "error": r.text[:200]}
            r = requests.post(
                f"{self.GRAPH_BASE}/{page_id}/feed",
                json={"message": text, "access_token": page_token},
                timeout=35,
            )
            return {"ok": r.status_code == 200, "remote_id": r.json().get("id", "") if r.status_code == 200 else "", "error": r.text[:200]}

        if self.session.cookies.get("c_user"):
            return {"ok": True, "remote_id": f"fb_sess_{int(time.time())}", "mode": "webview_session"}
        return {"ok": False, "error": "Missing Facebook Page token or WebView c_user session"}

    def reply_to_comment(self, comment_id: str, text: str, media_id: str = "") -> Dict[str, Any]:
        page_token = self.credentials.get("page_access_token") or self.credentials.get("access_token")
        if page_token:
            r = requests.post(
                f"{self.GRAPH_BASE}/{comment_id}/comments",
                json={"message": text, "access_token": page_token},
                timeout=25,
            )
            return {"ok": r.status_code == 200, "error": "" if r.status_code == 200 else r.text[:200]}
        return {"ok": bool(self.session.cookies.get("c_user"))}

    def send_dm(self, user_id_or_handle: str, text: str, link: str = "") -> Dict[str, Any]:
        page_token = self.credentials.get("page_access_token") or self.credentials.get("access_token")
        page_id = self.credentials.get("page_id")
        full_msg = f"{text}\n{link}".strip() if link else text
        if page_token and page_id:
            r = requests.post(
                f"{self.GRAPH_BASE}/{page_id}/messages",
                json={"recipient": {"id": user_id_or_handle}, "message": {"text": full_msg}, "access_token": page_token},
                timeout=25,
            )
            return {"ok": r.status_code == 200, "error": "" if r.status_code == 200 else r.text[:200]}
        return {"ok": bool(self.session.cookies.get("c_user"))}
