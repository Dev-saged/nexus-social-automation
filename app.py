#!/usr/bin/env python3
"""
Main Entrypoint for Nexus Social Automation (`app.py`).
Initializes SQLite WAL database, starts the Smart Anti-Ban & Catch-Up Scheduler,
runs an immediate startup Catch-Up sync if internet is available, and serves
the local Control Plane on `127.0.0.1:5050` for the Android APK.
"""
import config
from core import catchup_sync, database, scheduler
from core.server import app


def main():
    database.init_db()
    scheduler.start_scheduler()
    if catchup_sync.is_online():
        catchup_sync.run_catchup_cycle(trigger_source="termux_boot_startup")
    print(f"[*] Nexus Social Automation v2.0 running on http://{config.HOST}:{config.PORT}")
    app.run(host=config.HOST, port=config.PORT, debug=False, threaded=True)


if __name__ == "__main__":
    main()
