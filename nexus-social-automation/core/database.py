"""
SQLite WAL-Mode Database Engine & Credential Vault for Nexus Social Automation.
Resistant to sudden power cuts and internet drops on Android/Termux.
Includes 15 tables covering accounts, voice profiles, multi-platform posts,
OpenReply Arabic rules, unified inbox, Agent-Reach targets, and AI router telemetry.
"""
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import base64
import hashlib
try:
    from cryptography.fernet import Fernet
    _HAS_FERNET = True
except ImportError:
    Fernet = None  # type: ignore
    _HAS_FERNET = False

import config

_db_lock = threading.RLock()


def _get_secret_bytes() -> bytes:
    if not config.SECRET_KEY_PATH.exists():
        key = base64.urlsafe_b64encode(hashlib.sha256(str(datetime.now()).encode()).digest())
        config.SECRET_KEY_PATH.write_bytes(key)
        try:
            config.SECRET_KEY_PATH.chmod(0o600)
        except OSError:
            pass
    return config.SECRET_KEY_PATH.read_bytes().strip()


def encrypt_credentials(data: Dict[str, Any]) -> str:
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    secret = _get_secret_bytes()
    if _HAS_FERNET:
        try:
            return Fernet(secret).encrypt(raw).decode("utf-8")
        except Exception:
            pass
    # Pure-Python stdlib XOR-SHA256 fallback if cryptography is missing
    key_stream = hashlib.sha256(secret).digest()
    xored = bytes(b ^ key_stream[i % len(key_stream)] for i, b in enumerate(raw))
    return "STDLIB:" + base64.urlsafe_b64encode(xored).decode("ascii")


