"""
Demo scenario 3: Healthcare
Plant a wrong pediatric medication dosage.
"""

DOMAIN = "healthcare"

HALLUCINATED_OUTPUT = """
Pediatric Fever Management Protocol:

Patient: 7-year-old child, Weight: 20 kg, Temperature: 38.8 C

Medication: Paracetamol (Acetaminophen)
Recommended dose: 1000 mg every 6 hours
Maximum daily dose: 4000 mg/day

Administration: Oral tablet or syrup
Duration: Until fever resolves (typically 3-5 days)

Note: This is the standard adult-equivalent dose appropriate for school-age children.
"""

import asyncio

import httpx


async def run_demo():
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "http://localhost:8000/verify",
            json={
                "content": HALLUCINATED_OUTPUT,
                "domain": DOMAIN,
                "source": "demo",
            },
        )
        data = response.json()
        print(f"\n{'-' * 50}")
        print(f"VERDICT: {data['final_verdict']}  ({data['fail_count']}/5 failed)  {data['execution_time_ms']}ms")
        print(f"{'-' * 50}")
        for agent in data["agent_results"]:
            icon = "✓" if agent["verdict"] == "PASS" else "✗" if agent["verdict"] == "FAIL" else "?"
            print(f"  {icon} A{agent['agent_id']} {agent['agent_name']}: {agent['verdict']}")
            for issue in (agent["issues"] or [])[:2]:
                print(f"      • {issue}")
        if data.get("correction"):
            print(f"\nCORRECTION:\n{data['correction'][:300]}")


if __name__ == "__main__":
    asyncio.run(run_demo())
