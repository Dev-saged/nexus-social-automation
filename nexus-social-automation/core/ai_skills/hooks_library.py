"""
26 Scored Viral Hook Formulas (`hooks.json` equivalent from Jakeschincariol/instagram-agent-skill).
Used by `/ig-reel` and `/ig-viral` to classify and score hooks before generating scripts.
"""
from typing import Any, Dict, List

HOOK_FORMULAS: List[Dict[str, Any]] = [
    {"id": "H01", "category": "contrarian", "name": "عكس الشائع (Contrarian Truth)", "template_ar": "كل الناس تقول لك {common_belief}، بس الحقيقة اللي محدش بيقولها هي {truth}.", "base_score": 92},
    {"id": "H02", "category": "mistake", "name": "الخطأ المكلف (Costly Mistake)", "template_ar": "أكبر غلطة بتخسرك {loss} في {topic} هي إنك لسه بتعمل كده...", "base_score": 90},
    {"id": "H03", "category": "secret", "name": "السر المخفي (Gatekept Secret)", "template_ar": "أداة/طريقة في {topic} كنت أتمنى أعرفها قبل {time_period}...", "base_score": 89},
    {"id": "H04", "category": "comparison", "name": "مقارنة صادمة (Before vs After)", "template_ar": "الفرق بين الشخص اللي بيعمل {bad_way} واللي بيعمل {good_way} في 30 ثانية:", "base_score": 88},
    {"id": "H05", "category": "negative_warning", "name": "تحذير مباشر (Stop Doing This)", "template_ar": "وقف فوراً استخدام {tool_or_habit} لو هدفك {goal}!", "base_score": 94},
    {"id": "H06", "category": "case_study", "name": "تجربة حقيقية بالنتيجة (Proof First)", "template_ar": "إزاي قدرت أوصل لـ {result} في {timeframe} بدون {pain_point}:", "base_score": 93},
    {"id": "H07", "category": "step_by_step", "name": "خطة الـ 3 خطوات (3-Step Blueprint)", "template_ar": "لو بديت في {topic} من الصفر اليوم، هذي الـ 3 خطوات الوحيدة اللي بسويها:", "base_score": 91},
    {"id": "H08", "category": "callout", "name": "نداء الفئة المستهدفة (Specific Audience Callout)", "template_ar": "لو إنت {audience} وبتعاني من {problem}، الفيديو ده هيلخص لك الحل:", "base_score": 87},
    {"id": "H09", "category": "time_hack", "name": "اختصار الوقت (Time Compression)", "template_ar": "وفرت عليك 100 ساعة بحث في {topic} ولخصتها في دقيقة واحدة:", "base_score": 90},
    {"id": "H10", "category": "myth_buster", "name": "نسف الخرافة (Myth Buster)", "template_ar": "أكبر كذبة سمعتها عن {topic} وصدقتها لفترة طويلة...", "base_score": 89},
    {"id": "H11", "category": "question_hook", "name": "سؤال الفضول (Open Loop Question)", "template_ar": "ليه 95% من اللي بيبدأوا في {topic} بيفشلوا في أول شهر؟", "base_score": 86},
    {"id": "H12", "category": "unpopular_opinion", "name": "رأي غير شعبي (Unpopular Opinion)", "template_ar": "رأي ممكن يزعل ناس كتير في مجال {topic}:...", "base_score": 91},
    {"id": "H13", "category": "checklist", "name": "قائمة الفحص السريعة (Rapid Audit)", "template_ar": "3 علامات بتأكد إنك ماشي صح في {topic} (رقم 3 هي الأهم):", "base_score": 85},
    {"id": "H14", "category": "story_pivot", "name": "لحظة التحول (Turning Point Story)", "template_ar": "في اللحظة اللي غيرت فيها {change}، كل نتائج {topic} اتقلبت 180 درجة.", "base_score": 88},
    {"id": "H15", "category": "free_vs_paid", "name": "المجاني أقوى من المدفوع (Free Beats Paid)", "template_ar": "بديل مجاني 100% بيغنيك عن دفع اشتراكات شهرية في {paid_category}:", "base_score": 95},
    {"id": "H16", "category": "behind_scenes", "name": "خلف الكواليس (System Reveal)", "template_ar": "تعال أوريك النظام اللي شغال في الخلفية لـ {goal} وأنا قافل جهازي:", "base_score": 93},
    {"id": "H17", "category": "rule_of_one", "name": "القاعدة الواحدة (The 1% Rule)", "template_ar": "قاعدة واحدة لو طبقتها في {topic} هتغنيك عن 90% من المجهود الضائع:", "base_score": 87},
    {"id": "H18", "category": "Visual_shock", "name": "صدمة بصرية/رقمية (Data Shock)", "template_ar": "الرقم اللي قدامك على الشاشة ده مش صدفة، ده نتيجة {mechanism}:", "base_score": 89},
    {"id": "H19", "category": "dont_buy", "name": "لا تشتري قبل أن تعرف (Anti-Pitch)", "template_ar": "لا تبدأ في {topic} ولا تدفع ريال واحد قبل ما تتأكد من النقطة دي:", "base_score": 91},
    {"id": "H20", "category": "if_i_were_you", "name": "لو كنت مكانك (Empathy Action)", "template_ar": "لو جوالي هو أداتي الوحيدة وعايز أبني {goal}، هبدأ بالترتيب ده:", "base_score": 92},
    {"id": "H21", "category": "hidden_feature", "name": "ميزة مخفية (Hidden Gem)", "template_ar": "ميزة مخفية جوه {platform_or_tool} أغلب المستخدمين ما يعرفوا عنها شي:", "base_score": 88},
    {"id": "H22", "category": "speed_challenge", "name": "تحدي السرعة (60-Second Build)", "template_ar": "في أقل من 60 ثانية، هوريك إزاي تظبط {task} من الصفر:", "base_score": 90},
    {"id": "H23", "category": "harsh_truth", "name": "الحقيقة الصريحة (Brutal Honesty)", "template_ar": "محدش هيقولك الكلام ده بصراحة، بس مشكلتك في {topic} مش قلة الوقت...", "base_score": 91},
    {"id": "H24", "category": "steal_my_system", "name": "انسخ طريقتي (Steal My Workflow)", "template_ar": "انسخ هذي الهيكلة الجاهزة لـ {topic} وطبقها على حسابك اليوم:", "base_score": 94},
    {"id": "H25", "category": "experiment", "name": "تجربة الـ 7 أيام (7-Day Experiment)", "template_ar": "جربت {experiment} لمدة أسبوع كامل، ودي النتيجة بدون تجميل:", "base_score": 89},
    {"id": "H26", "category": "future_shift", "name": "تغير قواعد اللعبة (The New Meta)", "template_ar": "الطريقة القديمة في {topic} انتهت، وده النظام الجديد اللي شغال حالياً:", "base_score": 92},
]


def score_hook_text(hook_text: str) -> Dict[str, Any]:
    """Scores a hook out of 100 based on length, specificity, curiosity gap, and absence of fluff."""
    words = hook_text.strip().split()
    score = 75
    notes = []

    if 6 <= len(words) <= 18:
        score += 10
        notes.append("طول مثالي لأول 3 ثوانٍ")
    elif len(words) > 22:
        score -= 10
        notes.append("الهوك طويل جداً، يفضل اختصاره لأقل من 18 كلمة")

    if any(ch.isdigit() for ch in hook_text):
        score += 6
        notes.append("يحتوي على رقم محدد يرفع الفضول")

    power_tokens = ["وقف", "غلط", "سر", "مجاني", "بدون", "كيف", "إزاي", "ليش", "ليه", "خطوات", "تنسخ"]
    if any(tok in hook_text for tok in power_tokens):
        score += 7
        notes.append("يحتوي على كلمات محفزة للانتباه")

    score = max(40, min(99, score))
    return {"score": score, "word_count": len(words), "notes": notes}