def decrypt_credentials(token: str) -> Dict[str, Any]:
    if not token:
        return {}
    secret = _get_secret_bytes()
    if token.startswith("STDLIB:"):
        try:
            xored = base64.urlsafe_b64decode(token[7:].encode("ascii"))
            key_stream = hashlib.sha256(secret).digest()
            raw = bytes(b ^ key_stream[i % len(key_stream)] for i, b in enumerate(xored))
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}
    if _HAS_FERNET:
        try:
            raw = Fernet(secret).decrypt(token.encode("utf-8"))
            return json.loads(raw.decode("utf-8"))
        except Exception:
            pass
    try:
        return json.loads(token)
    except Exception:
        return {}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_conn():
    with _db_lock:
        conn = sqlite3.connect(str(config.DB_PATH), timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # Power-cut resilience: Write-Ahead Logging + Foreign Keys
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


SCHEMA_SQL = """
-- 1. Linked Personal & Business Accounts (with Catch-up Cursors & Mode Override)
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    username TEXT NOT NULL,
    display_name TEXT DEFAULT '',
    credentials TEXT NOT NULL,
    account_type TEXT DEFAULT 'personal',
    auth_method TEXT DEFAULT 'webview_session',
    operation_mode TEXT DEFAULT 'INHERIT',
    device_fingerprint TEXT DEFAULT '',
    last_comment_cursor TEXT DEFAULT '',
    last_dm_cursor TEXT DEFAULT '',
    last_sync_ts TEXT DEFAULT '',
    median_views INTEGER DEFAULT 1000,
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL
);

-- 2. Account Voice Profiles (voice.md per account from Instagram Agent Nadr.ai)
CREATE TABLE IF NOT EXISTS account_voice_profiles (
    account_id INTEGER PRIMARY KEY,
    dialect TEXT DEFAULT 'عربية فصحى بسيطة مطعمة بلهجةودية',
    persona_summary TEXT DEFAULT '',
    target_audience TEXT DEFAULT '',
    offer_and_price TEXT DEFAULT '',
    camera_style TEXT DEFAULT 'سريع وحماسي وعملي',
    signature_words TEXT DEFAULT '[]',
    forbidden_words TEXT DEFAULT '[]',
    emoji_density TEXT DEFAULT 'قليل',
    bold_opinions TEXT DEFAULT '[]',
    verified_proofs TEXT DEFAULT '[]',
    default_cta_keyword TEXT DEFAULT 'تفاصيل',
    bio_link_target TEXT DEFAULT '',
    updated_at TEXT NOT NULL,
    FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
);

-- 3. Post Groups (Multi-platform Campaign / Batch Container)
CREATE TABLE IF NOT EXISTS post_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT DEFAULT '',
    text TEXT NOT NULL,
    media_id INTEGER DEFAULT NULL,
    media_kind TEXT DEFAULT 'none',
    is_trial_reel INTEGER DEFAULT 0,
    hook_template_id TEXT DEFAULT '',
    hook_score INTEGER DEFAULT 0,
    humanizer_score INTEGER DEFAULT 100,
    scheduled_at TEXT NOT NULL,
    status TEXT DEFAULT 'scheduled',
    source TEXT DEFAULT 'manual',
    meta TEXT DEFAULT '{}',
    created_at TEXT NOT NULL
);

-- 4. Post Targets (Per-account delivery with exponential backoff & network recovery)
CREATE TABLE IF NOT EXISTS post_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    platform TEXT NOT NULL,
    text_override TEXT DEFAULT '',
    media_path_override TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    attempts INTEGER DEFAULT 0,
    due_at TEXT NOT NULL,
    next_try_at TEXT DEFAULT NULL,
    remote_id TEXT DEFAULT '',
    remote_url TEXT DEFAULT '',
    error TEXT DEFAULT '',
    updated_at TEXT NOT NULL,
    FOREIGN KEY(group_id) REFERENCES post_groups(id) ON DELETE CASCADE,
    FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
);

-- 5. Media Vault (FFmpeg Uniquify + Pexels Auto-Video + GitHub HTTPS Relay)
CREATE TABLE IF NOT EXISTS media_vault (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT DEFAULT '',
    media_kind TEXT NOT NULL,
    original_path TEXT NOT NULL,
    uniquified_path TEXT DEFAULT '',
    public_relay_url TEXT DEFAULT '',
    file_hash TEXT DEFAULT '',
    duration_sec REAL DEFAULT 0.0,
    aspect_ratio TEXT DEFAULT '9:16',
    avoid_women_verified INTEGER DEFAULT 1,
    meta TEXT DEFAULT '{}',
    created_at TEXT NOT NULL
);

-- 6. Auto-Reply Rules (Bulldozer OpenReply Comment-to-DM + Arabic Matcher)
CREATE TABLE IF NOT EXISTS reply_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    media_id TEXT DEFAULT '*',
    keywords TEXT NOT NULL,
    any_comment INTEGER DEFAULT 0,
    whole_word INTEGER DEFAULT 0,
    require_follower INTEGER DEFAULT 0,
    public_replies TEXT NOT NULL,
    dm_text TEXT DEFAULT '',
    dm_link TEXT DEFAULT '',
    dm_button_title TEXT DEFAULT 'افتح الرابط',
    followup_dm_text TEXT DEFAULT '',
    followup_delay_min INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
);

-- 7. Auto-Reply Execution Log (Deduplication & Catch-Up Throttling)
CREATE TABLE IF NOT EXISTS reply_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id INTEGER DEFAULT NULL,
    account_id INTEGER NOT NULL,
    platform TEXT NOT NULL,
    comment_id TEXT NOT NULL UNIQUE,
    media_id TEXT DEFAULT '',
    user_id TEXT DEFAULT '',
    username TEXT DEFAULT '',
    comment_text TEXT DEFAULT '',
    category TEXT DEFAULT 'KEYWORD',
    public_text TEXT DEFAULT '',
    dm_text TEXT DEFAULT '',
    public_status TEXT DEFAULT 'pending',
    dm_status TEXT DEFAULT 'pending',
    status TEXT DEFAULT 'queued',
    attempts INTEGER DEFAULT 0,
    release_at TEXT NOT NULL,
    error TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 8. Unified Categorized Inbox (Comments + DMs sorted by /ig-reply 6 tiers)
CREATE TABLE IF NOT EXISTS inbox_categorized (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    platform TEXT NOT NULL,
    item_type TEXT NOT NULL,
    external_id TEXT NOT NULL UNIQUE,
    sender_id TEXT DEFAULT '',
    sender_username TEXT NOT NULL,
    post_external_id TEXT DEFAULT '',
    incoming_text TEXT NOT NULL,
    category TEXT NOT NULL,
    priority_rank INTEGER DEFAULT 3,
    proposed_reply TEXT DEFAULT '',
    proposed_dm TEXT DEFAULT '',
    status TEXT DEFAULT 'pending_review',
    received_at TEXT NOT NULL,
    processed_at TEXT DEFAULT NULL,
    FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
);

-- 9. Target Accounts & Channels for Agent-Reach Radar
CREATE TABLE IF NOT EXISTS targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER DEFAULT NULL,
    platform TEXT NOT NULL,
    target_handle TEXT NOT NULL,
    niche_tag TEXT DEFAULT '',
    median_views INTEGER DEFAULT 5000,
    last_scanned_at TEXT DEFAULT '',
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL
);

-- 10. Comment & Engagement Queue (Agent-Reach Posts + /ig-comment 9 archetypes)
CREATE TABLE IF NOT EXISTS comment_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    platform TEXT NOT NULL,
    target_username TEXT NOT NULL,
    post_id TEXT NOT NULL,
    post_url TEXT DEFAULT '',
    post_text TEXT DEFAULT '',
    post_views INTEGER DEFAULT 0,
    outlier_multiplier REAL DEFAULT 1.0,
    detected_hook_formula TEXT DEFAULT '',
    comment_archetype TEXT DEFAULT '',
    proposed_comment TEXT NOT NULL,
    humanizer_score INTEGER DEFAULT 100,
    status TEXT DEFAULT 'pending',
    release_at TEXT DEFAULT NULL,
    posted_at TEXT DEFAULT NULL,
    error TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

-- 11. Autonomous Content Generation Rules (Auto-News, Auto-Topics, YouTube Repurpose)
CREATE TABLE IF NOT EXISTS auto_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    topic_or_source TEXT NOT NULL,
    account_ids TEXT NOT NULL,
    times TEXT NOT NULL,
    media_mode TEXT DEFAULT 'text_or_image',
    tone TEXT DEFAULT 'professional',
    require_approval INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    last_slot TEXT DEFAULT '',
    recent_titles TEXT DEFAULT '[]',
    created_at TEXT NOT NULL
);

-- 12. Hourly Rate Events Tracker (Anti-Ban Protection)
CREATE TABLE IF NOT EXISTS rate_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    ts TEXT NOT NULL
);

-- 13. System Activity Log
CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    platform TEXT DEFAULT 'system',
    action TEXT NOT NULL,
    detail TEXT NOT NULL,
    ok INTEGER DEFAULT 1
);

-- 14. Global Key-Value Settings
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- 15. AI Provider Health & Telemetry
CREATE TABLE IF NOT EXISTS ai_provider_stats (
    provider_name TEXT PRIMARY KEY,
    success_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    avg_latency_ms REAL DEFAULT 0.0,
    cooldown_until TEXT DEFAULT '',
    last_error TEXT DEFAULT '',
    updated_at TEXT NOT NULL
);
"""


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA_SQL)
        # Ensure default global settings exist
        defaults = {
            "operation_mode": config.DEFAULT_OPERATION_MODE,
            "active_window_start": config.SCHEDULER_CONFIG["active_window_start"],
            "active_window_end": config.SCHEDULER_CONFIG["active_window_end"],
            "jitter_minutes": str(config.SCHEDULER_CONFIG["jitter_minutes"]),
            "avoid_women_filter": "1",
            "auto_uniquify_video": "1",
            "last_network_online_ts": now_iso(),
        }
        for k, v in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (k, str(v)),
            )


def get_setting(key: str, default: str = "") -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )


def log_activity(action: str, detail: str, platform: str = "system", ok: bool = True):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO activity_log (ts, platform, action, detail, ok) VALUES (?, ?, ?, ?, ?)",
            (now_iso(), platform, action, detail[:1000], 1 if ok else 0),
        )


def check_rate_limit(account_id: int, action: str) -> bool:
    """Returns True if action is within safe hourly limits for this account."""
    limit = config.RATE_LIMITS_PER_HOUR.get(action, 20)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM rate_events "
            "WHERE account_id = ? AND action = ? AND ts >= datetime('now', '-1 hour')",
            (account_id, action),
        ).fetchone()
        return (row["cnt"] if row else 0) < limit


def record_rate_event(account_id: int, action: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO rate_events (account_id, action, ts) VALUES (?, ?, datetime('now'))",
            (account_id, action),
        )
