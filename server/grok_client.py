import json
from typing import Any, Dict

from openai import AsyncOpenAI

from .config import config


def grok_available() -> bool:
    return bool(config.GROK_API_KEY)


_client = AsyncOpenAI(
    api_key=config.GROK_API_KEY or "missing-key",
    base_url="https://api.x.ai/v1",
)


async def call_grok(prompt: str, max_tokens: int = 2000) -> str:
    if not grok_available():
        raise RuntimeError("Grok client unavailable")

    response = await _client.chat.completions.create(
        model=config.MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.1,
    )
    content = response.choices[0].message.content
    return (content or "").strip()


def parse_agent_json(raw: str) -> Dict[str, Any]:
    cleaned = raw.strip().replace("```json", "").replace("```", "").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start != -1 and end > start:
        cleaned = cleaned[start:end]
    return json.loads(cleaned)
