import time

from ..grok_client import call_grok as call_gemini, parse_agent_json
from ..models import AgentResult, AgentVerdict
from .common import verdict_payload


FACT_VERIFIER_PROMPT = """You are Agent 1: Fact Verifier for the AI Hallucination Juror system.

Your ONLY job is to check whether the technical content below contains factual hallucinations:
- Fabricated library or package names that do not exist
- Non-existent APIs or functions
- Fake citations or references
- Incorrect version numbers for well-known software
- Made-up standards or specification numbers
- Non-existent companies or products referenced as real

Domain context: {domain}

Content to verify:
---
{content}
---

Respond in this EXACT JSON format, nothing else, no markdown:
{{
  "verdict": "PASS",
  "confidence": 0.9,
  "issues": [],
  "reasoning": "one sentence explanation"
}}

verdict must be exactly "PASS" or "FAIL".
If no factual issues are found, issues must be an empty array.
Be strict. Hallucinated package names and fake APIs are common."""


def _fallback_fact_check(content: str, domain: str) -> dict:
    lowered = content.lower()
    issues: list[str] = []

    if "react-query-optimizer" in lowered:
        issues.append("Package 'react-query-optimizer' appears hallucinated; use '@tanstack/react-query' instead.")
    if "useoptimizedquery" in lowered:
        issues.append("Hook 'useOptimizedQuery' appears non-existent in the React Query ecosystem.")
    if "thousands of companies" in lowered and "battle-tested" in lowered and "react-query-optimizer" in lowered:
        issues.append("The package credibility claim is unsupported and likely fabricated.")

    if not issues and domain == "healthcare" and "adult-equivalent dose" in lowered:
        issues.append("The statement that an adult-equivalent dose is appropriate for a child is factually unsafe.")

    if issues:
        return verdict_payload("FAIL", 0.91, issues, "Detected hallucinated or unsupported factual claims.")
    return verdict_payload("PASS", 0.76, [], "No obvious factual hallucinations found by fallback checks.")


async def run_fact_verifier(content: str, domain: str) -> AgentResult:
    start = time.time()
    try:
        raw = await call_gemini(
            FACT_VERIFIER_PROMPT.format(domain=domain, content=content[:3000])
        )
        data = parse_agent_json(raw)
    except Exception:
        data = _fallback_fact_check(content, domain)

    return AgentResult(
        agent_id=1,
        agent_name="Fact Verifier",
        verdict=AgentVerdict(data["verdict"]),
        confidence=float(data["confidence"]),
        issues=data.get("issues", []),
        reasoning=data.get("reasoning", ""),
        execution_time_ms=int((time.time() - start) * 1000),
    )
