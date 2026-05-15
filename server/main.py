import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

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
        "provider": "Gemini 2.5 Flash",
        "configured": bool(config.GEMINI_API_KEY),
        "server": f"http://localhost:{config.SERVER_PORT}",
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


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    history = await get_history(limit=10)
    stats_raw = await get_history(limit=1000)
    verdicts = [entry["final_verdict"] for entry in stats_raw]
    total = len(verdicts)
    stats = {
        "total": total,
        "approved": verdicts.count("APPROVED"),
        "flagged": verdicts.count("FLAGGED"),
        "blocked": verdicts.count("BLOCKED"),
        "rate": f"{(verdicts.count('BLOCKED') / total * 100):.1f}%" if total else "0%",
    }
    colors = {"APPROVED": "#34d399", "FLAGGED": "#fbbf24", "BLOCKED": "#f87171"}
    rows = "".join(
        f"<tr>"
        f"<td style='color:{colors.get(entry['final_verdict'], '#fff')};font-weight:700'>{entry['final_verdict']}</td>"
        f"<td>{entry.get('domain', '?')}</td>"
        f"<td>{entry.get('fail_count', '?')}/5</td>"
        f"<td>{entry.get('source', '?')}</td>"
        f"<td style='color:#475569'>{str(entry.get('timestamp', ''))[:19]}</td>"
        f"</tr>"
        for entry in history
    ) or "<tr><td colspan='5' style='color:#334155;text-align:center;padding:20px'>No verifications yet</td></tr>"

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="10">
<title>AI Hallucination Juror</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#060a0f;color:#e2e8f0;font-family:'Courier New',monospace;padding:24px}}
h1{{color:#00ff9d;font-size:20px;letter-spacing:2px;margin-bottom:4px}}
.sub{{color:#475569;font-size:11px;margin-bottom:24px}}
.cards{{display:flex;gap:16px;margin-bottom:24px;flex-wrap:wrap}}
.card{{background:#0d1117;border:1px solid #ffffff10;border-radius:8px;padding:14px 18px;min-width:110px}}
.cv{{font-size:26px;font-weight:900;margin-bottom:3px}}
.cl{{color:#475569;font-size:9px;letter-spacing:1px}}
.g{{color:#34d399}}.y{{color:#fbbf24}}.r{{color:#f87171}}.b{{color:#00d4ff}}
table{{width:100%;border-collapse:collapse}}
th{{color:#475569;font-size:9px;letter-spacing:1px;text-align:left;padding:6px 10px;border-bottom:1px solid #ffffff10}}
td{{padding:7px 10px;font-size:11px;border-bottom:1px solid #ffffff06}}
h2{{color:#94a3b8;font-size:11px;letter-spacing:2px;margin-bottom:10px}}
a{{color:#00d4ff;font-size:10px;text-decoration:none}}
.badge{{display:inline-block;background:#00ff9d10;border:1px solid #00ff9d30;color:#00ff9d;padding:1px 7px;border-radius:3px;font-size:9px;letter-spacing:1px}}
</style>
</head>
<body>
<h1>⬡ AI HALLUCINATION JUROR</h1>
<div class="sub">Multi-agent verification · Auto-refreshes every 10s · <span class="badge">LIVE</span></div>
<div class="cards">
  <div class="card"><div class="cv b">{stats["total"]}</div><div class="cl">TOTAL</div></div>
  <div class="card"><div class="cv g">{stats["approved"]}</div><div class="cl">APPROVED</div></div>
  <div class="card"><div class="cv y">{stats["flagged"]}</div><div class="cl">FLAGGED</div></div>
  <div class="card"><div class="cv r">{stats["blocked"]}</div><div class="cl">BLOCKED</div></div>
  <div class="card"><div class="cv r">{stats["rate"]}</div><div class="cl">BLOCK RATE</div></div>
</div>
<h2>RECENT VERDICTS</h2>
<table>
  <thead><tr><th>VERDICT</th><th>DOMAIN</th><th>FAILS</th><th>SOURCE</th><th>TIME</th></tr></thead>
  <tbody>{rows}</tbody>
</table>
<div style="margin-top:20px;color:#1e293b;font-size:10px">
  gemini-2.5-flash · batched 5-agent jury ·
  <a href="/docs">API Docs</a> · <a href="/history">JSON History</a> · <a href="/stats">Stats</a>
</div>
</body>
</html>"""


app.include_router(create_mcp_router(), prefix="/mcp")


if __name__ == "__main__":
    uvicorn.run(
        "server.main:app",
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        reload=False,
        log_level="info",
    )
