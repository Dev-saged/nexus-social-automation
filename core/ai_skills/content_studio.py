"""
Complete 13-Skill Content Studio from Instagram Agent (Nadr.ai / Jakeschincariol):
- `/ig-reel`: 3 scored hooks from 26 templates + script + on-screen text + timed beat sheet
- `/ig-caption`: Caption with 125-char pre-fold linter + 1 clear CTA + 3-5 hashtags
- `/ig-carousel`: 7-10 slide 1080x1350 breakdown
- `/ig-story`: Frame-by-frame daily story sequence + sticker & DM trigger
- `/ig-repurpose`: Turns a YouTube transcript or long article into a full week of Reels & posts
- `/ig-plan`: Weekly content & engagement plan
- `/ig-profile`: 100-point 12-criterion bio/profile scorer
- `/ig-audit`: Post-mortem performance analyzer (3s swipe-away, watch time, sends/reach)
"""
from typing import Any, Dict, Optional
from core.ai_router import router
from core.ai_skills import hooks_library, humanizer, voice_profile


def lint_caption(caption_text: str, cta_keyword: str = "تفاصيل") -> Dict[str, Any]:
    """Lints an Instagram/LinkedIn/TikTok caption focusing on the first 125 visible characters."""
    cleaned_info = humanizer.clean_and_humanize(caption_text)
    cleaned = cleaned_info["cleaned_text"]
    first_line = cleaned.split("\n")[0].strip() if cleaned else ""
    pre_fold_125 = cleaned[:125]
    hashtags = [w for w in cleaned.split() if w.startswith("#")]

    warnings = []
    if len(first_line) > 125:
        warnings.append("السطر الأول أطول من 125 حرفاً؛ سينقطع قبل كلمة '...المزيد'")
    if len(hashtags) > 5:
        warnings.append(f"عدد الهاشتاجات ({len(hashtags)}) أكثر من الحد المثالي (3-5)")
    if cta_keyword and cta_keyword not in cleaned:
        warnings.append(f"الكلمة المفتاحية للدعوة للتفاعل ('{cta_keyword}') غير موجودة بوضوح في النص")

    return {
        "cleaned_caption": cleaned,
        "first_125_chars": pre_fold_125,
        "first_line_length": len(first_line),
        "hashtag_count": len(hashtags),
        "humanizer_score": cleaned_info["score"],
        "warnings": warnings,
        "passed": len(warnings) == 0,
    }


def run_skill(
    skill_name: str,
    topic_or_input: str,
    account_id: Optional[int] = None,
    extra_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Unified dispatcher for all 13 Instagram & Social Agent skills."""
    extra = extra_params or {}
    sys_prompt = voice_profile.build_voice_system_prompt(account_id)
    vp = voice_profile.get_voice_profile(account_id)

    skill_prompts = {
        "ig-reel": (
            f"نفّذ مهارة (/ig-reel) لتحويل هذه الفكرة إلى ريل كامل مدته {extra.get('duration', 45)} ثانية:\n"
            f"الفكرة: {topic_or_input}\n\n"
            f"المطلوب بالترتيب:\n"
            f"1. 3 هوكات مختلفة مقتبسة من قوالب الفايرال الـ 26 مع تقييم كل هوك من 100.\n"
            f"2. السكريبت المنطوق كاملاً بلهجتي.\n"
            f"3. النص المكتوب على الشاشة (On-Screen Text) لكل لقطة.\n"
            f"4. جدول التوقيت بالثواني (Timed Beat Sheet: 0-3s, 3-15s, 15-35s, CTA).\n"
            f"5. دعوة واضحة في النهاية للتعليق بكلمة ({vp['default_cta_keyword']})."
        ),
        "ig-caption": (
            f"نفّذ مهارة (/ig-caption) لكتابة كابشن احترافي لهذا الموضوع أو السكريبت:\n"
            f"{topic_or_input}\n\n"
            f"القيود:\n"
            f"- السطر الأول أقل من 125 حرفاً ليظهر كاملاً قبل '...المزيد'.\n"
            f"- فقرات قصيرة مريحة للعين.\n"
            f"- دعوة واحدة واضحة للتعليق بكلمة ({vp['default_cta_keyword']}).\n"
            f"- من 3 إلى 5 هاشتاجات دقيقة فقط في النهاية."
        ),
        "ig-carousel": (
            f"نفّذ مهارة (/ig-carousel) لتحويل هذه الفكرة إلى كاروسيل من 7 شرائح بمقاس 1080x1350:\n"
            f"الفكرة: {topic_or_input}\n"
            f"اكتب نص الغلاف (الشريحة 1) بحيث يجبر القارئ على السحب، ثم نص كل شريحة (2-6) بتركيز شديد، والشريحة 7 للـ CTA."
        ),
        "ig-story": (
            f"نفّذ مهارة (/ig-story) لبناء سلسلة ستوريات اليوم (5 ستوريات متتابعة فريم بفريم) حول:\n"
            f"{topic_or_input}\n"
            f"حدد لكل ستوري: نوع اللقطة، النص المكتوب، أي ملصق تفاعلي نستخدم (Poll / Question / Slider)، وستوري التحويل للخاص (DM)."
        ),
        "ig-repurpose": (
            f"نفّذ مهارة (/ig-repurpose) لإعادة تدوير هذا المحتوى الطويل (نص فيديو يوتيوب أو مقال) إلى خطة أسبوع كامل:\n"
            f"{topic_or_input[:3500]}\n\n"
            f"استخرج منه: 4 أفكار ريلز بهوكاتها، 2 كاروسيل، و3 منشورات نصية لمنصات LinkedIn وX وThreads."
        ),
        "ig-plan": (
            f"نفّذ مهارة (/ig-plan) لترتيب خطة الأسبوع القادم لهدفي: {topic_or_input}.\n"
            f"حدد جدول الأيام (الأحد إلى السبت)، نوع المحتوى لكل يوم، وأنماط الحسابات الـ 10 التي يجب التفاعل معها يومياً."
        ),
        "ig-profile": (
            f"نفّذ مهارة (/ig-profile) لتقييم هذا البروفايل من 100 عبر 12 معياراً، ثم أعد كتابة الأجزاء الضعيفة (الاسم، البايو، الرابط، المثبتات):\n"
            f"{topic_or_input}"
        ),
        "ig-audit": (
            f"نفّذ مهارة (/ig-audit) لتحليل أرقام الأداء التالية (ركز على نسبة التخطي في أول 3 ثوانٍ، متوسط المشاهدة، الإرسال Shares، والحفظ Saves):\n"
            f"{topic_or_input}\n"
            f"حدد ماذا نكرر وماذا نوقف فوراً للأسبوع القادم."
        ),
    }

    prompt = skill_prompts.get(skill_name, f"نفّذ مهارة {skill_name} على: {topic_or_input}")
    res = router.generate_text(prompt, system_prompt=sys_prompt, task_type="arabic_creative")
    cleaned = humanizer.clean_and_humanize(res.get("text", ""))
    output: Dict[str, Any] = {
        "ok": res["ok"],
        "skill": skill_name,
        "provider": res.get("provider", ""),
        "latency_ms": res.get("latency_ms", 0),
        "content": cleaned["cleaned_text"],
        "humanizer_score": cleaned["score"],
        "removed_ai_fingerprints": cleaned["removed_items"],
    }
    if skill_name == "ig-caption":
        output["caption_lint"] = lint_caption(cleaned["cleaned_text"], vp["default_cta_keyword"])
    return output
