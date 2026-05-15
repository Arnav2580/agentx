from typing import Dict, Iterable

from .grok_client import call_grok
from .models import Domain


DOMAIN_DETECTION_PROMPT = """
Analyze this technical content and return ONLY one of these exact strings:
civil_engineering, mechanical_engineering, software_development,
financial_modeling, healthcare, infrastructure, construction, general

Content:
{content}

Return only the domain string, nothing else."""


DOMAIN_KEYWORDS: Dict[Domain, Iterable[str]] = {
    Domain.CIVIL_ENGINEERING: ("seismic", "base shear", "is 875", "is 1893", "dead load", "live load"),
    Domain.MECHANICAL_ENGINEERING: ("torque", "bearing", "asme", "shaft", "stress-strain"),
    Domain.SOFTWARE_DEVELOPMENT: ("npm", "python", "api", "react", "typescript", "function", "usequery"),
    Domain.FINANCIAL_MODELING: ("compound interest", "npv", "irr", "basel", "principal", "monthly compounding"),
    Domain.HEALTHCARE: ("paracetamol", "acetaminophen", "dose", "patient", "mg/kg", "hipaa"),
    Domain.INFRASTRUCTURE: ("aws", "cloud", "kubernetes", "nist", "owasp", "cis benchmark"),
    Domain.CONSTRUCTION: ("building code", "nfpa", "concrete", "site safety", "permit"),
}


def _heuristic_domain(content: str) -> Domain:
    lowered = content.lower()
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return domain
    return Domain.GENERAL


async def detect_domain(content: str) -> Domain:
    """Auto-detect domain from content using Gemini with heuristic fallback."""
    try:
        result = await call_grok(
            DOMAIN_DETECTION_PROMPT.format(content=content[:1000]),
            max_tokens=20,
        )
        domain_str = result.strip().lower().replace(" ", "_")
        return Domain(domain_str)
    except Exception:
        pass
    return _heuristic_domain(content)
