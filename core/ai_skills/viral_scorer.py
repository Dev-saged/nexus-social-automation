"""
Viral Outlier Scorer (`/ig-viral`) & Trial Reels Loop Engine (Nadr.ai).
Formula: Outlier Multiplier = Reel/Post Views ÷ Account Median Views.
Any post with Multiplier >= 3.0x is flagged as a strong viral signal.
Also generates 3 Trial Reel variations for winning videos.
"""
from typing import Any, Dict, List
from core.ai_skills import hooks_library, humanizer, voice_profile
from core.ai_router import router


def calculate_outlier_multiplier(post_views: int, account_median_views: int) -> Dict[str, Any]:
    median = max(1, account_median_views)
    multiplier = round(post_views / median, 2)
    is_viral_winner = multiplier >= 3.0
    tier = (
        "🔥 فايرال استثنائي (>5x)" if multiplier >= 5.0
        else "✅ فائز قوي (>3x)" if multiplier >= 3.0
        else "📈 أعلى من المتوسط (1.5x-3x)" if multiplier >= 1.5
        else "⚪ عادي (<1.5x)"
    )
    return {
        "post_views": post_views,
        "account_median_views": median,
        "outlier_multiplier": multiplier,
        "is_viral_winner": is_viral_winner,
        "tier": tier,
    }


def generate_trial_reel_variants(
    original_script: str,
    topic: str,
    account_id: int = 0,
) -> Dict[str, Any]:
    """
    Implements the Nadr.ai Trial Reels Weekly Loop:
    Creates 3 distinct variations of a winning reel to test on non-followers:
    1. Version A: New Hook (different formula from the 26 templates)
    2. Version B: Different Opening Visual Shot & pacing
    3. Version C: 30% Shorter, ultra-dense cut
    """
    sys_prompt = voice_profile.build_voice_system_prompt(account_id)
    prompt = (
        f"لدينا هذا الريل الفائز حول موضوع ({topic}):\n"
        f"{original_script}\n\n"
        f"أنتج 3 نسخ تجريبية (Trial Reels) مختلفة فعلياً لغير المتابعين بصيغة JSON يحتوي على المفاتيح:\n"
        f"- variant_new_hook: نسخة بهوك افتتاحي جديد تماماً وجذاب\n"
        f"- variant_new_shot: نسخة بلقطة بصرية أولى مختلفة وزاوية طرح جديدة\n"
        f"- variant_shorter_30: نسخة مختصرة بنسبة 30% أسرع وأكثر تكثيفاً\n"
        f"- recommended_schedule_days: قائمة بـ 3 أيام وأوقات مختلفة لنشر النسخ الثلاث"
    )
    res = router.generate_text(prompt, system_prompt=sys_prompt, task_type="arabic_creative", json_mode=True)
    return {
        "ok": res["ok"],
        "provider": res.get("provider", ""),
        "variants_raw": res.get("text", ""),
    }
