import asyncio
import difflib
import time
import uuid
from datetime import datetime

from ..config import config
from ..domain_detector import detect_domain
from ..models import AgentResult, AgentVerdict, FinalVerdict, VerificationRequest, VerdictResponse
from .correction_agent import run_correction_agent
from .domain_expert import run_domain_expert
from .fact_verifier import run_fact_verifier
from .logic_auditor import run_logic_auditor
from .math_validator import run_math_validator
from .standards_checker import run_standards_checker


def _timeout_result(agent_id: int, agent_name: str) -> AgentResult:
    return AgentResult(
        agent_id=agent_id,
        agent_name=agent_name,
        verdict=AgentVerdict.UNCERTAIN,
        confidence=0.5,
        issues=["Agent timed out before returning a verdict."],
        reasoning="The agent exceeded the configured timeout.",
        execution_time_ms=config.AGENT_TIMEOUT_SECONDS * 1000,
    )


async def _with_timeout(coro, agent_id: int, agent_name: str) -> AgentResult:
    try:
        return await asyncio.wait_for(coro, timeout=config.AGENT_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        return _timeout_result(agent_id, agent_name)


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
    """
    Run the verification jury:
    - detect domain if missing
    - run agents 1-4 in parallel
    - run domain expert with the previous results
    - trigger correction when blocked
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())[:8]

    domain = request.domain or await detect_domain(request.content)
    domain_str = domain.value

    agent_1, agent_2, agent_3, agent_4 = await asyncio.gather(
        _with_timeout(run_fact_verifier(request.content, domain_str), 1, "Fact Verifier"),
        _with_timeout(run_math_validator(request.content, domain_str), 2, "Math Validator"),
        _with_timeout(run_standards_checker(request.content, domain_str), 3, "Standards Checker"),
        _with_timeout(run_logic_auditor(request.content, domain_str), 4, "Logic Auditor"),
    )

    agent_5 = await _with_timeout(
        run_domain_expert(request.content, domain_str, [agent_1, agent_2, agent_3, agent_4]),
        5,
        "Domain Expert",
    )

    all_results = [agent_1, agent_2, agent_3, agent_4, agent_5]
    fail_count = sum(1 for result in all_results if result.verdict == AgentVerdict.FAIL)

    if fail_count <= config.APPROVED_THRESHOLD:
        final_verdict = FinalVerdict.APPROVED
    elif fail_count == config.FLAGGED_THRESHOLD:
        final_verdict = FinalVerdict.FLAGGED
    else:
        final_verdict = FinalVerdict.BLOCKED

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
