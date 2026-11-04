"""
Main API & Dashboard Server (`core/server.py`).
Built on a dual-engine router that runs natively on Python's standard library
(`http.server.ThreadingHTTPServer`) OR Flask, plus includes a built-in test client
so it runs on any Android Termux setup without requiring C-extensions!
"""
import json
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple
from urllib.parse import urlparse

import config
from core import catchup_sync, database, media_factory, publisher, scheduler
from core.ai_router import router
from core.ai_skills import content_studio, hooks_library, humanizer, voice_profile


# ============================================================================
# CORE API HANDLERS (Framework-Agnostic JSON Controllers)
# ============================================================================

def handle_status() -> Tuple[int, Dict[str, Any]]:
    with database.get_conn() as conn:
        accounts_cnt = conn.execute("SELECT COUNT(*) as c FROM accounts WHERE active=1").fetchone()["c"]
        pending_posts = conn.execute("SELECT COUNT(*) as c FROM post_targets WHERE status IN ('pending','waiting_network')").fetchone()["c"]
        published_posts = conn.execute("SELECT COUNT(*) as c FROM post_targets WHERE status='published'").fetchone()["c"]
        pending_inbox = conn.execute("SELECT COUNT(*) as c FROM inbox_categorized WHERE status='pending_review'").fetchone()["c"]
        queued_replies = conn.execute("SELECT COUNT(*) as c FROM reply_log WHERE status='queued'").fetchone()["c"]
        logs = [dict(r) for r in conn.execute("SELECT * FROM activity_log ORDER BY id DESC LIMIT 25").fetchall()]

    base_vid = config.SCHEDULER_CONFIG["default_video_slots"]
    base_post = config.SCHEDULER_CONFIG["default_post_slots"]
    jitter = int(database.get_setting("jitter_minutes", "15"))

    return 200, {
        "ok": True,
        "online": catchup_sync.is_online(),
        "operation_mode": database.get_setting("operation_mode", config.DEFAULT_OPERATION_MODE),
        "last_network_online_ts": database.get_setting("last_network_online_ts", ""),
        "counts": {
            "active_accounts": accounts_cnt,
            "pending_posts": pending_posts,
            "published_posts": published_posts,
            "pending_inbox": pending_inbox,
            "queued_replies": queued_replies,
        },
        "planned_today": {
            "videos": scheduler.plan_daily_slots_with_jitter(base_vid, jitter),
            "posts": scheduler.plan_daily_slots_with_jitter(base_post, jitter),
        },
        "supported_platforms": config.SUPPORTED_PLATFORMS,
        "platform_login_urls": config.PLATFORM_LOGIN_URLS,
        "logs": logs,
    }


def handle_set_mode(data: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    mode = data.get("mode", "SMART_HYBRID")
    if mode not in ("FULL_AUTO", "SMART_HYBRID", "APPROVAL_QUEUE"):
        return 400, {"ok": False, "error": "Invalid mode"}
    database.set_setting("operation_mode", mode)
    database.log_activity("mode_switch", f"Global operation mode switched to {mode}")
    return 200, {"ok": True, "operation_mode": mode}


def handle_wakeup(data: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    source = data.get("source", "apk_watchdog")
    res = catchup_sync.run_catchup_cycle(trigger_source=source)
    pub_res = publisher.run_due_posts()
    rep_res = publisher.run_due_replies_and_comments()
    return 200, {"ok": True, "catchup": res, "publisher": pub_res, "replies": rep_res}


def handle_get_accounts() -> Tuple[int, Dict[str, Any]]:
    with database.get_conn() as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT id, platform, username, display_name, account_type, auth_method, operation_mode, last_sync_ts, median_views, active, created_at FROM accounts ORDER BY id DESC"
            ).fetchall()
        ]
    return 200, {"ok": True, "accounts": rows}


def handle_add_account(data: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    platform = data.get("platform", "instagram").lower()
    username = data.get("username", "my_account")
    creds = data.get("credentials", {})
    enc = database.encrypt_credentials(creds)
    with database.get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO accounts (platform, username, display_name, credentials, account_type, auth_method, operation_mode, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                platform,
                username,
                data.get("display_name", username),
                enc,
                data.get("account_type", "personal"),
                data.get("auth_method", "manual_token"),
                data.get("operation_mode", "INHERIT"),
                database.now_iso(),
            ),
        )
        acc_id = cur.lastrowid
    database.log_activity("account_linked", f"Linked @{username} on {platform}", platform=platform)
    return 200, {"ok": True, "account_id": acc_id}


