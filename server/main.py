import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .agents.orchestrator import run_jury
from .config import config
from .database import get_history, init_db, save_verdict
from .mcp_server import create_mcp_router
from .models import VerificationRequest, VerdictResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(config.LOG_PATH).parent.mkdir(parents=True, exist_ok=True)
    await init_db()
    print(f"Juror MCP Server started on http://localhost:{config.SERVER_PORT}")
    print(f"Verdict database: {config.DB_PATH}")
    yield
    print("Juror MCP Server stopped")


app = FastAPI(
    title="AI Hallucination Juror",
    description="Multi-agent verification system for AI-generated technical content",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {
        "status": "running",
        "version": "1.0.0",
        "model": config.MODEL,
        "server": f"http://localhost:{config.SERVER_PORT}",
        "grok_configured": bool(config.GROK_API_KEY),
    }


@app.post("/verify", response_model=VerdictResponse)
async def verify_output(request: VerificationRequest):
    if not request.content or len(request.content.strip()) < 10:
        raise HTTPException(status_code=400, detail="Content too short to verify")

    request.content = request.content[: config.REQUEST_CHAR_LIMIT]
    verdict = await run_jury(request)
    await save_verdict(verdict, source=request.source or "api", content=request.content)
    return verdict


@app.get("/history")
async def get_verdict_history(limit: int = 20):
    history = await get_history(limit=limit)
    return {"history": history, "count": len(history)}


@app.get("/stats")
async def get_stats():
    history = await get_history(limit=1000)
    if not history:
        return {"total": 0, "approved": 0, "flagged": 0, "blocked": 0, "block_rate": "0.0%"}

    verdicts = [entry["final_verdict"] for entry in history]
    blocked = verdicts.count("BLOCKED")
    return {
        "total": len(verdicts),
        "approved": verdicts.count("APPROVED"),
        "flagged": verdicts.count("FLAGGED"),
        "blocked": blocked,
        "block_rate": f"{(blocked / len(verdicts) * 100):.1f}%",
    }


app.include_router(create_mcp_router(), prefix="/mcp")


if __name__ == "__main__":
    uvicorn.run(
        "server.main:app",
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        reload=False,
        log_level="info",
    )
