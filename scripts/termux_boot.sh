#!/data/data/com.termux/files/usr/bin/sh
termux-wake-lock
cd ~/nexus-social-automation || exit 0
nohup python3 app.py > ~/.nexus_social/boot.log 2>&1 &
