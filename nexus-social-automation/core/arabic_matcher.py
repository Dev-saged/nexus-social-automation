"""
Arabic-Aware Keyword Matcher (Ported and enhanced from Dev-saged/bulldozer-social
`libraries/helpers/src/utils/keyword.matcher.ts`).
Handles all Arabic orthography variations in social media comments & DMs:
- Alef/Hamza normalization (أ إ آ ٱ -> ا)
- Teh Marbuta to Heh (ة -> ه)
- Alef Maqsura & Persian Yeh to Arabic Yeh (ى ی ئ -> ي)
- Persian/Urdu Kaf to Arabic Kaf (ک -> ك)
- Strips Arabic diacritics (Tashkeel) and Tatweel/Kashida (ـ)
- Converts Eastern Arabic (٠-٩) & Persian (۰-۹) digits to Western (0-9)
"""
import re
from typing import Iterable, List, Optional, Tuple

# Unicode ranges for Arabic diacritics (Tashkeel) + Tatweel
_DIACRITICS_RE = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")
_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)

_CHAR_MAP = str.maketrans({
    # Alef variants
    "أ": "ا",
    "إ": "ا",
    "آ": "ا",
    "ٱ": "ا",
    "ؤ": "و",
    # Teh Marbuta -> Heh
    "ة": "ه",
    # Yeh variants
    "ى": "ي",
    "ی": "ي",
    "ئ": "ي",
    # Kaf variants
    "ک": "ك",
    "گ": "ك",
    # Eastern Arabic digits (٠-٩)
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
    # Persian/Extended Arabic digits (۰-۹)
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
    "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
})


def normalize_arabic(text: str) -> str:
    """Normalizes Arabic and English text for resilient keyword matching."""
    if not text:
        return ""
    cleaned = _DIACRITICS_RE.sub("", text.strip().lower())
    cleaned = cleaned.translate(_CHAR_MAP)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned)
    return cleaned.strip()


def match_keywords(
    comment_text: str,
    keywords: Iterable[str],
    whole_word: bool = False,
    any_comment: bool = False,
) -> Tuple[bool, Optional[str]]:
    """
    Checks if `comment_text` matches any of `keywords` after full Arabic normalization.
    Returns (is_match, matched_keyword).
    """
    if not comment_text or not comment_text.strip():
        return False, None

    if any_comment:
        return True, "*"

    norm_comment = normalize_arabic(comment_text)
    comment_no_punct = _PUNCT_RE.sub(" ", norm_comment)
    comment_tokens = set(comment_no_punct.split())

    for raw_kw in keywords:
        if not raw_kw or not raw_kw.strip():
            continue
        norm_kw = normalize_arabic(raw_kw)
        if not norm_kw:
            continue

        if whole_word:
            kw_tokens = _PUNCT_RE.sub(" ", norm_kw).split()
            if len(kw_tokens) == 1:
                if kw_tokens[0] in comment_tokens:
                    return True, raw_kw
            else:
                pattern = r"(?<!\w)" + re.escape(norm_kw) + r"(?!\w)"
                if re.search(pattern, comment_no_punct):
                    return True, raw_kw
        else:
            if norm_kw in norm_comment or norm_kw in comment_no_punct:
                return True, raw_kw

    return False, None
