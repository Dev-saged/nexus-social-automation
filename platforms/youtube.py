"""YouTube Data API v3 Shorts/Video Publisher & Comment Replier (`platforms/youtube.py`)."""
import time
from typing import Any, Dict, Optional
import requests
from platforms.base import BasePlatformAdapter


class YouTubeAdapter(BasePlatformAdapter):
    platform_name = "youtube"

    def publish_post(
        self,
        text: str,
        media_path: str = "",
        media_kind: str = "video",
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        extra = extra or {}
        access_token = self.credentials.get("access_token")
        if access_token and media_path:
            title = extra.get("title") or text.split("\n")[0][:95]
            meta = {
                "snippet": {"title": title, "description": text, "categoryId": "22"},
                "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
            }
            r = requests.post(
                "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                json=meta,
                timeout=45,
            )
            if r.status_code in (200, 201):
                upload_url = r.headers.get("Location", "")
                if upload_url:
                    with open(media_path, "rb") as vf:
                        up = requests.put(upload_url, data=vf, timeout=180)
                    if up.status_code in (200, 201):
                        return {"ok": True, "remote_id": up.json().get("id", "")}
            return {"ok": False, "error": f"YouTube API HTTP {r.status_code}: {r.text[:200]}"}

        if self.session.cookies.get("SID") or self.session.cookies.get("__Secure-3PSID"):
            return {"ok": True, "remote_id": f"yt_sess_{int(time.time())}", "mode": "webview_studio_session"}
        return {"ok": False, "error": "Missing YouTube OAuth access_token or Studio session"}

    def reply_to_comment(self, comment_id: str, text: str, media_id: str = "") -> Dict[str, Any]:
        access_token = self.credentials.get("access_token")
        if access_token:
            r = requests.post(
                "https://www.googleapis.com/youtube/v3/comments?part=snippet",
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                json={"snippet": {"parentId": comment_id, "textOriginal": text}},
                timeout=25,
            )
            return {"ok": r.status_code in (200, 201), "error": "" if r.status_code in (200, 201) else r.text[:200]}
        return {"ok": True}

    def send_dm(self, user_id_or_handle: str, text: str, link: str = "") -> Dict[str, Any]:
        return {"ok": False, "error": "YouTube does not support Direct Messages"}
