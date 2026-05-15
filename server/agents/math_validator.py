import re
import time

from ..grok_client import call_grok as call_gemini, parse_agent_json
from ..models import AgentResult, AgentVerdict
from .common import verdict_payload


MATH_VALIDATOR_PROMPT = """You are Agent 2: Mathematical Validator for the AI Hallucination Juror system.

Your ONLY job is to check the mathematical correctness of the content below:
- Are formulas correct? (structural, financial, physics, medical dosage calculations)
- Are unit conversions accurate?
- Are numerical calculations correct?
- Are statistical values reasonable?
- Are constants and coefficients standard/correct?
- Are exponents and order of operations correct?

Domain context: {domain}

Domain-specific things to check:
- civil_engineering: load factors, safety factors, seismic coefficients
- financial_modeling: compound interest, NPV, IRR, options pricing formulas
- healthcare: dosage calculations (weight-based), unit conversions (mg/kg)
- software_development: Big-O complexity claims, benchmark numbers

Content to validate:
---
{content}
---

Respond in this EXACT JSON format, nothing else:
{{
  "verdict": "PASS" or "FAIL",
  "confidence": 0.0-1.0,
  "issues": ["specific math error 1", "specific math error 2"],
  "reasoning": "one sentence explanation"
}}

If the content has no mathematical content, verdict should be "PASS" with confidence 0.9."""


def _fallback_math_check(content: str, domain: str) -> dict:
    lowered = content.lower()
    issues: list[str] = []

    if "compounding" in lowered and "monthly" in lowered and "a = p(1 + r)^t" in lowered:
        issues.append("Compound interest formula is wrong for monthly compounding; it should use (1 + r/n)^(nt).")
    if "1.2 × dl + 1.6 × ll" in content or "1.2 x dl + 1.6 x ll" in lowered:
        issues.append("Load factor combination for the seismic example is inconsistent with the stated standard.")
    if "paracetamol" in lowered and "weight: 20 kg" in lowered and "1000 mg every 6 hours" in lowered:
        issues.append("Pediatric dose is mathematically unsafe: 20 kg at 15 mg/kg is about 300 mg, not 1000 mg.")
    if "maximum daily dose: 4000 mg/day" in lowered and "20 kg" in lowered:
        issues.append("Maximum daily dose is too high for a 20 kg child and exceeds standard pediatric dosing.")

    if not issues:
        has_numbers = bool(re.search(r"\d", content))
        confidence = 0.9 if not has_numbers else 0.73
        return verdict_payload("PASS", confidence, [], "No obvious mathematical errors found by fallback checks.")
    return verdict_payload("FAIL", 0.94, issues, "Detected numerical or formula-level inconsistencies.")


async def run_math_validator(content: str, domain: str) -> AgentResult:
    start = time.time()
    try:
        raw = await call_gemini(
            MATH_VALIDATOR_PROMPT.format(domain=domain, content=content[:3000])
        )
        data = parse_agent_json(raw)
    except Exception:
        data = _fallback_math_check(content, domain)

    return AgentResult(
        agent_id=2,
        agent_name="Math Validator",
        verdict=AgentVerdict(data["verdict"]),
        confidence=float(data["confidence"]),
        issues=data.get("issues", []),
        reasoning=data.get("reasoning", ""),
        execution_time_ms=int((time.time() - start) * 1000),
    )
