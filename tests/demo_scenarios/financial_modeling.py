"""
Demo scenario 2: Financial Modeling
Plant a wrong compound interest formula.
"""

DOMAIN = "financial_modeling"

HALLUCINATED_OUTPUT = """
Investment Portfolio Growth Calculation:

Principal (P): Rs10,00,000
Annual Interest Rate (r): 12%
Time Period (t): 5 years
Compounding: Monthly (n=12)

Using compound interest formula:
A = P(1 + r)^t
A = 10,00,000 x (1 + 0.12)^5
A = 10,00,000 x 1.7623
A = Rs17,62,342

The investment will grow to Rs17,62,342 after 5 years.
Expected return: 76.2%
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
