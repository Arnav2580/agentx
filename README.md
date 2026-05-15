# AI Hallucination Juror

AI Hallucination Juror is a multi-agent verification layer for AI-generated technical output. It exposes a FastAPI + MCP backend, a terminal dashboard, a VS Code extension, and a Chrome extension so developers can run the same "jury" across multiple surfaces.

## What it does

- Intercepts AI-generated technical content
- Runs five verification agents plus a correction agent
- Produces `APPROVED`, `FLAGGED`, or `BLOCKED` verdicts
- Stores verdict history in SQLite
- Exposes the jury over HTTP and MCP JSON-RPC

## Surfaces

- `server/`: FastAPI backend + MCP endpoint
- `terminal/`: Textual TUI + CLI
- `vscode-extension/`: VS Code sidebar and commands
- `chrome-extension/`: Chrome Manifest V3 extension

## Quick start

```bash
cd juror
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m server.main
```

Open `http://localhost:8000/docs` for the API docs and `http://localhost:8000/health` for a quick health check.

## Environment

Create `.env` in the project root:

```env
GROK_API_KEY=your_api_key_here
MODEL=grok-3-mini
SERVER_PORT=8000
```

If `GROK_API_KEY` is missing, the server falls back to lightweight heuristic checks so the demo paths still behave.

## CLI

```bash
juror start
juror status
juror verify tests/demo_scenarios/software_dev.py
juror history
```

## MCP setup

```bash
claude mcp add juror http://localhost:8000/mcp
```

## Notes

- Verdict history is stored under `~/.juror/verdicts.db`
- The Chrome extension expects the backend at `http://localhost:8000`
- The VS Code extension compiles to `vscode-extension/out`
