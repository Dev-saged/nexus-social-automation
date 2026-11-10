"""
Automated Verification Suite for Nexus Social Automation v2.0.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from core import arabic_matcher, database, scheduler
from core.ai_skills import hooks_library, humanizer, viral_scorer
from core.server import app
from platforms import ADAPTER_MAP, get_adapter


def run_all_tests():
    print("[1/7] Testing SQLite WAL database & 15 tables initialization...")
    database.init_db()
    assert config.DB_PATH.exists(), "Database file was not created"

    print("[2/7] Testing Fernet Credential Encryption & Decryption...")
    sample_creds = {"sessionid": "ig_secret_123", "cookie_string": "sessionid=abc; csrftoken=xyz"}
    enc = database.encrypt_credentials(sample_creds)
    dec = database.decrypt_credentials(enc)
    assert dec["sessionid"] == "ig_secret_123"

    print("[3/7] Testing Bulldozer Arabic Keyword Matcher normalization...")
    matched, kw = arabic_matcher.match_keywords(
        "ممكن تبعتلي الإرشادات أو التَفاصِيل لو سمحت؟ ١٢٣",
        ["تفاصيل", "ارشادات"],
        whole_word=False,
    )
    assert matched is True, "Arabic matcher failed to match normalized keywords"

    print("[4/7] Testing Nadr.ai `/ig-human` AI Footprint Cleaner & 26 Hooks Library...")
    assert len(hooks_library.HOOK_FORMULAS) == 26
    dirty_text = "في عالمنا المتسارع — هذا النظام يعد بمثابة نقلة نوعية\u200b في الأتمتة!"
    cleaned_res = humanizer.clean_and_humanize(dirty_text)
    assert "—" not in cleaned_res["cleaned_text"]
    assert "\u200b" not in cleaned_res["cleaned_text"]
    assert cleaned_res["score"] >= 80

    print("[5/7] Testing Viral Outlier Multiplier (>3x) & Smart Anti-Ban Jitter Scheduler...")
    v_res = viral_scorer.calculate_outlier_multiplier(post_views=18000, account_median_views=4000)
    assert v_res["is_viral_winner"] is True and v_res["outlier_multiplier"] == 4.5
    slots = scheduler.plan_daily_slots_with_jitter(["09:00", "14:00", "18:30"], jitter_min=15)
    assert len(slots) == 3

    print("[6/7] Testing all 12 Platform Adapters registration...")
    assert len(ADAPTER_MAP) == 12
    for plat in config.SUPPORTED_PLATFORMS:
        ad = get_adapter(plat, {"cookie_string": "sessionid=test"})
        assert ad.platform_name == plat

    print("[7/7] Testing Flask Control Plane REST API & One-Tap Session Capture...")
    client = app.test_client()
    r_stat = client.get("/api/status")
    assert r_stat.status_code == 200 and r_stat.get_json()["ok"] is True

    r_cap = client.post(
        "/api/accounts/capture-session",
        json={"platform": "instagram", "username": "devsaged_ig", "cookie_string": "sessionid=12345; csrftoken=abc"},
    )
    assert r_cap.status_code == 200 and r_cap.get_json()["ok"] is True

    r_mode = client.post("/api/system/mode", json={"mode": "FULL_AUTO"})
    assert r_mode.status_code == 200 and r_mode.get_json()["operation_mode"] == "FULL_AUTO"

    print("✅ ALL 7 VERIFICATION SUITES PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run_all_tests()
