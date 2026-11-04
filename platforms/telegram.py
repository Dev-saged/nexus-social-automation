"""Telegram Bot & Personal Channel/Group Adapter (`platforms/telegram.py`)."""
from typing import Any, Dict, Optional
import requests
from platforms.base import BasePlatformAdapter


class TelegramAdapter(BasePlatformAdapter):
    platform_name = "telegram"

    def publish_post(
        self,
        text: str,
        media_path: str = "",
        media_kind: str = "none",
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        bot_token = self.credentials.get("bot_token")
        chat_id = self.credentials.get("chat_id")
        if not (bot_token and chat_id):
            return {"ok": False, "error": "Missing Telegram bot_token or chat_id"}

        base_url = f"https://api.telegram.org/bot{bot_token}"
        if media_path and media_kind == "image":
            with open(media_path, "rb") as f:
                r = requests.post(f"{base_url}/sendPhoto", data={"chat_id": chat_id, "caption": text}, files={"photo": f}, timeout=45)
        elif media_path and media_kind == "video":
            with open(media_path, "rb") as f:
                r = requests.post(f"{base_url}/sendVideo", data={"chat_id": chat_id, "caption": text}, files={"video": f}, timeout=90)
        else:
            r = requests.post(f"{base_url}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=25)

        if r.status_code == 200 and r.json().get("ok"):
            return {"ok": True, "remote_id": str(r.json()["result"].get("message_id", ""))}
        return {"ok": False, "error": r.text[:200]}

    def reply_to_comment(self, comment_id: str, text: str, media_id: str = "") -> Dict[str, Any]:
        bot_token = self.credentials.get("bot_token")
        chat_id = self.credentials.get("chat_id")
        if not (bot_token and chat_id):
            return {"ok": False, "error": "Missing Telegram bot_token"}
        r = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "reply_to_message_id": int(comment_id) if str(comment_id).isdigit() else None},
            timeout=25,
        )
        return {"ok": r.status_code == 200}

    def send_dm(self, user_id_or_handle: str, text: str, link: str = "") -> Dict[str, Any]:
        bot_token = self.credentials.get("bot_token")
        full = f"{text}\n{link}".strip() if link else text
        if not bot_token:
            return {"ok": False, "error": "Missing bot_token"}
        r = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": user_id_or_handle, "text": full},
            timeout=25,
        )
        return {"ok": r.status_code == 200}
