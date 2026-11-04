"""
GitHub HTTPS Media Relay (`core/relay.py` upgraded from Dev-saged/social-manager).
Uploads local media files (images/videos) from Termux to a GitHub repository via REST API
to obtain a direct public `raw.githubusercontent.com` HTTPS link required by Meta Graph API
(Instagram, Facebook, Threads) and Pinterest API.
"""
import base64
import os
import time
from pathlib import Path
from typing import Dict
import requests


def upload_to_github_relay(local_path: str) -> Dict[str, str]:
    token = os.getenv("GITHUB_RELAY_TOKEN", "") or os.getenv("GITHUB_MODELS_TOKEN", "")
    repo = os.getenv("GITHUB_RELAY_REPO", "Dev-saged/media-relay-vault")
    branch = os.getenv("GITHUB_RELAY_BRANCH", "main")

    p = Path(local_path)
    if not p.exists():
        return {"ok": "false", "error": f"File not found: {local_path}", "url": ""}
    if not token:
        return {"ok": "false", "error": "GITHUB_RELAY_TOKEN is not configured in .env", "url": ""}

    remote_filename = f"uploads/{int(time.time())}_{p.name}"
    api_url = f"https://api.github.com/repos/{repo}/contents/{remote_filename}"
    b64_content = base64.b64encode(p.read_bytes()).decode("ascii")

    resp = requests.put(
        api_url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        json={
            "message": f"Relay upload {p.name}",
            "content": b64_content,
            "branch": branch,
        },
        timeout=90,
    )
    if resp.status_code in (200, 201):
        raw_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{remote_filename}"
        return {"ok": "true", "url": raw_url, "error": ""}
    return {"ok": "false", "url": "", "error": f"GitHub Relay HTTP {resp.status_code}: {resp.text[:200]}"}
