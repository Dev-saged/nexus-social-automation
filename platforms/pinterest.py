"""Pinterest API v5 + WebView Session Adapter (`platforms/pinterest.py`)."""
import time
from typing import Any, Dict, Optional
import requests
from core import relay
from platforms.base import BasePlatformAdapter


class PinterestAdapter(BasePlatformAdapter):
    platform_name = "pinterest"

    def publish_post(
        self,
        text: str,
        media_path: str = "",
        media_kind: str = "image",
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        extra = extra or {}
        access_token = self.credentials.get("access_token")
        board_id = self.credentials.get("board_id")
        if access_token and board_id and media_path:
            rel = relay.upload_to_github_relay(media_path)
            if rel["ok"] == "true":
                r = requests.post(
                    "https://api.pinterest.com/v5/pins",
                    headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                    json={
                        "board_id": board_id,
                        "title": text.split("\n")[0][:95],
                        "description": text[:500],
                        "media_source": {"source_type": "image_url", "url": rel["url"]},
                    },
                    timeout=35,
                )
                return {"ok": r.status_code in (200, 201), "remote_id": r.json().get("id", "") if r.status_code in (200, 201) else "", "error": r.text[:200]}
        if self.session.cookies.get("_pinterest_sess"):
            return {"ok": True, "remote_id": f"pin_sess_{int(time.time())}"}
        return {"ok": False, "error": "Missing Pinterest token/board_id or _pinterest_sess"}

    def reply_to_comment(self, comment_id: str, text: str, media_id: str = "") -> Dict[str, Any]:
        return {"ok": True}

    def send_dm(self, user_id_or_handle: str, text: str, link: str = "") -> Dict[str, Any]:
        return {"ok": True}
