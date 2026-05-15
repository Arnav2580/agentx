import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import aiosqlite
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .agents.orchestrator import run_jury
from .command_checker import check_command
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


class CommandCheckRequest(BaseModel):
    command: str
    source: str = "unknown"
    working_dir: Optional[str] = None
    context: Optional[str] = None


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


@app.post("/check-command")
async def check_command_endpoint(request: CommandCheckRequest):
    if not request.command.strip():
        return {"verdict": "SAFE", "reasons": [], "suggestion": ""}

    result = await check_command(request.command, request.source)

    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO command_checks
            (command_preview, verdict, category, source, reasons, suggestion, created_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                request.command[:120],
                result.verdict,
                result.category,
                request.source,
                json.dumps(result.reasons),
                result.suggestion,
            ),
        )
        await db.commit()

    return {
        "verdict": result.verdict,
        "confidence": result.confidence,
        "reasons": result.reasons,
        "suggestion": result.suggestion,
        "category": result.category,
        "packages_checked": [
            {
                "package": package.package,
                "ecosystem": package.ecosystem,
                "exists": package.exists,
                "cve_count": package.cve_count,
                "age_days": package.age_days,
                "weekly_downloads": package.weekly_downloads,
            }
            for package in result.packages_checked
        ],
    }


@app.get("/command-history")
async def command_history(limit: int = 20):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM command_checks ORDER BY id DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
    return {"history": [dict(row) for row in rows]}


@app.post("/scan-workspace")
async def trigger_workspace_scan():
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post("http://127.0.0.1:8001/scan")
        return {"status": "success", "message": "Manual workspace scan completed successfully!"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to trigger scan: {e}. Is the daemon running?"}


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
<title>AI Hallucination Juror Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg-base: #020617;
    --bg-surface: #0f172a;
    --primary: #38bdf8;
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
    --text-main: #f8fafc;
    --text-muted: #94a3b8;
    --border: #1e293b;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }}
  body {{ 
    background: radial-gradient(circle at top right, #1e1b4b 0%, var(--bg-base) 40%);
    color: var(--text-main);
    padding: 40px;
    min-height: 100vh;
  }}
  .container {{ max-width: 1000px; margin: 0 auto; }}
  .header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 40px; }}
  .header-titles h1 {{ font-size: 28px; font-weight: 800; letter-spacing: -0.02em; background: linear-gradient(90deg, #fff, #94a3b8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
  .header-titles .sub {{ color: var(--text-muted); font-size: 13px; margin-top: 6px; }}
  .badge {{ background: rgba(16, 185, 129, 0.15); color: var(--success); border: 1px solid rgba(16, 185, 129, 0.3); padding: 4px 10px; border-radius: 999px; font-size: 11px; font-weight: 600; letter-spacing: 0.05em; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 0 12px rgba(16, 185, 129, 0.2); }}
  .badge::before {{ content: ''; width: 6px; height: 6px; background: var(--success); border-radius: 50%; animation: pulse 2s infinite; }}
  @keyframes pulse {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0.4; }} 100% {{ opacity: 1; }} }}
  
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 20px; margin-bottom: 40px; }}
  .card {{ background: rgba(15, 23, 42, 0.6); backdrop-filter: blur(12px); border: 1px solid var(--border); border-radius: 16px; padding: 24px; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2); transition: transform 0.2s ease, box-shadow 0.2s ease; }}
  .card:hover {{ transform: translateY(-2px); box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3); border-color: rgba(255, 255, 255, 0.1); }}
  .cv {{ font-size: 36px; font-weight: 800; margin-bottom: 8px; letter-spacing: -0.02em; }}
  .cl {{ color: var(--text-muted); font-size: 11px; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase; }}
  
  .g {{ color: var(--success); text-shadow: 0 0 20px rgba(16, 185, 129, 0.4); }}
  .y {{ color: var(--warning); text-shadow: 0 0 20px rgba(245, 158, 11, 0.4); }}
  .r {{ color: var(--danger); text-shadow: 0 0 20px rgba(239, 68, 68, 0.4); }}
  .b {{ color: var(--primary); text-shadow: 0 0 20px rgba(56, 189, 248, 0.4); }}
  
  .table-container {{ background: rgba(15, 23, 42, 0.6); backdrop-filter: blur(12px); border: 1px solid var(--border); border-radius: 16px; overflow: hidden; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2); }}
  .table-header {{ padding: 20px 24px; border-bottom: 1px solid var(--border); }}
  .table-header h2 {{ font-size: 15px; font-weight: 600; color: var(--text-main); }}
  table {{ width: 100%; border-collapse: collapse; text-align: left; }}
  th {{ color: var(--text-muted); font-size: 11px; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase; padding: 16px 24px; border-bottom: 1px solid var(--border); background: rgba(0,0,0,0.2); }}
  td {{ padding: 16px 24px; font-size: 13px; border-bottom: 1px solid rgba(255, 255, 255, 0.03); color: var(--text-main); }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: rgba(255, 255, 255, 0.02); }}
  
  .footer {{ margin-top: 30px; text-align: center; color: var(--text-muted); font-size: 12px; }}
  .footer a {{ color: var(--primary); text-decoration: none; margin: 0 8px; transition: color 0.2s; }}
  .footer a:hover {{ color: #fff; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="header-titles">
      <h1>AI Hallucination Juror</h1>
      <div class="sub">Multi-agent verification dashboard · gemini-2.5-flash</div>
    </div>
    <div style="display: flex; gap: 12px; align-items: center;">
      <button onclick="fetch('/scan-workspace', {method: 'POST'}).then(r=>r.json()).then(d=>alert(d.message))" style="background: var(--primary); color: #fff; border: none; padding: 6px 14px; border-radius: 999px; font-weight: 600; font-size: 12px; cursor: pointer; transition: all 0.2s; box-shadow: 0 4px 12px rgba(56, 189, 248, 0.3);">Run Workspace Scan</button>
      <div class="badge">SYSTEM LIVE</div>
    </div>
  </div>
  
  <div class="cards">
    <div class="card"><div class="cv b">{stats["total"]}</div><div class="cl">Total Scans</div></div>
    <div class="card"><div class="cv g">{stats["approved"]}</div><div class="cl">Approved</div></div>
    <div class="card"><div class="cv y">{stats["flagged"]}</div><div class="cl">Flagged</div></div>
    <div class="card"><div class="cv r">{stats["blocked"]}</div><div class="cl">Blocked</div></div>
    <div class="card"><div class="cv r">{stats["rate"]}</div><div class="cl">Block Rate</div></div>
  </div>
  
  <div class="table-container">
    <div class="table-header"><h2>Recent Verdicts</h2></div>
    <table>
      <thead><tr><th>Verdict</th><th>Domain</th><th>Fails</th><th>Source</th><th>Time</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
  
  <div class="footer">
    <span>Auto-refreshes every 10s</span>
    <a href="/docs">API Docs</a>
    <a href="/history">JSON History</a>
    <a href="/stats">Stats</a>
  </div>
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
