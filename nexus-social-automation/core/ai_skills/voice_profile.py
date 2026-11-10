"""
Voice Profile Manager (`voice.md` equivalent per account from Instagram Agent Nadr.ai).
Ensures every generated post, reel script, comment, and DM sounds genuinely like the user.
"""
import json
from typing import Any, Dict, Optional
from core import database


def get_voice_profile(account_id: Optional[int]) -> Dict[str, Any]:
    default_profile = {
        "account_id": account_id or 0,
        "dialect": "عربية طبيعية واضحة قريبة من الناس بدون تكلف",
        "persona_summary": "صانع محتوى ورائد أعمال تقني يشارك خبرات عملية حقيقية",
        "target_audience": "أصحاب المشاريع والمهتمين بالتقنية والأتمتة والنمو الرقمي",
        "offer_and_price": "",
        "camera_style": "سريع، مباشر، عملي بدون مقدمات طويلة",
        "signature_words": ["بالمختصر", "الخلاصة", "خطوة بخطوة"],
        "forbidden_words": ["في عالمنا المتسارع", "مما لا شك فيه", "ثورة حقيقية", "سحر الذكاء الاصطناعي"],
        "emoji_density": "قليل",
        "bold_opinions": ["الأدوات البسيطة التي تعمل على جوالك أفضل من الأنظمة المعقدة المكلفة"],
        "verified_proofs": [],
        "default_cta_keyword": "تفاصيل",
        "bio_link_target": "",
    }
    if not account_id:
        return default_profile

    with database.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM account_voice_profiles WHERE account_id = ?", (account_id,)
        ).fetchone()
        if not row:
            return default_profile
        d = dict(row)
        for list_key in ("signature_words", "forbidden_words", "bold_opinions", "verified_proofs"):
            try:
                d[list_key] = json.loads(d.get(list_key) or "[]")
            except Exception:
                d[list_key] = []
        return d


def save_voice_profile(account_id: int, payload: Dict[str, Any]):
    current = get_voice_profile(account_id)
    current.update(payload)
    with database.get_conn() as conn:
        conn.execute(
            """
            INSERT INTO account_voice_profiles (
                account_id, dialect, persona_summary, target_audience, offer_and_price,
                camera_style, signature_words, forbidden_words, emoji_density,
                bold_opinions, verified_proofs, default_cta_keyword, bio_link_target, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(account_id) DO UPDATE SET
                dialect=excluded.dialect,
                persona_summary=excluded.persona_summary,
                target_audience=excluded.target_audience,
                offer_and_price=excluded.offer_and_price,
                camera_style=excluded.camera_style,
                signature_words=excluded.signature_words,
                forbidden_words=excluded.forbidden_words,
                emoji_density=excluded.emoji_density,
                bold_opinions=excluded.bold_opinions,
                verified_proofs=excluded.verified_proofs,
                default_cta_keyword=excluded.default_cta_keyword,
                bio_link_target=excluded.bio_link_target,
                updated_at=excluded.updated_at
            """,
            (
                account_id,
                current["dialect"],
                current["persona_summary"],
                current["target_audience"],
                current["offer_and_price"],
                current["camera_style"],
                json.dumps(current["signature_words"], ensure_ascii=False),
                json.dumps(current["forbidden_words"], ensure_ascii=False),
                current["emoji_density"],
                json.dumps(current["bold_opinions"], ensure_ascii=False),
                json.dumps(current["verified_proofs"], ensure_ascii=False),
                current["default_cta_keyword"],
                current["bio_link_target"],
                database.now_iso(),
            ),
        )


def build_voice_system_prompt(account_id: Optional[int]) -> str:
    vp = get_voice_profile(account_id)
    forbidden = "، ".join(vp["forbidden_words"]) if vp["forbidden_words"] else "الكليشيهات المستهلكة"
    sig = "، ".join(vp["signature_words"]) if vp["signature_words"] else "كلمات مباشرة"
    proofs = " | ".join(vp["verified_proofs"]) if vp["verified_proofs"] else "لا تخترع أرقاماً غير حقيقية، اترك الرقم فارغاً إن لم يتوفر"
    return (
        f"أنت تكتب نيابة عن صاحب الحساب وفق ملف بصمة الصوت (voice.md) التالي:\n"
        f"- الهوية والنبذة: {vp['persona_summary']}\n"
        f"- الجمهور المستهدف بدقة: {vp['target_audience']}\n"
        f"- اللهجة والأسلوب: {vp['dialect']} ({vp['camera_style']})\n"
        f"- كلمات معتادة: {sig}\n"
        f"- كلمات وعبارات ممنوعة تماماً: {forbidden}\n"
        f"- كثافة الإيموجي: {vp['emoji_density']}\n"
        f"- إثباتات حقيقية مسموح ذكرها (ممنوع اختراع أرقام): {proofs}\n"
        f"- الكلمة المفتاحية للدعوة للتفاعل (CTA): {vp['default_cta_keyword']}\n"
        f"التزم بهذه البصمة حرفياً ولا تستخدم شرطة طويلة (—) أو مقدمات إنشائية."
    )
