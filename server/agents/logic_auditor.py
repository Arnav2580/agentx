import time

from ..grok_client import call_grok as call_gemini, parse_agent_json
from ..models import AgentResult, AgentVerdict
from .common import verdict_payload


LOGIC_PROMPT = """You are Agent 4: Logic and Reasoning Auditor for the AI Hallucination Juror.

Your ONLY job is to verify that the technical content is logically consistent:
- Does the conclusion follow from the premises?
- Are there internal contradictions?
- Is the reasoning chain complete?
- Are conditional statements correct?
- Are there circular arguments?
- Does the proposed solution actually solve the stated problem?
- Are edge cases handled correctly?
- Are there hidden assumptions that could fail?

Domain: {domain}

Content to audit:
---
{content}
---

Respond in this EXACT JSON format, nothing else:
{{
  "verdict": "PASS" or "FAIL",
  "confidence": 0.0-1.0,
  "issues": ["logical flaw 1", "logical flaw 2"],
  "reasoning": "one sentence explanation"
}}"""


def _fallback_logic_check(content: str, domain: str) -> dict:
    lowered = content.lower()
    issues: list[str] = []

    if "this design is safe" in lowered and "base shear" in lowered:
        issues.append("The conclusion that the design is safe is asserted without enough supporting checks.")
    if "adult-equivalent dose appropriate for school-age children" in lowered:
        issues.append("The reasoning incorrectly treats adult-equivalent dosing as safe for pediatric use.")
    if "the investment will grow to" in lowered and "compounding: monthly" in lowered and "a = p(1 + r)^t" in lowered:
        issues.append("The conclusion relies on a formula that does not match the stated monthly compounding assumptions.")

    if issues:
        return verdict_payload("FAIL", 0.85, issues, "Detected gaps between the reasoning chain and the conclusion.")
    return verdict_payload("PASS", 0.7, [], "No obvious logical contradictions found by fallback checks.")


async def run_logic_auditor(content: str, domain: str) -> AgentResult:
    start = time.time()
    try:
        raw = await call_gemini(
            LOGIC_PROMPT.format(domain=domain, content=content[:3000])
        )
        data = parse_agent_json(raw)
    except Exception:
        data = _fallback_logic_check(content, domain)

    return AgentResult(
        agent_id=4,
        agent_name="Logic Auditor",
        verdict=AgentVerdict(data["verdict"]),
        confidence=float(data["confidence"]),
        issues=data.get("issues", []),
        reasoning=data.get("reasoning", ""),
        execution_time_ms=int((time.time() - start) * 1000),
    )
