"""
Comment Classifier (`/ig-reply`) and Smart Human Target Commenter (`/ig-comment`).
1. `/ig-reply`: Classifies incoming comments under the user's posts into 6 priority tiers:
   [1] KEYWORD, [2] LEAD, [3] SUBSTANCE, [4] QUESTION, [5] SUPPORT, [6] NOISE.
2. `/ig-comment`: Generates high-value, human-sounding comments on other accounts' posts
   discovered via Agent-Reach using 9 distinct archetypes (never generic "🔥🔥🔥").
"""
import json
from typing import Any, Dict, Optional
from core import arabic_matcher
from core.ai_router import router
from core.ai_skills import humanizer, voice_profile

COMMENT_ARCHETYPES = [
    ("counter_insight", "إضافة زاوية مكملة أو استثناء عملي يثري البوست"),
    ("experience_share", "مشاركة تجربة شخصية سريعة مؤيدة للفكرة"),
    ("tactical_question", "إشادة محددة بنقطة في البوست متبوعة بسؤال ذكي يفتح نقاشاً"),
    ("step_addition", "إضافة خطوة عملية أو أداة مجانية تكمل ما ذكره الكاتب"),
    ("nuance_builder", "توضيح الفرق بين حالتين لتعميق الفائدة للقراء في التعليقات"),
    ("case_validation", "تأكيد الفكرة بمثال واقعي ملموس"),
    ("friendly_challenge", "نقاش ودي محترم يطرح وجهة نظر بديلة تجذب الانتباه"),
    ("summary_gem", "تلخيص أقوى نقطة في البوست في جملة ذهبية خاطفة"),
    ("witty_observation", "ملاحظة ذكية خفيفة الظل ومرتبطة بصلب الموضوع"),
]


def classify_and_draft_reply(
    comment_text: str,
    sender_username: str,
    post_context: str = "",
    account_id: Optional[int] = None,
    keyword_rules: Optional[list] = None,
) -> Dict[str, Any]:
    """
    First checks deterministic Arabic keyword rules (Bulldozer OpenReply).
    If no exact keyword rule matches, uses fast AI classification (`/ig-reply`)
    into LEAD / QUESTION / SUBSTANCE / SUPPORT / NOISE.
    """
    if keyword_rules:
        for rule in keyword_rules:
            kws = [k.strip() for k in (rule.get("keywords") or "").split(",") if k.strip()]
            matched, kw = arabic_matcher.match_keywords(
                comment_text,
                kws,
                whole_word=bool(rule.get("whole_word")),
                any_comment=bool(rule.get("any_comment")),
            )
            if matched:
                replies = [r.strip() for r in (rule.get("public_replies") or "").split("|") if r.strip()]
                pub_reply = replies[0] if replies else f"تم إرسال التفاصيل لك في الخاص يا @{sender_username} ✨"
                return {
                    "category": "KEYWORD",
                    "priority_rank": 1,
                    "matched_rule_id": rule.get("id"),
                    "matched_keyword": kw,
                    "public_reply": pub_reply,
                    "dm_reply": rule.get("dm_text", ""),
                    "dm_link": rule.get("dm_link", ""),
                    "require_follower": bool(rule.get("require_follower")),
                    "provider": "arabic_matcher_local",
                }

    # AI Classification (/ig-reply)
    sys_prompt = voice_profile.build_voice_system_prompt(account_id)
    prompt = (
        f"صنّف هذا التعليق الوارد على حسابي واكتب رداً مناسباً بلهجتي.\n"
        f"صاحب التعليق: @{sender_username}\n"
        f"نص التعليق: \"{comment_text}\"\n"
        f"سياق المنشور: \"{post_context}\"\n\n"
        f"أجب بصيغة JSON فقط يحتوي على:\n"
        f"- category: اختر واحداً فقط من (LEAD / QUESTION / SUBSTANCE / SUPPORT / NOISE)\n"
        f"- priority_rank: رقم من 2 إلى 6 (2 للعميل المحتمل LEAD، 3 للنقاش، 4 للسؤال، 5 للدعم، 6 للضوضاء/السبام)\n"
        f"- public_reply: الرد العام تحت التعليق (مختصر وطبيعي جداً)\n"
        f"- dm_reply: رسالة خاصة مقترحة إذا كان LEAD أو QUESTION يحتاج تفصيلاً (أو نص فارغ)"
    )
    res = router.generate_text(prompt, system_prompt=sys_prompt, task_type="fast_classify", json_mode=True)
    if res["ok"]:
        try:
            parsed = json.loads(res["text"])
            pub_clean = humanizer.clean_and_humanize(parsed.get("public_reply", ""))["cleaned_text"]
            dm_clean = humanizer.clean_and_humanize(parsed.get("dm_reply", ""))["cleaned_text"]
            return {
                "category": parsed.get("category", "SUPPORT"),
                "priority_rank": int(parsed.get("priority_rank", 4)),
                "matched_rule_id": None,
                "public_reply": pub_clean,
                "dm_reply": dm_clean,
                "dm_link": "",
                "require_follower": False,
                "provider": res["provider"],
            }
        except Exception:
            pass

    return {
        "category": "SUPPORT",
        "priority_rank": 5,
        "matched_rule_id": None,
        "public_reply": f"شكراً لمرورك وتفاعلك القيم يا @{sender_username}!",
        "dm_reply": "",
        "dm_link": "",
        "require_follower": False,
        "provider": "fallback_local",
    }


def generate_smart_target_comment(
    target_username: str,
    post_text: str,
    archetype_key: str = "counter_insight",
    account_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Implements `/ig-comment`: Crafts a thoughtful, human opinion comment on a target account's post
    discovered by Agent-Reach so their audience notices and visits your profile.
    """
    archetype_desc = dict(COMMENT_ARCHETYPES).get(archetype_key, COMMENT_ARCHETYPES[0][1])
    sys_prompt = voice_profile.build_voice_system_prompt(account_id)
    prompt = (
        f"اكتب تعليقاً ذكياً وطبيعياً جداً على هذا المنشور لحساب (@{target_username}) في مجالي:\n"
        f"نص المنشور: \"{post_text[:1200]}\"\n\n"
        f"نوع التعليق المطلوب ({archetype_key}): {archetype_desc}.\n"
        f"شروط صارمة:\n"
        f"1. من جملتين إلى 3 جمل كحد أقصى.\n"
        f"2. يبدو من إنسان خبير قرأ البوست فعلاً وعنده رأي، وممنوع التعليقات السطحية مثل 'رائع 🔥'.\n"
        f"3. بدون هاشتاجات وبدون روابط وبدون شرطات طويلة (—)."
    )
    res = router.generate_text(prompt, system_prompt=sys_prompt, task_type="arabic_creative")
    cleaned = humanizer.clean_and_humanize(res.get("text", ""))
    return {
        "ok": res["ok"],
        "archetype": archetype_key,
        "comment": cleaned["cleaned_text"],
        "humanizer_score": cleaned["score"],
        "provider": res.get("provider", ""),
    }
