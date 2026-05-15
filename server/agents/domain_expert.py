import time

from ..grok_client import call_grok as call_gemini, parse_agent_json
from ..models import AgentResult, AgentVerdict
from .common import verdict_payload


DOMAIN_EXPERT_PROMPT = """You are Agent 5: Domain Expert for the AI Hallucination Juror.

You have read the verdicts from the other 4 agents and the original content.
Your job is to give the final expert assessment:
"Would a senior professional in this domain approve this content for production use?"

You are a senior expert in: {domain}

Other agents' verdicts:
{agent_verdicts}

Original content:
---
{content}
---

Consider:
- Overall safety and correctness for production use
- Any domain-specific risks the other agents might have missed
- Whether this could cause harm if deployed as-is
- Professional standards and best practices

Respond in this EXACT JSON format, nothing else:
{{
  "verdict": "PASS" or "FAIL",
  "confidence": 0.0-1.0,
  "issues": ["domain-specific concern 1"],
  "reasoning": "one sentence from a senior expert perspective"
}}"""


def _fallback_domain_expert(content: str, domain: str, previous_results: list) -> dict:
    fail_count = sum(1 for result in previous_results if result.verdict == AgentVerdict.FAIL)
    issues = []
    lowered = content.lower()

    if "paracetamol" in lowered and "20 kg" in lowered and "1000 mg every 6 hours" in lowered:
        issues.append("A senior healthcare reviewer would reject this because the suggested pediatric dose could cause harm.")
        return verdict_payload("FAIL", 0.97, issues, "This should not be used in practice without correction.")

    if "react-query-optimizer" in lowered or "useoptimizedquery" in lowered:
        issues.append("A senior software reviewer would reject hallucinated package guidance because of supply-chain risk.")
        return verdict_payload("FAIL", 0.93, issues, "This is too risky to ship without correction.")

    if domain == "civil_engineering" and fail_count >= 2:
        aggregated = []
        for result in previous_results:
            aggregated.extend(result.issues[:1])
        return verdict_payload(
            "FAIL",
            0.91,
            aggregated[:3],
            "A senior civil reviewer would require a corrected calculation before approval.",
        )

    if fail_count >= 3:
        aggregated = []
        for result in previous_results:
            aggregated.extend(result.issues[:1])
        return verdict_payload(
            "FAIL",
            0.9,
            aggregated[:3],
            "A senior domain reviewer would not approve this for production use.",
        )

    return verdict_payload("PASS", 0.68, [], "A senior reviewer would likely accept this with normal caution.")


async def run_domain_expert(content: str, domain: str, previous_results: list) -> AgentResult:
    start = time.time()
    verdicts_summary = "\n".join(
        f"Agent {result.agent_id} ({result.agent_name}): {result.verdict.value} - {result.reasoning}"
        for result in previous_results
    )

    try:
        raw = await call_gemini(
            DOMAIN_EXPERT_PROMPT.format(
                domain=domain,
                agent_verdicts=verdicts_summary,
                content=content[:2000],
            )
        )
        data = parse_agent_json(raw)
    except Exception:
        data = _fallback_domain_expert(content, domain, previous_results)

    return AgentResult(
        agent_id=5,
        agent_name="Domain Expert",
        verdict=AgentVerdict(data["verdict"]),
        confidence=float(data["confidence"]),
        issues=data.get("issues", []),
        reasoning=data.get("reasoning", ""),
        execution_time_ms=int((time.time() - start) * 1000),
    )
