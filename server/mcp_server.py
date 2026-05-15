"""
MCP (Model Context Protocol) server implementation.
Exposes Juror tools to Claude Code, Grok-compatible clients, Codex CLI, etc.
"""

import json
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from .agents.orchestrator import run_jury
from .database import get_history, save_verdict
from .models import VerificationRequest

router = APIRouter()

TOOLS_LIST = {
    "tools": [
        {
            "name": "verify_output",
            "description": "Verify AI-generated technical content using a 6-agent jury. Detect hallucinations, math errors, standards violations, and logical flaws. Returns APPROVED, FLAGGED, or BLOCKED verdict with detailed analysis.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The AI-generated technical content to verify",
                    },
                    "domain": {
                        "type": "string",
                        "enum": [
                            "civil_engineering",
                            "mechanical_engineering",
                            "software_development",
                            "financial_modeling",
                            "healthcare",
                            "infrastructure",
                            "construction",
                            "general",
                        ],
                        "description": "Domain context (auto-detected if omitted)",
                    },
                    "context": {
                        "type": "string",
                        "description": "Optional original prompt, file path, or other supporting context",
                    },
                },
                "required": ["content"],
            },
        },
        {
            "name": "get_verdict_history",
            "description": "Get the history of past verification verdicts",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of recent verdicts to return (default: 10)",
                    }
                },
            },
        },
        {
            "name": "get_stats",
            "description": "Get statistics on verdict outcomes",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
    ]
}


class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Any] = None
    method: str
    params: Optional[dict] = None


def _format_verdict_text(verdict) -> str:
    result_text = (
        f"JUROR VERDICT: {verdict.final_verdict.value}\n"
        f"Confidence: {verdict.overall_confidence:.0%}\n"
        f"Domain: {verdict.domain.value}\n"
        f"Agents Failed: {verdict.fail_count}/5\n"
        f"Time: {verdict.execution_time_ms}ms\n\n"
        "AGENT RESULTS:\n"
    )

    for agent in verdict.agent_results:
        icon = "PASS" if agent.verdict.value == "PASS" else "FAIL" if agent.verdict.value == "FAIL" else "UNCERTAIN"
        result_text += f"- Agent {agent.agent_id} ({agent.agent_name}): {icon}"
        if agent.issues:
            result_text += f"\n  Issues: {'; '.join(agent.issues)}"
        result_text += "\n"

    if verdict.final_verdict.value == "BLOCKED" and verdict.correction:
        result_text += f"\nCORRECTED OUTPUT:\n{verdict.correction}\n"

    if verdict.issues_summary:
        result_text += "\nSUMMARY OF ISSUES:\n"
        result_text += "\n".join(f"- {issue}" for issue in verdict.issues_summary[:5])

    return result_text


@router.post("")
@router.post("/")
async def handle_mcp_request(request: MCPRequest):
    """Handle MCP-style JSON-RPC requests."""
    if request.method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "ai-hallucination-juror", "version": "1.0.0"},
            },
        }

    if request.method == "notifications/initialized":
        return {"jsonrpc": "2.0", "id": request.id, "result": {}}

    if request.method == "tools/list":
        return {"jsonrpc": "2.0", "id": request.id, "result": TOOLS_LIST}

    if request.method == "tools/call":
        params = request.params or {}
        tool_name = params.get("name")
        arguments = params.get("arguments", {}) or {}

        if tool_name == "verify_output":
            verify_request = VerificationRequest(
                content=arguments.get("content", ""),
                domain=arguments.get("domain"),
                context=arguments.get("context"),
                source="mcp",
            )
            verdict = await run_jury(verify_request)
            await save_verdict(verdict, source="mcp", content=verify_request.content)
            result_text = _format_verdict_text(verdict)
            return {
                "jsonrpc": "2.0",
                "id": request.id,
                "result": {
                    "content": [{"type": "text", "text": result_text}],
                    "isError": verdict.final_verdict.value == "BLOCKED",
                },
            }

        if tool_name == "get_verdict_history":
            history = await get_history(limit=int(arguments.get("limit", 10)))
            return {
                "jsonrpc": "2.0",
                "id": request.id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(history, indent=2, default=str)}]
                },
            }

        if tool_name == "get_stats":
            history = await get_history(limit=1000)
            verdicts = [entry["final_verdict"] for entry in history]
            stats = {
                "total": len(verdicts),
                "approved": verdicts.count("APPROVED"),
                "flagged": verdicts.count("FLAGGED"),
                "blocked": verdicts.count("BLOCKED"),
            }
            return {
                "jsonrpc": "2.0",
                "id": request.id,
                "result": {"content": [{"type": "text", "text": json.dumps(stats, indent=2)}]},
            }

        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "error": {"code": -32601, "message": f"Tool not found: {tool_name}"},
        }

    return {
        "jsonrpc": "2.0",
        "id": request.id,
        "error": {"code": -32601, "message": f"Method not found: {request.method}"},
    }


def create_mcp_router() -> APIRouter:
    return router
