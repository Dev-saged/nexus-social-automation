"""
Offline-First & Power-Cut Catch-Up Engine (`core/catchup_sync.py`).
Designed specifically for mobile/Termux environments where internet or electricity disconnects:
1. Checks internet connectivity (`is_online()`).
2. Recovers missed scheduled posts (`waiting_network` / overdue `pending`) and applies Anti-Ban Jitter.
3. Polls all active accounts across the 12 platforms for comments & DMs that arrived while offline
   (using each account's `last_comment_cursor` and `last_sync_ts`).
4. Runs `classify_and_draft_reply` (Bulldozer Arabic Keyword Matcher + Nadr.ai `/ig-reply`).
5. Enforces the 3-Way Mode Switch (`FULL_AUTO`, `SMART_HYBRID`, `APPROVAL_QUEUE`) and spaces out
   auto-replies in the Anti-Burst Throttling Queue (`35-90s` intervals).
"""
import json
import random
import socket
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import config
from core import database
from core.ai_skills import comment_classifier, viral_scorer
from reach_bridge.dispatcher import reach_bridge
from platforms import get_adapter


def is_online() -> bool:
    """Fast socket probe to verify real internet access before running any platform sync."""
    for host, port in [("1.1.1.1", 53), ("8.8.8.8", 53)]:
        try:
            with socket.create_connection((host, port), timeout=3.0):
                return True
        except OSError:
            continue
    return False


def get_effective_mode(account_row: Dict[str, Any]) -> str:
    acc_mode = account_row.get("operation_mode", "INHERIT")
    if acc_mode and acc_mode != "INHERIT":
        return acc_mode
    return database.get_setting("operation_mode", config.DEFAULT_OPERATION_MODE)