def handle_capture_session(data: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    platform = (data.get("platform") or "instagram").lower()
    username = data.get("username") or f"{platform}_user"
    cookie_string = data.get("cookie_string", "")
    user_agent = data.get("user_agent", "")
    extra_tokens = data.get("tokens", {})

    creds_payload = {
        "cookie_string": cookie_string,
        "user_agent": user_agent,
        **extra_tokens,
    }
    enc = database.encrypt_credentials(creds_payload)
    with database.get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM accounts WHERE platform=? AND username=?", (platform, username)
        ).fetchone()
        if existing:
            acc_id = existing["id"]
            conn.execute(
                "UPDATE accounts SET credentials=?, auth_method='apk_webview_bridge', active=1, last_sync_ts=? WHERE id=?",
                (enc, database.now_iso(), acc_id),
            )
        else:
            cur = conn.execute(
                "INSERT INTO accounts (platform, username, display_name, credentials, account_type, auth_method, created_at) "
                "VALUES (?, ?, ?, ?, 'personal', 'apk_webview_bridge', ?)",
                (platform, username, username, enc, database.now_iso()),
            )
            acc_id = cur.lastrowid

    database.log_activity("apk_session_captured", f"One-Tap WebView session captured for @{username} ({platform})", platform=platform)
    return 200, {"ok": True, "account_id": acc_id, "platform": platform, "username": username}


