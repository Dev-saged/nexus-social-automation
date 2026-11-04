"""
Agent-Reach Bridge & Multi-Fallback Reader (`reach_bridge/dispatcher.py`).
Implements Panniantong/Agent-Reach's core design philosophy:
"Every platform = Primary tool + Ordered Fallbacks (Read-Only, Zero API Fees)."
1. Primary: Calls `agent-reach <channel> <action> ...` CLI if installed in Termux (`~/.agent-reach`).
2. Fallback 1: `yt-dlp` for YouTube/TikTok/Instagram video metadata & subtitles extraction.
3. Fallback 2: `Jina Reader` (`https://r.jina.ai/<url>`) for clean Markdown extraction of public profiles/posts/threads.
4. Fallback 3: Platform adapter's isolated read session (`fetch_account_posts`).
"""
import json
import shutil
import subprocess
from typing import Any, Dict, List
import requests

from core import database


class AgentReachBridge:
    """Gives the AI automation system 'eyes' to read posts, trends, and transcripts for free."""

    def has_agent_reach_cli(self) -> bool:
        return shutil.which("agent-reach") is not None

    def read_url_or_post(self, url: str) -> Dict[str, Any]:
        """Reads any social post, thread, article, or video URL using ordered fallbacks."""
        # 1. Try Agent-Reach CLI first
        if self.has_agent_reach_cli():
            try:
                proc = subprocess.run(
                    ["agent-reach", "read", url],
                    capture_output=True,
                    text=True,
                    timeout=35,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    return {"ok": True, "source": "agent_reach_cli", "content": proc.stdout.strip(), "url": url}
            except Exception:
                pass

        # 2. If YouTube / TikTok / Reel video URL, try yt-dlp metadata & subtitles
        if any(dom in url for dom in ("youtube.com", "youtu.be", "tiktok.com")) and shutil.which("yt-dlp"):
            try:
                proc = subprocess.run(
                    ["yt-dlp", "--dump-json", "--no-download", url],
                    capture_output=True,
                    text=True,
                    timeout=35,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    meta = json.loads(proc.stdout.splitlines()[0])
                    text_summary = (
                        f"Title: {meta.get('title')}\n"
                        f"Uploader: {meta.get('uploader')}\n"
                        f"Views: {meta.get('view_count', 0)}\n"
                        f"Description: {meta.get('description', '')[:1500]}"
                    )
                    return {
                        "ok": True,
                        "source": "yt_dlp_extractor",
                        "content": text_summary,
                        "views": int(meta.get("view_count") or 0),
                        "url": url,
                    }
            except Exception:
                pass

        # 3. Fallback: Jina Reader API (Free Markdown Web & Social Reader)
        try:
            jina_url = f"https://r.jina.ai/{url}"
            resp = requests.get(jina_url, headers={"Accept": "text/plain"}, timeout=25)
            if resp.status_code == 200 and len(resp.text.strip()) > 40:
                return {
                    "ok": True,
                    "source": "jina_reader_fallback",
                    "content": resp.text.strip()[:4000],
                    "url": url,
                }
        except Exception as exc:
            return {"ok": False, "error": str(exc), "url": url}

        return {"ok": False, "error": "All Agent-Reach fallbacks exhausted for URL", "url": url}

    def search_platform(self, channel: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Searches a platform (x_twitter, reddit, youtube, linkedin, instagram, web)
        using Agent-Reach CLI primary + native fallbacks.
        """
        if self.has_agent_reach_cli():
            ch_map = {"x_twitter": "twitter"}
            ar_channel = ch_map.get(channel, channel)
            try:
                proc = subprocess.run(
                    ["agent-reach", ar_channel, "search", query],
                    capture_output=True,
                    text=True,
                    timeout=40,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    try:
                        data = json.loads(proc.stdout)
                        items = data.get("result") or data.get("items") or []
                        if isinstance(items, list) and items:
                            return items[:limit]
                    except Exception:
                        return [{"title": query, "text": proc.stdout.strip()[:1000], "url": "", "views": 1000}]
            except Exception:
                pass

        # Fallback for YouTube search via yt-dlp
        if channel == "youtube" and shutil.which("yt-dlp"):
            try:
                proc = subprocess.run(
                    ["yt-dlp", f"ytsearch{limit}:{query}", "--dump-json", "--flat-playlist"],
                    capture_output=True,
                    text=True,
                    timeout=35,
                )
                results = []
                for line in proc.stdout.splitlines():
                    if not line.strip():
                        continue
                    item = json.loads(line)
                    results.append({
                        "id": item.get("id", ""),
                        "title": item.get("title", ""),
                        "text": f"{item.get('title', '')} - {item.get('description', '')}",
                        "url": item.get("url") or f"https://www.youtube.com/watch?v={item.get('id')}",
                        "views": int(item.get("view_count") or 5000),
                        "author": item.get("uploader", ""),
                    })
                if results:
                    return results
            except Exception:
                pass

        # Fallback for Reddit JSON search (Zero API Key)
        if channel == "reddit":
            try:
                resp = requests.get(
                    "https://www.reddit.com/search.json",
                    params={"q": query, "limit": limit, "sort": "hot"},
                    headers={"User-Agent": "NexusSocialAgentReach/2.0"},
                    timeout=20,
                )
                if resp.status_code == 200:
                    children = resp.json().get("data", {}).get("children", [])
                    return [
                        {
                            "id": c["data"].get("id"),
                            "title": c["data"].get("title"),
                            "text": c["data"].get("selftext", "")[:800] or c["data"].get("title", ""),
                            "url": f"https://www.reddit.com{c['data'].get('permalink', '')}",
                            "views": int(c["data"].get("score", 100)) * 20,
                            "author": c["data"].get("author", ""),
                        }
                        for c in children
                    ]
            except Exception:
                pass

        # Fallback: Jina Search / DuckDuckGo Lite via Jina Reader
        try:
            q_url = f"https://s.jina.ai/{requests.utils.quote(channel + ' ' + query)}"
            resp = requests.get(q_url, headers={"Accept": "text/plain"}, timeout=25)
            if resp.status_code == 200 and resp.text.strip():
                return [{
                    "id": f"web_{ abs(hash(query)) % 100000 }",
                    "title": f"نتائج رصد {channel}: {query}",
                    "text": resp.text.strip()[:1500],
                    "url": "",
                    "views": 4500,
                    "author": query,
                }]
        except Exception:
            pass

        return []


reach_bridge = AgentReachBridge()
