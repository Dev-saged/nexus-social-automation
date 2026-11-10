#!/data/data/com.termux/files/usr/bin/bash
echo "=========================================================="
echo "🚀 Installing Nexus Social Automation v2.0 in Termux..."
echo "=========================================================="

pkg update -y
pkg install -y python python-pip python-cryptography python-pillow ffmpeg git curl

# Do NOT run 'pip install --upgrade pip' on Termux (forbidden by Termux python-pip)
pip install requests python-dotenv tweepy tzdata yt-dlp edge-tts gTTS flask apscheduler || true

echo "[*] Installing Agent-Reach CLI..."
pip install https://github.com/Panniantong/Agent-Reach/releases/latest/download/agent-reach.zip || true

if [ ! -f .env ]; then
    cp .env.example .env
    echo "[+] Created .env from .env.example"
fi

mkdir -p ~/.termux/boot
cp scripts/termux_boot.sh ~/.termux/boot/start_nexus_social.sh
chmod +x ~/.termux/boot/start_nexus_social.sh
chmod +x scripts/*.sh

echo "✅ Installation Complete! Run: bash scripts/start_termux.sh"
