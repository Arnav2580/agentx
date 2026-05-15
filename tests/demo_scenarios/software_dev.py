"""
Demo scenario 4: Software Development
Plant a hallucinated npm package name (slopsquatting risk).
"""

DOMAIN = "software_development"

HALLUCINATED_OUTPUT = """
Here's how to implement data fetching with caching in your React application:

First, install the required packages:
npm install react-query-optimizer axios-cache-interceptor

Then use it in your component:

import { useOptimizedQuery } from 'react-query-optimizer';
import { setupCache } from 'axios-cache-interceptor';

const { data, isLoading, error } = useOptimizedQuery({
  queryKey: ['users'],
  queryFn: () => fetch('/api/users').then(r => r.json()),
  staleTime: 5 * 60 * 1000,
  cacheTime: 10 * 60 * 1000,
});

This will automatically handle caching and background refetching.
The react-query-optimizer package is battle-tested and used by thousands of companies.
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
