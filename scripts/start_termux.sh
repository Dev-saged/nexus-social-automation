#!/data/data/com.termux/files/usr/bin/bash
cd "$(dirname "$0")/.."
if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock
fi
echo "🚀 Starting Nexus Social Automation Core on http://127.0.0.1:5050 ..."
python3 app.py
