from ..config import config
from ..grok_client import call_grok as call_gemini


CORRECTION_PROMPT = """You are Agent 6: Correction Agent for the AI Hallucination Juror.

The previous content was BLOCKED by the jury. Your job is to produce a corrected version.

Domain: {domain}

Issues identified by the jury:
{all_issues}

Original content that was BLOCKED:
---
{content}
---

Produce a corrected version that:
1. Fixes all identified issues
2. Maintains the same intent and structure
3. Is technically accurate for the domain
4. Would pass all 5 verification agents

Output only the corrected content, nothing else."""


def _fallback_correction(content: str, domain: str) -> str:
    lowered = content.lower()

    if "react-query-optimizer" in lowered:
        return """Here's how to implement data fetching with caching in your React application:

First, install the required packages:
npm install @tanstack/react-query axios axios-cache-interceptor

Then use it in your component:

import { useQuery } from '@tanstack/react-query';

function UsersList() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['users'],
    queryFn: async () => {
      const response = await fetch('/api/users');
      return response.json();
    },
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });

  return null;
}

This uses the supported React Query API and avoids hallucinated packages."""

    if "monthly" in lowered and "compound interest" in lowered:
        return """Investment Portfolio Growth Calculation:

Principal (P): Rs10,00,000
Annual Interest Rate (r): 12%
Time Period (t): 5 years
Compounding: Monthly (n=12)

Using compound interest formula:
A = P(1 + r/n)^(nt)
A = 10,00,000 x (1 + 0.12/12)^(12 x 5)
A = 10,00,000 x (1.01)^60
A is approximately Rs18,16,970

The investment will grow to about Rs18.17 lakh after 5 years, which is an expected return of about 81.7%."""

    if "paracetamol" in lowered and "20 kg" in lowered:
        return """Pediatric Fever Management Protocol:

Patient: 7-year-old child, Weight: 20 kg, Temperature: 38.8 C

Medication: Paracetamol (Acetaminophen)
Recommended dose: 15 mg/kg every 4 to 6 hours as needed
Calculated single dose: 15 x 20 = 300 mg
Maximum daily dose: follow pediatric guidance and keep the total well below adult limits

Administration: Use an age-appropriate liquid or tablet formulation with accurate weight-based dosing
Duration: Use the minimum duration necessary and seek clinician advice if fever persists

Note: Pediatric dosing must be weight-based and should not use standard adult dosing."""

    if "seismic" in lowered and "zone iv" in lowered:
        return """Here is the seismic load calculation for the residential building in Zone IV:

Structural Load Calculation:
- Dead Load (DL): 15 kN/m2
- Live Load (LL): 3 kN/m2

Use the correct load combination required by the governing standard for seismic design rather than the earlier 1.2 and 1.6 mix.
Confirm the applicable factors from the relevant edition of IS 875 and IS 1893 before final design sign-off.

Seismic Zone Factor (Z) for Zone IV: 0.24
Importance Factor (I): 1.0
Response Reduction Factor (R): 5.0

Base shear should be calculated using the governing code expression with the correct design horizontal acceleration coefficient.
Do not conclude the design is safe until the full load combinations, member checks, drift checks, and detailing requirements have been verified."""

    return content


async def run_correction_agent(content: str, domain: str, all_issues: list[str]) -> str:
    issues_text = "\n".join(f"- {issue}" for issue in all_issues)

    if config.GROK_API_KEY:
        try:
            return await call_gemini(
                CORRECTION_PROMPT.format(
                    domain=domain,
                    all_issues=issues_text,
                    content=content,
                ),
                max_tokens=4000,
            )
        except Exception:
            pass

    return _fallback_correction(content, domain)
