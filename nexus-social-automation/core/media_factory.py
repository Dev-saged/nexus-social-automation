"""
Media Factory Engine (`core/media_factory.py`):
Merges features from:
1. `Katzca/AutoSocial`: FFmpeg-based Video Uniquifier (`uniquify_video`) to alter file/perceptual
   hashes, strip metadata, apply subtle color/gamma shifts, and overlay optional brand logos so
   TikTok, Instagram Reels, and YouTube Shorts never flag multi-account or Trial Reel uploads as duplicates.
2. `LinkedIn Auto Publisher`: Automated Short/Reel Generator (Script + Edge-TTS/gTTS voiceover +
   Pexels stock video fetcher with strict `Avoid-women filter` + FFmpeg muxing).
"""
import hashlib
import os
import random
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests

import config
from core import database
from core.ai_router import router

# Strict exclusion terms for the Avoid-Women filter (inspired by Stage 1 LinkedIn Auto Publisher log)
AVOID_WOMEN_KEYWORDS = {
    "woman", "women", "girl", "girls", "female", "lady", "ladies",
    "bride", "actress", "mother", "sister", "bikini", "model", "makeup",
    "fashion model", "businesswoman", "dancing",
}


def compute_file_hash(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def uniquify_video(
    input_path: str,
    output_path: Optional[str] = None,
    logo_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Runs an FFmpeg recipe against `input_path` to produce a visually identical video
    with a completely new cryptographic and perceptual fingerprint.
    """
    src = Path(input_path)
    if not src.exists():
        return {"ok": False, "error": f"Input video not found: {input_path}"}

    if not output_path:
        out_name = f"{src.stem}_uniq_{int(time.time())}_{random.randint(100,999)}{src.suffix}"
        output_path = str(config.MEDIA_DIR / out_name)

    if not ffmpeg_available():
        shutil.copy2(str(src), output_path)
        return {
            "ok": True,
            "input_path": str(src),
            "output_path": output_path,
            "mode": "copy_fallback_no_ffmpeg",
            "new_hash": compute_file_hash(output_path),
        }

    # Subtle random perceptual adjustments imperceptible to the human eye
    gamma = round(random.uniform(0.98, 1.03), 3)
    contrast = round(random.uniform(0.99, 1.02), 3)
    sat = round(random.uniform(0.98, 1.03), 3)
    vf_chain = f"eq=gamma={gamma}:contrast={contrast}:saturation={sat}"

    cmd = ["ffmpeg", "-y", "-i", str(src)]
    logo = logo_path or os.getenv("UNIQUIFY_LOGO_PATH", "")
    if logo and Path(logo).exists():
        cmd.extend([
            "-i", logo,
            "-filter_complex", f"[0:v]{vf_chain}[v0];[1:v]scale=120:-1[lg];[v0][lg]overlay=W-w-25:25",
        ])
    else:
        cmd.extend(["-vf", vf_chain])

    cmd.extend([
        "-map_metadata", "-1",
        "-metadata", f"creation_time={database.now_iso()}",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        output_path,
    ])

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        return {
            "ok": True,
            "input_path": str(src),
            "output_path": output_path,
            "mode": "ffmpeg_uniquified",
            "original_hash": compute_file_hash(str(src)),
            "new_hash": compute_file_hash(output_path),
        }
    except Exception as exc:
        return {"ok": False, "error": f"FFmpeg uniquify failed: {exc}"}


def passes_avoid_women_filter(video_item: Dict[str, Any]) -> bool:
    """
    Inspects Pexels video URL slug, tags, and description to reject clips containing women
    when the strict filter (`Avoid-women filter`) is enabled.
    """
    blob = " ".join([
        str(video_item.get("url", "")),
        str(video_item.get("user", {}).get("name", "")),
        " ".join(str(t) for t in video_item.get("tags", [])),
    ]).lower()

    for word in AVOID_WOMEN_KEYWORDS:
        if word in blob:
            return False
    return True


def fetch_pexels_clips(
    query: str,
    count: int = 3,
    aspect_ratio: str = "9:16",
    avoid_women: bool = True,
) -> Dict[str, Any]:
    """Searches Pexels Videos API, applies the content filter, and downloads matching MP4s."""
    api_key = os.getenv("PEXELS_API_KEY", "")
    if not api_key:
        return {"ok": False, "clips": [], "rejected": 0, "error": "PEXELS_API_KEY not set"}

    orientation = "portrait" if aspect_ratio == "9:16" else "landscape" if aspect_ratio == "16:9" else "square"
    resp = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": api_key},
        params={"query": query, "orientation": orientation, "per_page": 15},
        timeout=25,
    )
    if resp.status_code != 200:
        return {"ok": False, "clips": [], "rejected": 0, "error": f"Pexels HTTP {resp.status_code}"}

    videos = resp.json().get("videos", [])
    accepted_paths: List[str] = []
    rejected_count = 0

    for v in videos:
        if avoid_women and not passes_avoid_women_filter(v):
            rejected_count += 1
            continue
        files = v.get("video_files", [])
        mp4_files = [f for f in files if f.get("file_type") == "video/mp4" and (f.get("width") or 0) <= 1080]
        if not mp4_files:
            mp4_files = files
        if not mp4_files:
            continue
        dl_url = mp4_files[0].get("link")
        if not dl_url:
            continue
        local_file = config.MEDIA_DIR / f"px{v.get('id')}_{int(time.time())}.mp4"
        try:
            r_vid = requests.get(dl_url, timeout=45)
            if r_vid.status_code == 200:
                local_file.write_bytes(r_vid.content)
                accepted_paths.append(str(local_file))
                if len(accepted_paths) >= count:
                    break
        except Exception:
            continue

    database.log_activity(
        "pexels_filter",
        f"Query '{query}': downloaded {len(accepted_paths)} clips, Avoid-women filter rejected {rejected_count}/{len(videos)} candidates",
        platform="media_factory",
    )
    return {"ok": len(accepted_paths) > 0, "clips": accepted_paths, "rejected": rejected_count}


def synthesize_voiceover(
    text: str,
    lang: str = "ar",
    gender: str = "Male",
    output_mp3: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Synthesizes natural human-like speech using Microsoft Edge-TTS (Free neural voices)
    with automatic fallback to gTTS (`voice_gtts.mp3`), matching and upgrading Stage 1 tool.
    """
    if not output_mp3:
        output_mp3 = str(config.MEDIA_DIR / f"voice_{int(time.time())}.mp3")

    voice_map = {
        ("ar", "Male"): "ar-SA-HamedNeural",
        ("ar", "Female"): "ar-SA-ZariyahNeural",
        ("en", "Male"): "en-US-AndrewNeural",
        ("en", "Female"): "en-US-AvaNeural",
    }
    edge_voice = voice_map.get((lang, gender), "ar-SA-HamedNeural")

    # Primary: edge-tts CLI
    if shutil.which("edge-tts"):
        try:
            subprocess.run(
                ["edge-tts", "--voice", edge_voice, "--text", text, "--write-media", output_mp3],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
            )
            if Path(output_mp3).exists() and Path(output_mp3).stat().st_size > 500:
                return {"ok": True, "path": output_mp3, "engine": f"edge-tts ({edge_voice})"}
        except Exception:
            pass

    # Fallback: gTTS Python library
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang="ar" if lang.startswith("ar") else "en")
        tts.save(output_mp3)
        return {"ok": True, "path": output_mp3, "engine": "gTTS_fallback"}
    except Exception as exc:
        return {"ok": False, "error": f"TTS synthesis failed: {exc}"}


def generate_complete_video(
    topic: str,
    duration_sec: int = 45,
    aspect_ratio: str = "9:16",
    lang: str = "ar",
    voice_gender: str = "Male",
    avoid_women: bool = True,
    account_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    End-to-End 2-minute Automated Video Producer (Script + Tags + TTS + Pexels Filter + FFmpeg Uniquify).
    """
    prompt = (
        f"اكتب تعليقاً صوتياً احترافياً ومباشراً لفيديو قصير مدته {duration_sec} ثانية (حوالي {int(duration_sec * 2.2)} كلمة) "
        f"حول الموضوع التالي: {topic}.\n"
        f"أعطني النتيجة بصيغة JSON يحتوي على:\n"
        f"- voiceover_script: النص الصوتي الصافي بدون أي رموز أو توجيهات مسرحية\n"
        f"- pexels_search_query_en: كلمتين بالإنجليزية للبحث عن لقطات فيديو مناسبة في Pexels (مثل 'business finance' أو 'coding technology')\n"
        f"- caption: وصف المنشور مع الهاشتاجات"
    )
    ai_res = router.generate_text(prompt, task_type="arabic_creative", json_mode=True)
    script_text = topic
    search_q = "technology business"
    caption = topic
    if ai_res["ok"]:
        try:
            import json
            parsed = json.loads(ai_res["text"])
            script_text = parsed.get("voiceover_script", topic)
            search_q = parsed.get("pexels_search_query_en", "technology business")
            caption = parsed.get("caption", topic)
        except Exception:
            script_text = ai_res["text"]

    tts_res = synthesize_voiceover(script_text, lang=lang, gender=voice_gender)
    pexels_res = fetch_pexels_clips(search_q, count=2, aspect_ratio=aspect_ratio, avoid_women=avoid_women)

    final_video_path = str(config.MEDIA_DIR / f"auto_video_{int(time.time())}.mp4")
    if pexels_res.get("clips") and tts_res.get("ok") and ffmpeg_available():
        clip_path = pexels_res["clips"][0]
        audio_path = tts_res["path"]
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-stream_loop", "-1", "-i", clip_path,
                    "-i", audio_path,
                    "-shortest",
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac",
                    final_video_path,
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120,
            )
            uniq_res = uniquify_video(final_video_path)
            if uniq_res.get("ok"):
                final_video_path = uniq_res["output_path"]
        except Exception:
            final_video_path = pexels_res["clips"][0]

    with database.get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO media_vault (
                title, media_kind, original_path, uniquified_path,
                duration_sec, aspect_ratio, avoid_women_verified, created_at
            ) VALUES (?, 'video', ?, ?, ?, ?, ?, ?)
            """,
            (
                topic[:120],
                final_video_path,
                final_video_path,
                float(duration_sec),
                aspect_ratio,
                1 if avoid_women else 0,
                database.now_iso(),
            ),
        )
        media_id = cur.lastrowid

    return {
        "ok": True,
        "media_id": media_id,
        "topic": topic,
        "script": script_text,
        "caption": caption,
        "pexels_query": search_q,
        "avoid_women_rejected": pexels_res.get("rejected", 0),
        "tts_engine": tts_res.get("engine", "none"),
        "video_path": final_video_path,
    }
