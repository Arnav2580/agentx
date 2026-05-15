import asyncio
import json
import random
import time
from typing import Any, Dict

import httpx

from .config import config

class GeminiRateLimitError(RuntimeError):
    def __init__(self, message: str, retry_after_seconds: int | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


_RATE_LIMIT_UNTIL = 0.0
_grok_semaphore = asyncio.Semaphore(1)


def grok_available() -> bool:
    return bool(config.GEMINI_API_KEY)


async def call_grok(
    prompt: str,
    max_tokens: int = 400,
    json_mode: bool = False,
    response_json_schema: Dict[str, Any] | None = None,
) -> str:
    global _RATE_LIMIT_UNTIL

    if not grok_available():
        raise RuntimeError("Gemini client unavailable")

    if _RATE_LIMIT_UNTIL and time.time() < _RATE_LIMIT_UNTIL:
        wait_seconds = max(1, int(_RATE_LIMIT_UNTIL - time.time()))
        raise GeminiRateLimitError(
            f"Gemini is temporarily rate-limited. Try again in about {wait_seconds} seconds.",
            retry_after_seconds=wait_seconds,
        )

    request_body: Dict[str, Any] = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": max_tokens,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    if json_mode:
        request_body["generationConfig"]["responseMimeType"] = "application/json"
    if response_json_schema:
        request_body["generationConfig"]["responseJsonSchema"] = response_json_schema

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.MODEL}:generateContent"
    headers = {
        "x-goog-api-key": config.GEMINI_API_KEY,
        "Content-Type": "application/json",
    }

    async with _grok_semaphore:
        async with httpx.AsyncClient(timeout=120.0) as client:
            max_retries = 8
            base_delay = 4.0
            
            for attempt in range(max_retries):
                response = await client.post(url, headers=headers, json=request_body)
                if response.status_code == 429 and attempt < max_retries - 1:
                    retry_after_header = response.headers.get("Retry-After")
                    retry_after = None
                    if retry_after_header:
                        try:
                            retry_after = max(1, int(float(retry_after_header)))
                        except ValueError:
                            retry_after = None
                    
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 2.0)
                    if retry_after:
                        delay = max(delay, retry_after)
                        
                    await asyncio.sleep(delay)
                    continue
                    
                if response.status_code == 429:
                    retry_after_header = response.headers.get("Retry-After")
                    retry_after = None
                    if retry_after_header:
                        try:
                            retry_after = max(1, int(float(retry_after_header)))
                        except ValueError:
                            retry_after = None
    
                    payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                    google_message = ""
                    if isinstance(payload, dict):
                        google_message = payload.get("error", {}).get("message", "").strip()
                    wait_seconds = retry_after or int(base_delay * (2 ** (max_retries - 1)))
                    _RATE_LIMIT_UNTIL = time.time() + wait_seconds
                    friendly = google_message or "Gemini rate limit reached."
                    raise GeminiRateLimitError(
                        f"{friendly} Try again in about {wait_seconds} seconds.",
                        retry_after_seconds=wait_seconds,
                    )
                    
                response.raise_for_status()
                payload = response.json()
                _RATE_LIMIT_UNTIL = 0.0
                break

    candidates = payload.get("candidates") or []
    if not candidates:
        raise ValueError(f"No Gemini candidates returned: {payload}")

    parts = candidates[0].get("content", {}).get("parts", [])
    text_chunks = [part.get("text", "") for part in parts if isinstance(part, dict)]
    content = "".join(text_chunks).strip()
    if not content:
        raise ValueError(f"Gemini returned empty content: {payload}")
    return content


def parse_agent_json(raw: str) -> Dict[str, Any]:
    cleaned = raw.strip().replace("```json", "").replace("```", "").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start != -1 and end > start:
        cleaned = cleaned[start:end]
    return json.loads(cleaned)
