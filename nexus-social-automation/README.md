# 🚀 Nexus Social Automation v2.0 (APK + Termux Offline-First Suite)

النظام المتكامل لأتمتة وإدارة حساباتك الخاصة عبر **12 منصة تواصل اجتماعي** من هاتفك المحمول مباشرة (**تطبيق أندرويد أصلي بـ Java + WebView Bridge** متصل بمحرك **Python Offline-First في Termux**)، مع دعم **9 مزودين مجانيين للذكاء الاصطناعي** وبروتوكول **الاستدراك التلقائي بعد انقطاع الإنترنت والكهرباء**.

## ✨ ماذا يدمج هذا المستودع؟

1. **نواة `Dev-saged/social-manager` المطورة**:
   - قاعدة بيانات `SQLite WAL` مقاومة لانقطاع الكهرباء (15 جدولاً) مع تشفير `Fernet` لبيانات الدخول.
   - مرحل GitHub للميديا (`core/relay.py`) لرفع الصور والفيديوهات والحصول على روابط HTTPS مباشرة لـ Meta/Instagram/Threads/Pinterest.
   - دعم كامل لـ **12 منصة**: `Instagram`, `Facebook`, `Threads` (نصوص + صور + فيديو), `X/Twitter`, `LinkedIn`, `TikTok`, `YouTube`, `Telegram`, `Bluesky` (ضغط صور تلقائي + فيديو), `Reddit`, `Pinterest`, `Mastodon`.
2. **محرك الرد العربي من `Dev-saged/bulldozer-social` (OpenReply)**:
   - خوارزمية المطابقة العربية الكاملة (`core/arabic_matcher.py`) لتوحيد الهمزات والتاء المربوطة والياء وإزالة التشكيل والأرقام المشرقية، والرد التلقائي (Comment-to-DM).
3. **عيون القراءة من `Panniantong/Agent-Reach` (`reach_bridge/dispatcher.py`)**:
   - قراءة بوستات الحسابات المستهدفة والترندات ونصوص فيديوهات يوتيوب بصفر تكلفة API ونظام بدائل مرتب (`agent-reach CLI` -> `yt-dlp` -> `Jina Reader`).
4. **عقل المحتوى والتفاعل من `Instagram Agent | Nadr.ai` (`core/ai_skills/`)**:
   - المهارات الـ 13 كاملة، شاملة: ملف البصمة الصوتية (`voice.md`)، مكتبة الـ 26 قالب هوك مقيّم (`hooks_library.py`)، حساب مضاعف الانتشار (`Outlier > 3x`)، حلقة الريلز التجريبية (`Trial Reels`)، مصنف التعليقات لـ 6 فئات (`/ig-reply`)، كاتب التعليقات البشرية من 9 أنماط (`/ig-comment`)، ومنظف بصمة الذكاء الاصطناعي (`/ig-human`).
5. **معمل الفيديو من `Katzca/AutoSocial` وأداة `LinkedIn Auto Publisher` (`core/media_factory.py`)**:
   - تفريد بصمة الفيديو بـ `FFmpeg Uniquify` لتغيير الـ Hash والألوان الخفيفة لمنع كشف التكرار.
   - توليد فيديو كامل (سكريبت + صوت بشري `Edge-TTS`/`gTTS` + مقاطع `Pexels` مع **فلتر تجنب النساء الصارم `Avoid-women filter`**).
   - جدولة تمويهية بنظام الانحراف العشوائي (`Jitter ±15m`) داخل نافذة النشاط اليومية.
6. **موزع الذكاء الاصطناعي لـ 9 مزودين مجانيين (`core/ai_router.py`)**:
   - يتنقل تلقائياً بين: `Google Gemini`, `Groq Cloud + Whisper`, `Cerebras`, `GitHub Models`, `OpenRouter Free`, `Cohere Arabic`, `Mistral AI`, `Cloudflare Workers AI + Flux`, و`Oxion + Pollinations Zero-Key`.

## 📱 خطوات التشغيل السريع على هاتفك (Termux + APK)

### أولاً: تشغيل المحرك في Termux
```bash
pkg install git -y
git clone https://github.com/Dev-saged/nexus-social-automation.git
cd nexus-social-automation
bash scripts/install_termux.sh
bash scripts/start_termux.sh
```

### ثانياً: استخراج تطبيق الـ APK عبر GitHub Actions (بدون كمبيوتر)
1. ارفع هذا المستودع إلى حسابك على GitHub عبر تشغيل:
   ```bash
   bash scripts/push_to_github.sh https://github.com/Dev-saged/nexus-social-automation.git
   ```
2. افتح تبويب **Actions** في مستودعك على GitHub من متصفح جوالك.
3. ستجد مهمة `Build Nexus Social Android APK` قد انتهت في دقيقتين؛ حمّل ملف `nexus-social-automation-apk` وثبّته على هاتفك.
