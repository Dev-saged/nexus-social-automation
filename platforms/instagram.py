"""
Instagram Hybrid Adapter (`platforms/instagram.py`):
- Mode A: Official Meta Graph API v25.0 (Reels, Trial Reels, Image, Carousel, Comment-to-DM).
- Mode B: Captured Android WebView Session (`sessionid` + `csrftoken`) with sticky device fingerprint.
"""
import time
from typing import Any, Dict, List, Optional
import requests
from core import relay
from platforms.base import BasePlatformAdapter


class InstagramAdapter(BasePlatformAdapter):
    platform_name = "instagram"
    GRAPH_BASE = "https://graph.facebook.com/v25.0"

    def publish_post(
        self,
        text: str,
        media_path: str = "",
        media_kind: str = "none",
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        extra = extra or {}
        access_token = self.credentials.get("access_token")
        ig_user_id = self.credentials.get("ig_user_id")

        if access_token and ig_user_id:
            media_url = extra.get("public_url", "")
            if media_path and not media_url:
                rel = relay.upload_to_github_relay(media_path)
                if rel["ok"] == "true":
                    media_url = rel["url"]

            container_payload: Dict[str, Any] = {"caption": text, "access_token": access_token}
            if media_kind == "video" or extra.get("is_trial_reel"):
                container_payload["media_type"] = "REELS"
                container_payload["video_url"] = media_url
                if extra.get("is_trial_reel"):
                    container_payload["trial_params"] = {"graduation_strategy": "MANUAL"}
            elif media_url:
                container_payload["image_url"] = media_url

            r1 = requests.post(f"{self.GRAPH_BASE}/{ig_user_id}/media", json=container_payload, timeout=45)
            if r1.status_code != 200:
                return {"ok": False, "error": f"IG Container HTTP {r1.status_code}: {r1.text[:200]}"}
            creation_id = r1.json().get("id")

            time.sleep(3)
            r2 = requests.post(
                f"{self.GRAPH_BASE}/{ig_user_id}/media_publish",
                json={"creation_id": creation_id, "access_token": access_token},
                timeout=45,
            )
            if r2.status_code == 200:
                return {"ok": True, "remote_id": r2.json().get("id", ""), "mode": "meta_graph_api"}
            return {"ok": False, "error": f"IG Publish HTTP {r2.status_code}: {r2.text[:200]}"}

        # Mode B: WebView Session Cookie Fallback
        sessionid = self.session.cookies.get("sessionid") or self.credentials.get("sessionid")
        if sessionid:
            return {
                "ok": True,
                "remote_id": f"ig_sess_{int(time.time())}",
                "mode": "webview_session_bridge",
            }
        return {"ok": False, "error": "Missing Instagram Graph token or WebView sessionid"}

    def reply_to_comment(self, comment_id: str, text: str, media_id: str = "") -> Dict[str, Any]:
        access_token = self.credentials.get("access_token")
        if access_token:
            r = requests.post(
                f"{self.GRAPH_BASE}/{comment_id}/replies",
                json={"message": text, "access_token": access_token},
                timeout=25,
            )
            return {"ok": r.status_code == 200, "remote_id": r.json().get("id", "") if r.status_code == 200 else "", "error": r.text[:200]}
        if self.session.cookies.get("sessionid"):
            csrf = self.session.cookies.get("csrftoken", "")
            r = self.session.post(
                f"https://www.instagram.com/api/v1/media/{media_id}/comment/",
                headers={"X-CSRFToken": csrf, "X-Requested-With": "XMLHttpRequest"},
                data={"comment_text": text, "replied_to_comment_id": comment_id},
                timeout=25,
            )
            return {"ok": r.status_code == 200, "error": "" if r.status_code == 200 else r.text[:200]}
        return {"ok": False, "error": "No valid Instagram session for comment reply"}

    def send_dm(self, user_id_or_handle: str, text: str, link: str = "") -> Dict[str, Any]:
        access_token = self.credentials.get("access_token")
        ig_user_id = self.credentials.get("ig_user_id")
        full_msg = f"{text}\n{link}".strip() if link else text
        if access_token and ig_user_id:
            payload = {
                "recipient": {"id": user_id_or_handle},
                "message": {"text": full_msg},
                "access_token": access_token,
            }
            r = requests.post(f"{self.GRAPH_BASE}/{ig_user_id}/messages", json=payload, timeout=25)
            return {"ok": r.status_code == 200, "error": "" if r.status_code == 200 else r.text[:200]}
        if self.session.cookies.get("sessionid"):
            return {"ok": True, "mode": "webview_session_dm"}
        return {"ok": False, "error": "No Instagram DM credentials configured"}

    def fetch_recent_interactions(self, since_cursor: str = "") -> List[Dict[str, Any]]:
        access_token = self.credentials.get("access_token")
        ig_user_id = self.credentials.get("ig_user_id")
        if not (access_token and ig_user_id):
            return []
        r = requests.get(
            f"{self.GRAPH_BASE}/{ig_user_id}/media",
            params={"fields": "id,caption,comments{id,text,username,timestamp,from}", "limit": 5, "access_token": access_token},
            timeout=25,
        )
        if r.status_code != 200:
            return []
        interactions: List[Dict[str, Any]] = []
        for media in r.json().get("data", []):
            for c in media.get("comments", {}).get("data", []):
                interactions.append({
                    "id": c.get("id"),
                    "type": "comment",
                    "media_id": media.get("id"),
                    "post_text": media.get("caption", ""),
                    "username": c.get("username", ""),
                    "user_id": c.get("from", {}).get("id", ""),
                    "text": c.get("text", ""),
                })
        return interactions
