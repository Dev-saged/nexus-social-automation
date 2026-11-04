"""
Smart Anti-Ban Scheduler (`core/scheduler.py`).
Supports both APScheduler and a native Python stdlib `threading.Thread` daemon loop
so it runs reliably on Termux with zero external scheduler dependencies.
"""
import random
import threading
import time
from datetime import datetime, timedelta
from typing import List

from core import catchup_sync, database, publisher

_started = False
_stop_event = threading.Event()


def plan_daily_slots_with_jitter(base_slots: List[str], jitter_min: int = 15) -> List[str]:
    """
    Takes fixed slots like `['09:00', '14:00', '18:30']` and adds ±jitter_min random deviation
    so scheduled posts look 100% human (e.g., `09:11`, `13:49`, `18:42`).
    """
    planned = []
    today = datetime.now()
    for slot in base_slots:
        try:
            hh, mm = [int(x) for x in slot.strip().split(":")]
            dt = today.replace(hour=hh, minute=mm, second=random.randint(5, 55))
            deviation = random.randint(-jitter_min, jitter_min)
            dt_jittered = dt + timedelta(minutes=deviation)
            planned.append(dt_jittered.strftime("%H:%M"))
        except Exception:
            planned.append(slot)
    return sorted(planned)


def tick():
    """Main 60-second background loop in Termux."""
    try:
        publisher.run_due_posts()
        publisher.run_due_replies_and_comments()
    except Exception as exc:
        database.log_activity("scheduler_tick_error", str(exc), ok=False)


def _background_loop():
    ticks = 0
    while not _stop_event.is_set():
        tick()
        ticks += 1
        if ticks % 15 == 0:
            try:
                catchup_sync.run_catchup_cycle("periodic_15m")
            except Exception:
                pass
        _stop_event.wait(60.0)


def start_scheduler():
    global _started
    if _started:
        return
    _stop_event.clear()
    t = threading.Thread(target=_background_loop, name="NexusSmartScheduler", daemon=True)
    t.start()
    _started = True
    database.log_activity("scheduler_started", "Nexus Smart Scheduler & Catch-Up Engine started (60s daemon tick).")


def shutdown_scheduler():
    global _started
    _stop_event.set()
    _started = False
