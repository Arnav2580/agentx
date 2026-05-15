import difflib
import time
import uuid
from datetime import datetime

from ..config import config
from ..domain_detector import detect_domain
from ..grok_client import call_grok, parse_agent_json
from ..models import AgentResult, AgentVerdict, FinalVerdict, VerificationRequest, VerdictResponse
from .correction_agent import run_correction_agent


BATCH_PROMPT = """You are the AI Hallucination Juror - a multi-agent verification system.

Run ALL 5 verification agents simultaneously on this technical content and return ONE JSON object.

Domain: {domain}

Content to verify:
---
{content}
---

Return ONLY valid JSON with this exact object shape, no markdown, no explanation:
{{
  "agent1_fact_verifier": {{
    "verdict": "PASS",
    "confidence": 0.9,
    "issues": [],
    "reasoning": "one sentence"
  }},
  "agent2_math_validator": {{
    "verdict": "PASS",
    "confidence": 0.9,
    "issues": [],
    "reasoning": "one sentence"
  }},
  "agent3_standards_checker": {{
    "verdict": "PASS",
    "confidence": 0.9,
    "issues": [],
    "reasoning": "one sentence"
  }},
  "agent4_logic_auditor": {{
    "verdict": "PASS",
    "confidence": 0.9,
    "issues": [],
    "reasoning": "one sentence"
  }},
  "agent5_domain_expert": {{
    "verdict": "PASS",
    "confidence": 0.9,
    "issues": [],
    "reasoning": "one sentence from senior expert perspective"
  }}
}}

Agent roles:
- agent1: Check for fabricated packages, fake APIs, non-existent libraries
- agent2: Check mathematical formulas, calculations, unit conversions
- agent3: Check compliance with domain standards (IS 875/AWS CIS/WHO/IFRS etc)
- agent4: Check logical consistency and reasoning gaps
- agent5: Senior expert judgment - would a professional approve this for production?"""


AGENT_META = {
    "agent1_fact_verifier": (1, "Fact Verifier"),
    "agent2_math_validator": (2, "Math Validator"),
    "agent3_standards_checker": (3, "Standards Checker"),
    "agent4_logic_auditor": (4, "Logic Auditor"),
    "agent5_domain_expert": (5, "Domain Expert"),
}


BATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "agent1_fact_verifier": {
            "type": "object",
            "properties": {
                "verdict": {"type": "string"},
                "confidence": {"type": "number"},
                "issues": {"type": "array", "items": {"type": "string"}},
                "reasoning": {"type": "string"},
            },
            "required": ["verdict", "confidence", "issues", "reasoning"],
        },
        "agent2_math_validator": {
            "type": "object",
            "properties": {
                "verdict": {"type": "string"},
                "confidence": {"type": "number"},
                "issues": {"type": "array", "items": {"type": "string"}},
                "reasoning": {"type": "string"},
            },
            "required": ["verdict", "confidence", "issues", "reasoning"],
        },
        "agent3_standards_checker": {
            "type": "object",
            "properties": {
                "verdict": {"type": "string"},
                "confidence": {"type": "number"},
                "issues": {"type": "array", "items": {"type": "string"}},
                "reasoning": {"type": "string"},
            },
            "required": ["verdict", "confidence", "issues", "reasoning"],
        },
        "agent4_logic_auditor": {
            "type": "object",
            "properties": {
                "verdict": {"type": "string"},
                "confidence": {"type": "number"},
                "issues": {"type": "array", "items": {"type": "string"}},
                "reasoning": {"type": "string"},
            },
            "required": ["verdict", "confidence", "issues", "reasoning"],
        },
        "agent5_domain_expert": {
            "type": "object",
            "properties": {
                "verdict": {"type": "string"},
                "confidence": {"type": "number"},
                "issues": {"type": "array", "items": {"type": "string"}},
                "reasoning": {"type": "string"},
            },
            "required": ["verdict", "confidence", "issues", "reasoning"],
        },
    },
    "required": list(AGENT_META.keys()),
}


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    ordered: list[str] = []
    for item in items:
        if item and item not in seen:
            ordered.append(item)
            seen.add(item)
    return ordered


def _build_diff(original: str, corrected: str) -> str:
    diff = difflib.unified_diff(
        original.splitlines(),
        corrected.splitlines(),
        fromfile="original",
        tofile="corrected",
        lineterm="",
    )
    return "\n".join(diff)


async def run_jury(request: VerificationRequest) -> VerdictResponse:
    start_time = time.time()
    request_id = str(uuid.uuid4())[:8]

    domain = request.domain or await detect_domain(request.content)
    domain_str = domain.value

    all_results: list[AgentResult] = []
    try:
        raw = await call_grok(
            BATCH_PROMPT.format(domain=domain_str, content=request.content[:2500]),
            max_tokens=1200,
            json_mode=True,
            response_json_schema=BATCH_SCHEMA,
        )
        data = parse_agent_json(raw)
        if not any(key in data for key in AGENT_META):
            raise ValueError("Batch response did not contain any expected agent payloads.")

        for key, (agent_id, agent_name) in AGENT_META.items():
            agent_data = data.get(key, {})
            verdict_str = agent_data.get("verdict", "UNCERTAIN")
            if verdict_str not in ("PASS", "FAIL"):
                verdict_str = "UNCERTAIN"
            issues = agent_data.get("issues", [])
            if not isinstance(issues, list):
                issues = [str(issues)]
            all_results.append(
                AgentResult(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    verdict=AgentVerdict(verdict_str),
                    confidence=float(agent_data.get("confidence", 0.5)),
                    issues=issues,
                    reasoning=agent_data.get("reasoning", ""),
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )
            )
    except Exception as exc:
        for agent_id, agent_name in AGENT_META.values():
            all_results.append(
                AgentResult(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    verdict=AgentVerdict.UNCERTAIN,
                    confidence=0.5,
                    issues=[f"Batch agent error: {exc}"],
                    reasoning="Error during verification",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )
            )

    fail_count = sum(1 for result in all_results if result.verdict == AgentVerdict.FAIL)

    if fail_count <= config.APPROVED_THRESHOLD:
        final_verdict = FinalVerdict.APPROVED
    elif fail_count == config.FLAGGED_THRESHOLD:
        final_verdict = FinalVerdict.FLAGGED
    else:
        final_verdict = FinalVerdict.BLOCKED

    if all(result.verdict == AgentVerdict.UNCERTAIN for result in all_results):
        final_verdict = FinalVerdict.FLAGGED

    all_issues = _dedupe([issue for result in all_results for issue in result.issues])
    correction = None
    correction_diff = None

    if final_verdict == FinalVerdict.BLOCKED:
        correction = await run_correction_agent(request.content, domain_str, all_issues)
        correction_diff = _build_diff(request.content, correction)

    overall_confidence = sum(result.confidence for result in all_results) / len(all_results)
    total_time = int((time.time() - start_time) * 1000)

    return VerdictResponse(
        request_id=request_id,
        timestamp=datetime.now(),
        domain=domain,
        agent_results=all_results,
        final_verdict=final_verdict,
        overall_confidence=overall_confidence,
        fail_count=fail_count,
        issues_summary=all_issues,
        correction=correction,
        correction_diff=correction_diff,
        execution_time_ms=total_time,
    )
