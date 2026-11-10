#!/usr/bin/env bash
REPO_URL=${1:-"https://github.com/Dev-saged/nexus-social-automation.git"}
git init
git branch -M main
git add .
git commit -m "feat: complete Nexus Social Automation v2.0 (12 platforms, 9 free AI providers, Offline Catch-Up, Native Java APK)"
git remote remove origin 2>/dev/null || true
git remote add origin "$REPO_URL"
git push -u origin main
echo "✅ Pushed to $REPO_URL! Open the 'Actions' tab on GitHub to download your compiled APK."
