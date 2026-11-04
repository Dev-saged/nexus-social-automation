"""Mastodon Open REST API Adapter (`platforms/mastodon.py` - 100% Free & Open Protocol)."""
from pathlib import Path
from typing import Any, Dict, Optional
import requests
from platforms.base import BasePlatformAdapter


class MastodonAdapter(BasePlatformAdapter):
    platform_name = "mastodon"

    def publish_post(
        self,
        text: str,
        media_path: str = "",
        media_kind: str = "none",
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        instance_url = (self.credentials.get("instance_url") or "https://mastodon.social").rstrip("/")
        access_token = self.credentials.get("access_token")
        if not access_token:
            return {"ok": False, "error": "Missing Mastodon access_token"}

        headers = {"Authorization": f"Bearer {access_token}"}
        media_ids = []
        if media_path and Path(media_path).exists():
            with open(media_path, "rb") as f:
                up = requests.post(f"{instance_url}/api/v2/media", headers=headers, files={"file": f}, timeout=60)
                if up.status_code in (200, 202):
                    media_ids.append(up.json().get("id"))

        payload: Dict[str, Any] = {"status": text, "visibility": "public"}
        if media_ids:
            payload["media_ids"] = media_ids

        r = requests.post(f"{instance_url}/api/v1/statuses", headers=headers, json=payload, timeout=30)
        if r.status_code in (200, 201):
            return {"ok": True, "remote_id": str(r.json().get("id", "")), "remote_url": r.json().get("url", "")}
        return {"ok": False, "error": r.text[:200]}

    def reply_to_comment(self, comment_id: str, text: str, media_id: str = "") -> Dict[str, Any]:
        instance_url = (self.credentials.get("instance_url") or "https://mastodon.social").rstrip("/")
        access_token = self.credentials.get("access_token")
        if not access_token:
            return {"ok": False, "error": "Missing Mastodon access_token"}
        r = requests.post(
            f"{instance_url}/api/v1/statuses",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"status": text, "in_reply_to_id": comment_id},
            timeout=25,
        )
        return {"ok": r.status_code in (200, 201)}

    def send_dm(self, user_id_or_handle: str, text: str, link: str = "") -> Dict[str, Any]:
        instance_url = (self.credentials.get("instance_url") or "https://mastodon.social").rstrip("/")
        access_token = self.credentials.get("access_token")
        full = f"@{user_id_or_handle.lstrip('@')} {text} {link}".strip()
        if not access_token:
            return {"ok": False, "error": "Missing Mastodon access_token"}
        r = requests.post(
            f"{instance_url}/api/v1/statuses",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"status": full, "visibility": "direct"},
            timeout=25,
        )
        return {"ok": r.status_code in (200, 201)}
