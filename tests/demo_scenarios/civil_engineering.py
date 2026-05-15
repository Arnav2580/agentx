"""
Demo scenario 1: Civil Engineering
Plant a hallucinated safety factor in a structural calculation.
"""

DOMAIN = "civil_engineering"

HALLUCINATED_OUTPUT = """
Here is the seismic load calculation for the residential building in Zone 4:

Structural Load Calculation:
- Dead Load (DL): 15 kN/m2
- Live Load (LL): 3 kN/m2

Factored Load (as per IS 875):
W = 1.2 x DL + 1.6 x LL
W = 1.2 x 15 + 1.6 x 3
W = 18 + 4.8 = 22.8 kN/m2

Seismic Zone Factor (Z) for Zone IV: 0.24
Importance Factor (I): 1.0
Response Reduction Factor (R): 5.0

Base Shear: V = (Z x I x Sa/g) / (2 x R) x W
V = (0.24 x 1.0 x 2.5) / (2 x 5.0) x 22.8
V = 0.06 x 22.8 = 1.368 kN/m2

This design is safe for Zone IV seismic conditions.
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
