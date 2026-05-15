from typing import Any, Dict


def verdict_payload(verdict: str, confidence: float, issues: list[str], reasoning: str) -> Dict[str, Any]:
    return {
        "verdict": verdict,
        "confidence": confidence,
        "issues": issues,
        "reasoning": reasoning,
    }
