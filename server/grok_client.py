import json
from typing import Any, Dict

import httpx

from .config import config


def grok_available() -> bool:
    return bool(config.GEMINI_API_KEY)


async def call_grok(
    prompt: str,
    max_tokens: int = 400,
    json_mode: bool = False,
    response_json_schema: Dict[str, Any] | None = None,
) -> str:
    if not grok_available():
        raise RuntimeError("Gemini client unavailable")

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

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, headers=headers, json=request_body)
        response.raise_for_status()
        payload = response.json()

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