def handle_schedule_post(data: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    texts = data.get("topics") or [data.get("text", "")]
    account_ids = data.get("account_ids", [])
    media_kind = data.get("media_kind", "none")
    is_trial_reel = 1 if data.get("is_trial_reel") else 0
    publish_now = bool(data.get("publish_now", False))

    if not account_ids:
        with database.get_conn() as conn:
            account_ids = [r["id"] for r in conn.execute("SELECT id FROM accounts WHERE active=1").fetchall()]

    created_groups = []
    now = datetime.now(timezone.utc)
    jitter_min = int(database.get_setting("jitter_minutes", "15"))

    for idx, raw_txt in enumerate(texts):
        txt = raw_txt.strip()
        if not txt:
            continue
        cleaned = humanizer.clean_and_humanize(txt)
        due_dt = now if publish_now else (now + timedelta(minutes=(idx * 60) + jitter_min))
        due_iso = due_dt.isoformat()

        with database.get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO post_groups (title, text, media_kind, is_trial_reel, humanizer_score, scheduled_at, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'scheduled', ?)
                """,
                (txt[:80], cleaned["cleaned_text"], media_kind, is_trial_reel, cleaned["score"], due_iso, database.now_iso()),
            )
            gid = cur.lastrowid
            for aid in account_ids:
                acc_row = conn.execute("SELECT platform FROM accounts WHERE id=?", (aid,)).fetchone()
                if not acc_row:
                    continue
                conn.execute(
                    """
                    INSERT INTO post_targets (group_id, account_id, platform, status, due_at, updated_at)
                    VALUES (?, ?, ?, 'pending', ?, ?)
                    """,
                    (gid, aid, acc_row["platform"], due_iso, database.now_iso()),
                )
            created_groups.append(gid)

    if publish_now:
        publisher.run_due_posts()

    return 200, {"ok": True, "created_groups": created_groups, "count": len(created_groups)}


def handle_get_queues() -> Tuple[int, Dict[str, Any]]:
    with database.get_conn() as conn:
        targets = [
            dict(r)
            for r in conn.execute(
                """
                SELECT pt.*, pg.title, pg.text, pg.media_kind, pg.is_trial_reel, pg.humanizer_score, a.username
                FROM post_targets pt
                JOIN post_groups pg ON pg.id = pt.group_id
                LEFT JOIN accounts a ON a.id = pt.account_id
                ORDER BY pt.id DESC LIMIT 60
                """
            ).fetchall()
        ]
    return 200, {"ok": True, "queue": targets}


def handle_queue_action(data: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    action = data.get("action")
    target_id = data.get("target_id")
    now_str = database.now_iso()

    with database.get_conn() as conn:
        if action == "pause" and target_id:
            conn.execute("UPDATE post_targets SET status='paused', updated_at=? WHERE id=?", (now_str, target_id))
        elif action == "resume" and target_id:
            conn.execute("UPDATE post_targets SET status='pending', updated_at=? WHERE id=?", (now_str, target_id))
        elif action == "retry" and target_id:
            conn.execute("UPDATE post_targets SET status='pending', attempts=0, next_try_at=?, error='', updated_at=? WHERE id=?", (now_str, now_str, target_id))
        elif action == "delete" and target_id:
            conn.execute("DELETE FROM post_targets WHERE id=?", (target_id,))
        elif action == "clear_all":
            conn.execute("DELETE FROM post_targets WHERE status IN ('pending','paused','failed')")

    return 200, {"ok": True, "action": action}


def handle_run_skill(data: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    skill = data.get("skill", "ig-reel")
    topic = data.get("input", "")
    account_id = data.get("account_id")
    res = content_studio.run_skill(skill, topic, account_id=account_id, extra_params=data)
    return 200, res


def handle_auto_video(data: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    res = media_factory.generate_complete_video(
        topic=data.get("topic", "أتمتة الأعمال بالذكاء الاصطناعي"),
        duration_sec=int(data.get("duration_sec", 45)),
        aspect_ratio=data.get("aspect_ratio", "9:16"),
        lang=data.get("lang", "ar"),
        voice_gender=data.get("voice_gender", "Male"),
        avoid_women=bool(data.get("avoid_women", True)),
        account_id=data.get("account_id"),
    )
    return 200, res


def handle_get_inbox() -> Tuple[int, Dict[str, Any]]:
    with database.get_conn() as conn:
        items = [dict(r) for r in conn.execute("SELECT * FROM inbox_categorized ORDER BY priority_rank ASC, id DESC LIMIT 50").fetchall()]
        rules = [dict(r) for r in conn.execute("SELECT * FROM reply_rules ORDER BY id DESC").fetchall()]
    return 200, {"ok": True, "inbox": items, "rules": rules}


def handle_inbox_approve(data: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    item_id = data.get("id")
    edited_reply = data.get("reply_text")
    now_str = database.now_iso()

    with database.get_conn() as conn:
        row = conn.execute("SELECT * FROM inbox_categorized WHERE id=?", (item_id,)).fetchone()
        if not row:
            return 404, {"ok": False, "error": "Item not found"}
        item = dict(row)
        final_reply = edited_reply if edited_reply is not None else item["proposed_reply"]
        conn.execute("UPDATE inbox_categorized SET status='approved', proposed_reply=?, processed_at=? WHERE id=?", (final_reply, now_str, item_id))
        conn.execute(
            """
            INSERT OR IGNORE INTO reply_log (
                account_id, platform, comment_id, media_id, user_id, username,
                comment_text, category, public_text, dm_text, status, release_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?, ?)
            """,
            (
                item["account_id"], item["platform"], item["external_id"], item["post_external_id"],
                item["sender_id"], item["sender_username"], item["incoming_text"], item["category"],
                final_reply, item["proposed_dm"], now_str, now_str, now_str,
            ),
        )
    publisher.run_due_replies_and_comments()
    return 200, {"ok": True}


def handle_add_reply_rule(data: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    with database.get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO reply_rules (
                account_id, name, keywords, any_comment, whole_word,
                require_follower, public_replies, dm_text, dm_link, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(data.get("account_id", 1)),
                data.get("name", "قاعدة رد تلقائي"),
                data.get("keywords", "تفاصيل, السعر, الرابط"),
                1 if data.get("any_comment") else 0,
                1 if data.get("whole_word") else 0,
                1 if data.get("require_follower") else 0,
                data.get("public_replies", "شيك على الخاص بعتلك التفاصيل ✨ | تم الإرسال في الرسائل الخاصة 📩"),
                data.get("dm_text", "أهلاً بك! إليك كافة التفاصيل والرابط المباشر:"),
                data.get("dm_link", ""),
                database.now_iso(),
            ),
        )
    return 200, {"ok": True, "rule_id": cur.lastrowid}


def handle_targets(method: str, data: Optional[Dict[str, Any]] = None) -> Tuple[int, Dict[str, Any]]:
    if method == "GET":
        with database.get_conn() as conn:
            targets = [dict(r) for r in conn.execute("SELECT * FROM targets ORDER BY id DESC").fetchall()]
            comments = [dict(r) for r in conn.execute("SELECT * FROM comment_queue ORDER BY outlier_multiplier DESC, id DESC LIMIT 40").fetchall()]
        return 200, {"ok": True, "targets": targets, "comment_queue": comments}

    data = data or {}
    with database.get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO targets (account_id, platform, target_handle, niche_tag, median_views, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                data.get("account_id"),
                data.get("platform", "instagram"),
                data.get("target_handle", ""),
                data.get("niche_tag", ""),
                int(data.get("median_views", 5000)),
                database.now_iso(),
            ),
        )
    return 200, {"ok": True, "target_id": cur.lastrowid}


def handle_scan_targets() -> Tuple[int, Dict[str, Any]]:
    return 200, catchup_sync.scan_targets_with_agent_reach()


def handle_ai_providers() -> Tuple[int, Dict[str, Any]]:
    return 200, {"ok": True, "providers": router.get_providers_status(), "hooks_count": len(hooks_library.HOOK_FORMULAS)}


def dispatch_api_request(method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Tuple[int, Dict[str, Any]]:
    body = body or {}
    if path == "/api/status" and method == "GET":
        return handle_status()
    if path == "/api/system/mode" and method == "POST":
        return handle_set_mode(body)
    if path == "/api/system/wakeup" and method == "POST":
        return handle_wakeup(body)
    if path == "/api/accounts":
        return handle_get_accounts() if method == "GET" else handle_add_account(body)
    if path == "/api/accounts/capture-session" and method == "POST":
        return handle_capture_session(body)
    if path.startswith("/api/voice-profile/"):
        acc_id = int(path.rstrip("/").split("/")[-1])
        if method == "POST":
            voice_profile.save_voice_profile(acc_id, body)
        return 200, {"ok": True, "profile": voice_profile.get_voice_profile(acc_id)}
    if path == "/api/posts/schedule" and method == "POST":
        return handle_schedule_post(body)
    if path == "/api/queues" and method == "GET":
        return handle_get_queues()
    if path == "/api/queues/action" and method == "POST":
        return handle_queue_action(body)
    if path == "/api/skills/run" and method == "POST":
        return handle_run_skill(body)
    if path == "/api/media/auto-video" and method == "POST":
        return handle_auto_video(body)
    if path == "/api/inbox" and method == "GET":
        return handle_get_inbox()
    if path == "/api/inbox/approve" and method == "POST":
        return handle_inbox_approve(body)
    if path == "/api/reply-rules" and method == "POST":
        return handle_add_reply_rule(body)
    if path == "/api/targets":
        return handle_targets(method, body)
    if path == "/api/targets/scan" and method == "POST":
        return handle_scan_targets()
    if path == "/api/ai-providers" and method == "GET":
        return handle_ai_providers()
    return 404, {"ok": False, "error": f"Unknown endpoint {method} {path}"}


# ============================================================================
# BUILT-IN ZERO-DEPENDENCY HTTP SERVER & TEST CLIENT
# ============================================================================

class _TestResponse:
    def __init__(self, status_code: int, payload: Dict[str, Any]):
        self.status_code = status_code
        self._payload = payload

    def get_json(self) -> Dict[str, Any]:
        return self._payload


class _TestClient:
    def get(self, path: str) -> _TestResponse:
        code, data = dispatch_api_request("GET", path)
        return _TestResponse(code, data)

    def post(self, path: str, json: Optional[Dict[str, Any]] = None) -> _TestResponse:
        code, data = dispatch_api_request("POST", path, json or {})
        return _TestResponse(code, data)


class NexusHTTPRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any):
        return  # Quiet logs in Termux

    def _send_json(self, code: int, payload: Dict[str, Any]):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            html_file = config.BASE_DIR / "static" / "index.html"
            raw = html_file.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        code, data = dispatch_api_request("GET", parsed.path)
        self._send_json(code, data)

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            body = json.loads(raw_body) if raw_body.strip() else {}
        except Exception:
            body = {}
        code, data = dispatch_api_request("POST", parsed.path, body)
        self._send_json(code, data)


class NexusServerApp:
    """Provides both `.run(host, port)` and `.test_client()` with zero external dependencies."""

    def test_client(self) -> _TestClient:
        return _TestClient()

    def run(self, host: str = "127.0.0.1", port: int = 5050, **kwargs: Any):
        httpd = ThreadingHTTPServer((host, port), NexusHTTPRequestHandler)
        httpd.serve_forever()


app = NexusServerApp()
