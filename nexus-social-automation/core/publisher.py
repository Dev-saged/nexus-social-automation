"""
Multi-Platform Publisher & Throttled Reply Dispatcher (`core/publisher.py`).
Includes:
- Exponential Backoff `[60, 300, 900, 3600, 10800]` from `Dev-saged/social-manager`
- Network check before publishing (`waiting_network` state if offline)
- Automatic video uniquification per target account when enabled
- Execution of queued Comment-to-DM replies & Target Engagement comments
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import config
from core import catchup_sync, database, media_factory
from platforms import get_adapter

BACKOFF_SECONDS = config.SCHEDULER_CONFIG["retry_backoff_seconds"]


def run_due_posts() -> Dict[str, int]:
    now = datetime.now(timezone.utc)
    now_str = now.isoformat()

    if not catchup_sync.is_online():
        with database.get_conn() as conn:
            conn.execute(
                "UPDATE post_targets SET status='waiting_network', updated_at=? "
                "WHERE status='pending' AND due_at <= ?",
                (now_str, now_str),
            )
        return {"published": 0, "failed": 0, "waiting_network": 1}

    with database.get_conn() as conn:
        due_rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT pt.*, pg.text as base_text, pg.media_id, pg.media_kind, pg.is_trial_reel
                FROM post_targets pt
                JOIN post_groups pg ON pg.id = pt.group_id
                WHERE pt.status IN ('pending', 'waiting_network')
                  AND COALESCE(pt.next_try_at, pt.due_at) <= ?
                ORDER BY pt.due_at ASC
                LIMIT 10
                """,
                (now_str,),
            ).fetchall()
        ]

    published_cnt = 0
    failed_cnt = 0

    for pt in due_rows:
        acc_id = pt["account_id"]
        if not database.check_rate_limit(acc_id, "publish"):
            continue

        with database.get_conn() as conn:
            acc = conn.execute("SELECT * FROM accounts WHERE id = ?", (acc_id,)).fetchone()
            media_row = (
                conn.execute("SELECT * FROM media_vault WHERE id = ?", (pt["media_id"],)).fetchone()
                if pt.get("media_id")
                else None
            )

        if not acc:
            continue

        acc_dict = dict(acc)
        creds = database.decrypt_credentials(acc_dict["credentials"])
        adapter = get_adapter(pt["platform"], creds, acc_dict)

        text_to_send = pt.get("text_override") or pt["base_text"]
        media_path = pt.get("media_path_override") or (media_row["original_path"] if media_row else "")

        # If video and auto_uniquify is active, produce a unique hash for this target
        if media_path and pt.get("media_kind") == "video" and database.get_setting("auto_uniquify_video", "1") == "1":
            u_res = media_factory.uniquify_video(media_path)
            if u_res.get("ok"):
                media_path = u_res["output_path"]

        res = adapter.publish_post(
            text=text_to_send,
            media_path=media_path,
            media_kind=pt.get("media_kind", "none"),
            extra={"is_trial_reel": bool(pt.get("is_trial_reel"))},
        )

        if res.get("ok"):
            published_cnt += 1
            database.record_rate_event(acc_id, "publish")
            with database.get_conn() as conn:
                conn.execute(
                    "UPDATE post_targets SET status='published', remote_id=?, error='', updated_at=? WHERE id=?",
                    (res.get("remote_id", ""), now_str, pt["id"]),
                )
            database.log_activity("publish_ok", f"Published target #{pt['id']} on {pt['platform']}", platform=pt["platform"])
        else:
            failed_cnt += 1
            attempts = int(pt.get("attempts") or 0) + 1
            if attempts <= len(BACKOFF_SECONDS):
                delay = BACKOFF_SECONDS[attempts - 1]
                next_try = (now + timedelta(seconds=delay)).isoformat()
                new_status = "pending"
            else:
                next_try = None
                new_status = "failed"
            with database.get_conn() as conn:
                conn.execute(
                    "UPDATE post_targets SET status=?, attempts=?, next_try_at=?, error=?, updated_at=? WHERE id=?",
                    (new_status, attempts, next_try, res.get("error", "")[:400], now_str, pt["id"]),
                )
            database.log_activity("publish_err", f"Failed target #{pt['id']}: {res.get('error', '')}", platform=pt["platform"], ok=False)

    return {"published": published_cnt, "failed": failed_cnt, "waiting_network": 0}


def run_due_replies_and_comments() -> Dict[str, int]:
    """Dispatches due Comment-to-DM replies and approved Target Engagement comments."""
    if not catchup_sync.is_online():
        return {"replies_sent": 0, "target_comments_sent": 0}

    now_str = database.now_iso()
    replies_sent = 0
    target_comments_sent = 0

    with database.get_conn() as conn:
        due_replies = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM reply_log WHERE status='queued' AND release_at <= ? ORDER BY release_at ASC LIMIT 8",
                (now_str,),
            ).fetchall()
        ]
        due_engagements = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM comment_queue WHERE status='approved' AND COALESCE(release_at, created_at) <= ? LIMIT 5",
                (now_str,),
            ).fetchall()
        ]

    for rep in due_replies:
        acc_id = rep["account_id"]
        if not database.check_rate_limit(acc_id, "comment_reply"):
            continue
        with database.get_conn() as conn:
            acc = conn.execute("SELECT * FROM accounts WHERE id=?", (acc_id,)).fetchone()
        if not acc:
            continue
        adapter = get_adapter(rep["platform"], database.decrypt_credentials(acc["credentials"]), dict(acc))
        pub_ok = True
        if rep.get("public_text"):
            r_pub = adapter.reply_to_comment(rep["comment_id"], rep["public_text"], rep.get("media_id", ""))
            pub_ok = bool(r_pub.get("ok"))
        dm_ok = True
        if rep.get("dm_text") and rep.get("user_id"):
            r_dm = adapter.send_dm(rep["user_id"], rep["dm_text"])
            dm_ok = bool(r_dm.get("ok"))

        with database.get_conn() as conn:
            conn.execute(
                "UPDATE reply_log SET public_status=?, dm_status=?, status=?, updated_at=? WHERE id=?",
                (
                    "sent" if pub_ok else "failed",
                    "sent" if dm_ok else "failed",
                    "completed" if (pub_ok and dm_ok) else "partial",
                    now_str,
                    rep["id"],
                ),
            )
        database.record_rate_event(acc_id, "comment_reply")
        replies_sent += 1

    for eng in due_engagements:
        acc_id = eng["account_id"]
        if not database.check_rate_limit(acc_id, "target_engage"):
            continue
        with database.get_conn() as conn:
            acc = conn.execute("SELECT * FROM accounts WHERE id=?", (acc_id,)).fetchone()
        if not acc:
            continue
        adapter = get_adapter(eng["platform"], database.decrypt_credentials(acc["credentials"]), dict(acc))
        res = adapter.reply_to_comment(eng["post_id"], eng["proposed_comment"])
        with database.get_conn() as conn:
            conn.execute(
                "UPDATE comment_queue SET status=?, posted_at=?, error=? WHERE id=?",
                ("posted" if res.get("ok") else "failed", now_str, res.get("error", ""), eng["id"]),
            )
        database.record_rate_event(acc_id, "target_engage")
        target_comments_sent += 1

    return {"replies_sent": replies_sent, "target_comments_sent": target_comments_sent}
