"""
AI Text Humanizer (`/ig-human` from Instagram Agent Nadr.ai).
Strips AI watermarks, invisible zero-width characters, em-dashes (—),
robotic Arabic/English transitions, and evaluates a 5-point human authenticity score.
"""
import re
from typing import Any, Dict, List

_ZERO_WIDTH_RE = re.compile(r"[\u200B-\u200D\uFEFF\u2060]")
_EM_DASH_RE = re.compile(r"\s*[—–]\s*")

_AI_SLOP_PHRASES_AR = [
    "في عالمنا المتسارع",
    "في عصر الرقمنة",
    "مما لا شك فيه",
    "تعد بمثابة",
    "سلاح ذو حدين",
    "نقلة نوعية",
    "ليس مجرد خيار بل ضرورة",
    "هل تساءلت يوماً",
    "في الختام يمكننا القول",
    "أفق جديد",
]

_AI_SLOP_PHRASES_EN = [
    "in today's fast-paced world",
    "delve into",
    "testament to",
    "game-changer",
    "unleash the power",
    "moreover",
    "tapestry",
    "elevate your",
    "it's not just about",
]


def clean_and_humanize(text: str) -> Dict[str, Any]:
    """
    Cleans text from AI fingerprints and returns a 5-check panel score out of 100.
    """
    if not text:
        return {"cleaned_text": "", "score": 0, "checks": {}, "removed_items": []}

    removed: List[str] = []
    cleaned = text

    # Check 1: Zero-width invisible watermark characters
    if _ZERO_WIDTH_RE.search(cleaned):
        removed.append("رموز مخفية (Zero-width characters)")
        cleaned = _ZERO_WIDTH_RE.sub("", cleaned)

    # Check 2: Em-dashes (—) and En-dashes (–)
    if _EM_DASH_RE.search(cleaned):
        removed.append("شرطات الذكاء الاصطناعي الطويلة (—)")
        cleaned = _EM_DASH_RE.sub("، ", cleaned)

    # Check 3: Arabic & English AI Slop Vocabulary
    for phrase in _AI_SLOP_PHRASES_AR + _AI_SLOP_PHRASES_EN:
        if phrase.lower() in cleaned.lower():
            removed.append(f"كليشيه مستهلك: '{phrase}'")
            cleaned = re.sub(re.escape(phrase), "", cleaned, flags=re.IGNORECASE)

    # Check 4: Excessive markdown bolding (**word**) inside social captions
    bold_count = len(re.findall(r"\*\*[^*]+\*\*", cleaned))
    if bold_count > 3:
        removed.append("تنسيق نجمات مفرط (**)")
        cleaned = cleaned.replace("**", "")

    # Normalize spacing
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    # 5-Check Authenticity Panel
    checks = {
        "no_invisible_chars": not bool(_ZERO_WIDTH_RE.search(cleaned)),
        "no_em_dashes": "—" not in cleaned and "–" not in cleaned,
        "no_slop_vocabulary": not any(p in cleaned.lower() for p in _AI_SLOP_PHRASES_AR + _AI_SLOP_PHRASES_EN),
        "natural_sentence_rhythm": 5 <= len(cleaned.split()) <= 450,
        "clean_formatting": "**" not in cleaned,
    }
    score = sum(20 for v in checks.values() if v)
    return {
        "cleaned_text": cleaned,
        "score": score,
        "checks": checks,
        "removed_items": removed,
    }
