"""
Smart Multi-Provider Free AI Router (`core/ai_router.py`).
Seamlessly integrates 9 Free/Freemium AI Providers with automatic failover,
cooldown tracking on HTTP 429/503, latency telemetry, and task-specific routing:
1. Google Gemini API (gemini-2.5-flash / gemini-3.8-flash)
2. Groq Cloud (llama-3.3-70b-versatile + whisper-large-v3-turbo for free STT)
3. Cerebras Inference (llama-3.3-70b ultra-low latency)
4. GitHub Models (gpt-4o-mini / DeepSeek-R1 via Azure AI Inference)
5. OpenRouter Free Tier (deepseek/deepseek-r1:free, gemma-3-27b-it:free)
6. Cohere API (command-a-03-2025 - Arabic specialist)
7. Mistral AI (mistral-small-latest)
8. Cloudflare Workers AI (llama-3.3-70b + flux-1-schnell free image generation)
9. Oxion AI + Pollinations.ai (Zero-API-Key unconditional fallback!)
"""
import base64
import json
import os
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import requests

import config
from core import database


class SmartAIRouter:
    """Manages 9 free AI providers with automatic failover and task routing."""

    TASK_PROVIDER_ORDER = {
        "arabic_creative": [
            "gemini", "cohere", "github_models", "groq", "cerebras",
            "openrouter", "mistral", "cloudflare", "oxion", "pollinations"
        ],
        "fast_classify": [
            "groq", "cerebras", "gemini", "mistral", "cloudflare",
            "openrouter", "github_models", "cohere", "oxion", "pollinations"
        ],
        "deep_analysis": [
            "github_models", "gemini", "openrouter", "cohere", "groq",
            "cerebras", "mistral", "cloudflare", "oxion", "pollinations"
        ],
        "default": [
            "gemini", "groq", "cerebras", "github_models", "openrouter",
            "cohere", "mistral", "cloudflare", "oxion", "pollinations"
        ],
    }

    def __init__(self):
        self._cooldowns: Dict[str, float] = {}

    def _is_available(self, provider: str) -> bool:
        now = time.time()
        if self._cooldowns.get(provider, 0) > now:
            return False

        key_checks = {
            "gemini": bool(os.getenv("GEMINI_API_KEY")),
            "groq": bool(os.getenv("GROQ_API_KEY")),
            "cerebras": bool(os.getenv("CEREBRAS_API_KEY")),
            "github_models": bool(os.getenv("GITHUB_MODELS_TOKEN")),
            "openrouter": bool(os.getenv("OPENROUTER_API_KEY")),
            "cohere": bool(os.getenv("COHERE_API_KEY")),
            "mistral": bool(os.getenv("MISTRAL_API_KEY")),
            "cloudflare": bool(os.getenv("CLOUDFLARE_ACCOUNT_ID") and os.getenv("CLOUDFLARE_API_TOKEN")),
            "oxion": bool(os.getenv("OXION_API_KEY")),
            # Pollinations requires ZERO API keys and is always available as ultimate fallback!
            "pollinations": os.getenv("ENABLE_POLLINATIONS_FALLBACK", "true").lower() == "true",
        }
        return key_checks.get(provider, False)

    def _mark_result(self, provider: str, ok: bool, latency_ms: float, error_msg: str = "", is_rate_limit: bool = False):
        cooldown_iso = ""
        if not ok:
            cooldown_sec = 90 if is_rate_limit else 30
            self._cooldowns[provider] = time.time() + cooldown_sec
            cooldown_iso = (datetime.now(timezone.utc) + timedelta(seconds=cooldown_sec)).isoformat()

        try:
            with database.get_conn() as conn:
                row = conn.execute(
                    "SELECT success_count, fail_count, avg_latency_ms FROM ai_provider_stats WHERE provider_name = ?",
                    (provider,),
                ).fetchone()
                if not row:
                    conn.execute(
                        "INSERT INTO ai_provider_stats (provider_name, success_count, fail_count, avg_latency_ms, cooldown_until, last_error, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (provider, 1 if ok else 0, 0 if ok else 1, latency_ms, cooldown_iso, error_msg[:300], database.now_iso()),
                    )
                else:
                    s_cnt = row["success_count"] + (1 if ok else 0)
                    f_cnt = row["fail_count"] + (0 if ok else 1)
                    avg_lat = ((row["avg_latency_ms"] * row["success_count"]) + latency_ms) / max(1, s_cnt) if ok else row["avg_latency_ms"]
                    conn.execute(
                        "UPDATE ai_provider_stats SET success_count=?, fail_count=?, avg_latency_ms=?, cooldown_until=?, last_error=?, updated_at=? "
                        "WHERE provider_name=?",
                        (s_cnt, f_cnt, round(avg_lat, 1), cooldown_iso, error_msg[:300], database.now_iso(), provider),
                    )
        except Exception:
            pass

    def generate_text(
        self,
        prompt: str,
        system_prompt: str = "أنت مساعد ذكي خبير في إدارة وأتمتة حسابات التواصل الاجتماعي.",
        task_type: str = "default",
        temperature: float = 0.7,
        json_mode: bool = False,
    ) -> Dict[str, Any]:
        """
        Routes prompt across the ordered free providers for `task_type`.
        Automatically fails over in <100ms if a provider is rate-limited or offline.
        Returns {"ok": True, "text": "...", "provider": "...", "latency_ms": ...}
        """
        order = self.TASK_PROVIDER_ORDER.get(task_type, self.TASK_PROVIDER_ORDER["default"])
        errors = []

        for provider in order:
            if not self._is_available(provider):
                continue
            t0 = time.time()
            try:
                text = self._call_provider(provider, prompt, system_prompt, temperature, json_mode)
                latency_ms = round((time.time() - t0) * 1000, 1)
                if text and text.strip():
                    self._mark_result(provider, True, latency_ms)
                    return {
                        "ok": True,
                        "text": text.strip(),
                        "provider": provider,
                        "latency_ms": latency_ms,
                    }
            except Exception as exc:
                latency_ms = round((time.time() - t0) * 1000, 1)
                err_str = str(exc)
                is_rl = "429" in err_str or "rate" in err_str.lower() or "quota" in err_str.lower()
                self._mark_result(provider, False, latency_ms, err_str, is_rate_limit=is_rl)
                errors.append(f"{provider}: {err_str[:120]}")

        return {
            "ok": False,
            "text": "",
            "provider": "none",
            "error": " | ".join(errors) if errors else "No AI providers configured or reachable.",
        }

    def _call_provider(
        self, provider: str, prompt: str, system_prompt: str, temperature: float, json_mode: bool
    ) -> str:
        if provider == "gemini":
            api_key = os.getenv("GEMINI_API_KEY", "")
            model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            payload: Dict[str, Any] = {
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": temperature},
            }
            if json_mode:
                payload["generationConfig"]["responseMimeType"] = "application/json"
            resp = requests.post(url, json=payload, timeout=35)
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

        if provider in ("groq", "cerebras", "github_models", "openrouter", "mistral", "oxion"):
            endpoints = {
                "groq": (
                    "https://api.groq.com/openai/v1/chat/completions",
                    os.getenv("GROQ_API_KEY", ""),
                    os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
                ),
                "cerebras": (
                    "https://api.cerebras.ai/v1/chat/completions",
                    os.getenv("CEREBRAS_API_KEY", ""),
                    os.getenv("CEREBRAS_MODEL", "llama-3.3-70b"),
                ),
                "github_models": (
                    "https://models.inference.ai.azure.com/chat/completions",
                    os.getenv("GITHUB_MODELS_TOKEN", ""),
                    os.getenv("GITHUB_MODELS_MODEL", "gpt-4o-mini"),
                ),
                "openrouter": (
                    "https://openrouter.ai/api/v1/chat/completions",
                    os.getenv("OPENROUTER_API_KEY", ""),
                    os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-r1:free"),
                ),
                "mistral": (
                    "https://api.mistral.ai/v1/chat/completions",
                    os.getenv("MISTRAL_API_KEY", ""),
                    os.getenv("MISTRAL_MODEL", "mistral-small-latest"),
                ),
                "oxion": (
                    f"{os.getenv('OXION_BASE_URL', 'https://api.oxion.ai/v1').rstrip('/')}/chat/completions",
                    os.getenv("OXION_API_KEY", ""),
                    os.getenv("OXION_MODEL", "gpt-5.6-luna"),
                ),
            }
            url, key, model = endpoints[provider]
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": temperature,
            }
            if json_mode and provider in ("groq", "github_models", "mistral"):
                payload["response_format"] = {"type": "json_object"}
            resp = requests.post(url, headers=headers, json=payload, timeout=35)
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            return resp.json()["choices"][0]["message"]["content"]

        if provider == "cohere":
            key = os.getenv("COHERE_API_KEY", "")
            model = os.getenv("COHERE_MODEL", "command-a-03-2025")
            resp = requests.post(
                "https://api.cohere.com/v2/chat",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": temperature,
                },
                timeout=35,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            return resp.json()["message"]["content"][0]["text"]

        if provider == "cloudflare":
            acc_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
            token = os.getenv("CLOUDFLARE_API_TOKEN", "")
            model = os.getenv("CLOUDFLARE_TEXT_MODEL", "@cf/meta/llama-3.3-70b-instruct-fp8-fast")
            url = f"https://api.cloudflare.com/client/v4/accounts/{acc_id}/ai/run/{model}"
            resp = requests.post(
                url,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ]
                },
                timeout=35,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            return resp.json()["result"]["response"]

        if provider == "pollinations":
            # Free Zero-Key OpenAI-compatible endpoint
            resp = requests.post(
                "https://text.pollinations.ai/openai",
                headers={"Content-Type": "application/json"},
                json={
                    "model": "openai",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": temperature,
                },
                timeout=40,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
            return data["choices"][0]["message"]["content"]

        raise ValueError(f"Unknown provider: {provider}")

    def transcribe_audio_free(self, audio_path: str) -> Dict[str, Any]:
        """Uses Groq Free Whisper Large v3 Turbo to transcribe video/audio in seconds."""
        groq_key = os.getenv("GROQ_API_KEY", "")
        if not groq_key or not Path(audio_path).exists():
            return {"ok": False, "text": "", "error": "GROQ_API_KEY missing or file not found"}
        model = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")
        with open(audio_path, "rb") as f:
            resp = requests.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {groq_key}"},
                files={"file": (Path(audio_path).name, f, "audio/mpeg")},
                data={"model": model, "response_format": "json"},
                timeout=60,
            )
        if resp.status_code == 200:
            return {"ok": True, "text": resp.json().get("text", ""), "provider": "groq_whisper"}
        return {"ok": False, "text": "", "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}

    def generate_image_free(self, prompt: str, output_path: str, aspect: str = "9:16") -> Dict[str, Any]:
        """
        Generates an image using Cloudflare Workers AI (Flux-1-Schnell Free)
        with automatic fallback to Pollinations Flux Zero-Key generator.
        """
        acc_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
        token = os.getenv("CLOUDFLARE_API_TOKEN", "")
        if acc_id and token:
            try:
                model = os.getenv("CLOUDFLARE_IMAGE_MODEL", "@cf/black-forest-labs/flux-1-schnell")
                url = f"https://api.cloudflare.com/client/v4/accounts/{acc_id}/ai/run/{model}"
                resp = requests.post(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    json={"prompt": prompt, "num_steps": 4},
                    timeout=45,
                )
                if resp.status_code == 200:
                    b64_img = resp.json().get("result", {}).get("image", "")
                    if b64_img:
                        Path(output_path).write_bytes(base64.b64decode(b64_img))
                        return {"ok": True, "path": output_path, "provider": "cloudflare_flux"}
            except Exception:
                pass

        # Fallback: Pollinations Flux (Zero Key)
        try:
            w, h = (720, 1280) if aspect == "9:16" else (1080, 1080)
            encoded = urllib.parse.quote(prompt)
            url = f"https://image.pollinations.ai/prompt/{encoded}?width={w}&height={h}&nologo=true&model=flux"
            resp = requests.get(url, timeout=45)
            if resp.status_code == 200 and len(resp.content) > 1000:
                Path(output_path).write_bytes(resp.content)
                return {"ok": True, "path": output_path, "provider": "pollinations_flux"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        return {"ok": False, "error": "Image generation failed across providers"}

    def get_providers_status(self) -> List[Dict[str, Any]]:
        """Returns health, latency, and availability for all 9+ providers."""
        all_providers = [
            ("gemini", "Google Gemini API (Free)"),
            ("groq", "Groq Cloud LPU + Whisper (Free)"),
            ("cerebras", "Cerebras Wafer-Scale (Free)"),
            ("github_models", "GitHub Models GPT-4o/DeepSeek (Free)"),
            ("openrouter", "OpenRouter :free Pool"),
            ("cohere", "Cohere Command-A Arabic (Free)"),
            ("mistral", "Mistral AI La Plateforme (Free)"),
            ("cloudflare", "Cloudflare Workers AI + Flux (Free)"),
            ("oxion", "Oxion AI Gateway"),
            ("pollinations", "Pollinations Zero-Key Fallback"),
        ]
        stats_map = {}
        try:
            with database.get_conn() as conn:
                for r in conn.execute("SELECT * FROM ai_provider_stats").fetchall():
                    stats_map[r["provider_name"]] = dict(r)
        except Exception:
            pass

        result = []
        for code, label in all_providers:
            st = stats_map.get(code, {})
            result.append({
                "code": code,
                "label": label,
                "configured": self._is_available(code),
                "success_count": st.get("success_count", 0),
                "fail_count": st.get("fail_count", 0),
                "avg_latency_ms": st.get("avg_latency_ms", 0.0),
                "cooldown_until": st.get("cooldown_until", ""),
                "last_error": st.get("last_error", ""),
            })
        return result


router = SmartAIRouter()
