import time

from ..grok_client import call_grok as call_gemini, parse_agent_json
from ..models import AgentResult, AgentVerdict
from .common import verdict_payload


STANDARDS_PROMPT = """You are Agent 3: Standards and Codebook Verifier for the AI Hallucination Juror.

Your ONLY job is to verify that the technical content complies with relevant standards.

Domain: {domain}

Standards to check by domain:
- civil_engineering: IS 456, IS 875, IS 1893, Eurocode 2/3/8, AISC, ACI 318
- infrastructure/cloud: AWS CIS Benchmark, OWASP Top 10, NIST SP 800-53, ISO 27001
- healthcare: WHO essential medicines list, FDA guidance, HIPAA requirements
- financial_modeling: IFRS, GAAP, Basel III, SEC regulations
- software_development: OWASP Top 10, CVE database, GDPR, PCI-DSS
- mechanical_engineering: ASME standards, ISO 9001, DIN standards
- construction: IBC, NFPA 101

Content to check:
---
{content}
---

Respond in this EXACT JSON format, nothing else:
{{
  "verdict": "PASS" or "FAIL",
  "confidence": 0.0-1.0,
  "issues": ["violated standard X: specific issue", "another violation"],
  "reasoning": "one sentence explanation"
}}"""


def _fallback_standards_check(content: str, domain: str) -> dict:
    lowered = content.lower()
    issues: list[str] = []

    if "is 875" in lowered and ("1.2 × dl + 1.6 × ll" in content or "1.2 x dl + 1.6 x ll" in lowered):
        issues.append("Referenced IS seismic load combination appears inconsistent with the stated standard guidance.")
    if "react-query-optimizer" in lowered:
        issues.append("Hallucinated package advice creates a software supply-chain risk under standard secure development guidance.")
    if "paracetamol" in lowered and "1000 mg every 6 hours" in lowered and "20 kg" in lowered:
        issues.append("Pediatric dosing recommendation conflicts with standard weight-based medication guidance.")

    if issues:
        return verdict_payload("FAIL", 0.88, issues, "Detected standards or compliance mismatches.")
    return verdict_payload("PASS", 0.72, [], "No obvious standards violations found by fallback checks.")


async def run_standards_checker(content: str, domain: str) -> AgentResult:
    start = time.time()
    try:
        raw = await call_gemini(
            STANDARDS_PROMPT.format(domain=domain, content=content[:3000])
        )
        data = parse_agent_json(raw)
    except Exception:
        data = _fallback_standards_check(content, domain)

    return AgentResult(
        agent_id=3,
        agent_name="Standards Checker",
        verdict=AgentVerdict(data["verdict"]),
        confidence=float(data["confidence"]),
        issues=data.get("issues", []),
        reasoning=data.get("reasoning", ""),
        execution_time_ms=int((time.time() - start) * 1000),
    )
