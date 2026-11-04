#!/data/data/com.termux/files/usr/bin/bash
set -e
echo "=========================================================="
echo "🚀 Installing Nexus Social Automation v2.0 in Termux..."
echo "=========================================================="

pkg update -y && pkg upgrade -y
pkg install -y python ffmpeg git curl libjpeg-turbo libcrypt clang rust make

pip install --upgrade pip
pip install -r requirements.txt

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