def run_catchup_cycle(trigger_source: str = "scheduler") -> Dict[str, Any]:
    """
    Executes a complete retroactive sync across all active accounts when internet returns
    or when triggered by the Android APK Watchdog / user button.
    """
    if not is_online():
        database.log_activity("catchup_skip", "Internet offline — keeping tasks safe in SQLite WAL queue.")
        return {"ok": False, "online": False, "message": "لا يوجد اتصال بالإنترنت حالياً؛ المهام محفوظة بأمان."}

    now = datetime.now(timezone.utc)
    database.set_setting("last_network_online_ts", now.isoformat())

    summary = {
        "ok": True,
        "online": True,
        "trigger": trigger_source,
        "recovered_posts": 0,
        "new_comments_processed": 0,
        "auto_replied_count": 0,
        "queued_for_approval": 0,
        "targets_scanned": 0,
    }

    with database.get_conn() as conn:
        # Step 1: Recover overdue or network-waiting posts with staggered anti-ban jitter
        overdue_targets = conn.execute(
            """
            SELECT id, account_id, platform, due_at
            FROM post_targets
            WHERE status IN ('pending', 'waiting_network') AND due_at <= ?
            ORDER BY due_at ASC
            """,
            (now.isoformat(),),
        ).fetchall()

        offset_sec = 10
        for pt in overdue_targets:
            new_due = (now + timedelta(seconds=offset_sec)).isoformat()
            conn.execute(
                "UPDATE post_targets SET status='pending', next_try_at=?, updated_at=? WHERE id=?",
                (new_due, now.isoformat(), pt["id"]),
            )
            offset_sec += random.randint(45, 120)
            summary["recovered_posts"] += 1

        # Step 2: Poll active accounts for new comments & DMs since last_sync_ts
        accounts = [dict(r) for r in conn.execute("SELECT * FROM accounts WHERE active = 1").fetchall()]

    for acc in accounts:
        acc_id = acc["id"]
        platform = acc["platform"]
        mode = get_effective_mode(acc)
        creds = database.decrypt_credentials(acc["credentials"])
        adapter = get_adapter(platform, creds, acc)

        # Load account's active keyword reply rules
        with database.get_conn() as conn:
            rules = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM reply_rules WHERE account_id = ? AND active = 1", (acc_id,)
                ).fetchall()
            ]

        try:
            incoming_comments = adapter.fetch_recent_interactions(since_cursor=acc.get("last_comment_cursor", ""))
        except Exception as exc:
            database.log_activity("sync_error", f"Account @{acc['username']}: {exc}", platform=platform, ok=False)
            incoming_comments = []

        throttle_delay_sec = 5
        for item in incoming_comments:
            ext_id = str(item.get("id") or "")
            if not ext_id:
                continue

            with database.get_conn() as conn:
                exists = conn.execute(
                    "SELECT 1 FROM inbox_categorized WHERE external_id = ?", (ext_id,)
                ).fetchone()
                if exists:
                    continue

            decision = comment_classifier.classify_and_draft_reply(
                comment_text=item.get("text", ""),
                sender_username=item.get("username", "user"),
                post_context=item.get("post_text", ""),
                account_id=acc_id,
                keyword_rules=rules,
            )

            category = decision["category"]
            should_auto_send = False
            if mode == "FULL_AUTO" and category != "NOISE":
                should_auto_send = True
            elif mode == "SMART_HYBRID" and category in ("KEYWORD", "SUPPORT"):
                should_auto_send = True

            release_time = (now + timedelta(seconds=throttle_delay_sec)).isoformat()
            throttle_delay_sec += random.randint(
                config.SCHEDULER_CONFIG["catchup_min_delay_sec"],
                config.SCHEDULER_CONFIG["catchup_max_delay_sec"],
            )

            inbox_status = "auto_queued" if should_auto_send else "pending_review"
            with database.get_conn() as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO inbox_categorized (
                        account_id, platform, item_type, external_id, sender_id,
                        sender_username, post_external_id, incoming_text, category,
                        priority_rank, proposed_reply, proposed_dm, status, received_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        acc_id,
                        platform,
                        item.get("type", "comment"),
                        ext_id,
                        item.get("user_id", ""),
                        item.get("username", "user"),
                        item.get("media_id", ""),
                        item.get("text", ""),
                        category,
                        decision["priority_rank"],
                        decision["public_reply"],
                        decision["dm_reply"],
                        inbox_status,
                        now.isoformat(),
                    ),
                )

                if should_auto_send:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO reply_log (
                            rule_id, account_id, platform, comment_id, media_id,
                            user_id, username, comment_text, category, public_text,
                            dm_text, status, release_at, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?, ?)
                        """,
                        (
                            decision.get("matched_rule_id"),
                            acc_id,
                            platform,
                            ext_id,
                            item.get("media_id", ""),
                            item.get("user_id", ""),
                            item.get("username", "user"),
                            item.get("text", ""),
                            category,
                            decision["public_reply"],
                            decision["dm_reply"],
                            release_time,
                            now.isoformat(),
                            now.isoformat(),
                        ),
                    )
                    summary["auto_replied_count"] += 1
                else:
                    summary["queued_for_approval"] += 1

            summary["new_comments_processed"] += 1

        # Update account sync timestamp
        with database.get_conn() as conn:
            conn.execute(
                "UPDATE accounts SET last_sync_ts = ? WHERE id = ?",
                (now.isoformat(), acc_id),
            )

    database.log_activity(
        "catchup_complete",
        f"Trigger={trigger_source} | RecoveredPosts={summary['recovered_posts']} | "
        f"NewComments={summary['new_comments_processed']} | AutoQueued={summary['auto_replied_count']} | "
        f"NeedsApproval={summary['queued_for_approval']}",
    )
    return summary


def scan_targets_with_agent_reach() -> Dict[str, Any]:
    """
    Uses Agent-Reach Bridge to read posts from target accounts/keywords,
    scores their Viral Outlier Multiplier (>3x), and drafts smart human comments (`/ig-comment`).
    """
    if not is_online():
        return {"ok": False, "scanned": 0}

    with database.get_conn() as conn:
        targets = [dict(r) for r in conn.execute("SELECT * FROM targets WHERE active = 1").fetchall()]
        accounts = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM accounts WHERE active = 1").fetchall()}

    scanned_posts = 0
    drafted_comments = 0
    now = database.now_iso()

    for t in targets:
        items = reach_bridge.search_platform(t["platform"], t["target_handle"], limit=3)
        for post in items:
            scanned_posts += 1
            post_id = str(post.get("id") or f"{t['platform']}_{abs(hash(post.get('text', ''))) % 999999}")
            views = int(post.get("views") or 3000)
            viral_info = viral_scorer.calculate_outlier_multiplier(views, t.get("median_views") or 1000)

            acc_id = t.get("account_id") or ( next(iter(accounts.keys()), 0) )
            comment_res = comment_classifier.generate_smart_target_comment(
                target_username=t["target_handle"],
                post_text=post.get("text", ""),
                account_id=acc_id,
            )
            if not comment_res.get("comment"):
                continue

            acc_row = accounts.get(acc_id, {})
            mode = get_effective_mode(acc_row)
            initial_status = "approved" if mode == "FULL_AUTO" else "pending"

            with database.get_conn() as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO comment_queue (
                        account_id, platform, target_username, post_id, post_url,
                        post_text, post_views, outlier_multiplier, comment_archetype,
                        proposed_comment, humanizer_score, status, release_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        acc_id,
                        t["platform"],
                        t["target_handle"],
                        post_id,
                        post.get("url", ""),
                        post.get("text", "")[:1000],
                        views,
                        viral_info["outlier_multiplier"],
                        comment_res["archetype"],
                        comment_res["comment"],
                        comment_res["humanizer_score"],
                        initial_status,
                        now,
                        now,
                    ),
                )
                drafted_comments += 1

        with database.get_conn() as conn:
            conn.execute("UPDATE targets SET last_scanned_at = ? WHERE id = ?", (now, t["id"]))

    return {"ok": True, "scanned_posts": scanned_posts, "drafted_comments": drafted_comments}
