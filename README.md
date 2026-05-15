# AI Hallucination Juror

AI Hallucination Juror is a multi-surface verification layer for AI-generated technical output. It puts a jury between an AI answer and the developer by running a 5-agent review plus an optional correction pass before the output is accepted.

Today the project ships as:

- a FastAPI backend with REST + MCP
- a terminal CLI and Textual dashboard
- a VS Code extension with sidebar, commands, and decorations
- a Chrome extension that can auto-scan known AI sites and manually scan text on any page

## Current Runtime

| Component | Current implementation |
|---|---|
| Model provider | Google Gemini 2.5 Flash |
| Main verification path | Batched 5-agent jury in one model call |
| Correction path | Second model call only when verdict is `BLOCKED` |
| Health route | `GET /health` |
| Dashboard | `GET /` |
| Storage | SQLite at `~/.juror/verdicts.db` |
| Default server | `http://localhost:8000` |

## What It Does

- verifies AI-generated technical content before it is trusted
- returns `APPROVED`, `FLAGGED`, or `BLOCKED`
- stores verdict history and summary stats
- exposes the jury over HTTP and MCP
- works across terminal, VS Code, Chrome, and any tool that can call the API

## One-Command Install

### macOS / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/Arnav2580/agentx/main/install.sh | bash
```

### Windows PowerShell

```powershell
irm https://raw.githubusercontent.com/Arnav2580/agentx/main/install.ps1 | iex
```

The installers:

- clone the repo into `~/.juror-app`
- install Python dependencies
- create `~/.juror/.env`
- install the `juror` command
- install the bundled VS Code `.vsix` when `code` is available

Chrome still requires a one-time manual "Load Unpacked" step because browsers do not allow silent extension installation.

## Manual Developer Setup

```bash
git clone https://github.com/Arnav2580/agentx.git
cd agentx
python -m venv .venv
```

### Windows

```powershell
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m server.main
```

### macOS / Linux

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m server.main
```

Open:

- `http://localhost:8000` for the live dashboard
- `http://localhost:8000/docs` for API docs
- `http://localhost:8000/health` for a quick health check

## Environment

Create `.env` in the repo root, or use `~/.juror/.env`.

```env
GEMINI_API_KEY=your_api_key_here
MODEL=gemini-2.5-flash
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
REQUEST_CHAR_LIMIT=8000
```

Load order:

1. `~/.juror/.env`
2. local repo `.env`

The global file is loaded first and is convenient for installers and judge machines.

## Core Usage

### Start the server and terminal dashboard

```bash
juror start
```

### Start backend only

```bash
juror start --no-tui
```

### Verify a file

```bash
juror verify tests/demo_scenarios/software_dev.py
```

### Wrap an AI CLI command

```bash
juror run claude "write a structural load calculation for Zone IV India"
```

### Check status and history

```bash
juror status
juror history
juror logs
```

## API and MCP

### REST routes

- `GET /`
- `GET /health`
- `POST /verify`
- `GET /history`
- `GET /stats`

### MCP endpoint

```bash
claude mcp add juror http://localhost:8000/mcp
```

Available MCP tools:

- `verify_output`
- `get_verdict_history`
- `get_stats`

## Surfaces

### Chrome extension

- content script runs on `<all_urls>`
- auto-monitor is enabled only for known AI sites
- any site can be scanned manually with:
  - the floating `JUROR` button
  - selected text + `Ctrl+Shift+J`
- sidebar is rendered inside a Shadow DOM panel
- opening the sidebar shifts the page left instead of covering content

Load it once:

1. open `chrome://extensions`
2. enable Developer Mode
3. click Load Unpacked
4. select `chrome-extension/`

### VS Code extension

Included package:

- `vscode-extension/ai-hallucination-juror-1.0.0.vsix`

Install manually if needed:

```bash
code --install-extension vscode-extension/ai-hallucination-juror-1.0.0.vsix --force
```

Features:

- `Juror: Verify Selected Text`
- `Juror: Verify Current File`
- sidebar panel
- status bar item
- optional auto-verify on save

### Terminal UI

The TUI shows:

- captured AI output
- live jury status
- verdict banner
- recent verdict history

## Demo Scenarios

Use the included scenario files when you want repeatable demo results:

```bash
python tests/demo_scenarios/civil_engineering.py
python tests/demo_scenarios/financial_modeling.py
python tests/demo_scenarios/software_dev.py
python tests/demo_scenarios/healthcare.py
```

Expected outcomes:

- `civil_engineering` -> `BLOCKED`
- `financial_modeling` -> `FLAGGED`
- `software_dev` -> `BLOCKED`
- `healthcare` -> `BLOCKED`

## Important Implementation Notes

### The live runtime is batched

The active verification path lives in [server/agents/orchestrator.py](server/agents/orchestrator.py). It sends one batched prompt to Gemini for Agents 1-5, then only calls the correction agent if the result is `BLOCKED`.

### `grok_client.py` is a legacy filename

[server/grok_client.py](server/grok_client.py) no longer calls Grok. It is now a thin Gemini REST client kept under the old name to avoid breaking imports.

### Some agent files are legacy reference modules

These files still exist but are not the main live path:

- `server/agents/fact_verifier.py`
- `server/agents/math_validator.py`
- `server/agents/standards_checker.py`
- `server/agents/logic_auditor.py`
- `server/agents/domain_expert.py`

The active files are:

- `server/main.py`
- `server/config.py`
- `server/grok_client.py`
- `server/domain_detector.py`
- `server/database.py`
- `server/models.py`
- `server/agents/orchestrator.py`
- `server/agents/correction_agent.py`

## Repo Map

```text
server/              FastAPI backend, MCP, config, storage, jury
terminal/            CLI + Textual dashboard
vscode-extension/    VS Code extension source + packaged VSIX
chrome-extension/    Chrome extension source
tests/               demo scenarios and backend tests
install.sh           macOS / Linux installer
install.ps1          Windows installer
```

## Docs In This Repo

- [documentation.md](documentation.md) - detailed technical walkthrough
- [JUDGE_SETUP.md](JUDGE_SETUP.md) - fast setup instructions for judges
- [ARCHITECTURE_MERMAID.md](ARCHITECTURE_MERMAID.md) - code-to-system Mermaid map

