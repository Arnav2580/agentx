# AI Hallucination Juror

AI Hallucination Juror is a local safety layer for AI-generated technical output and AI-generated terminal commands.

It now ships in two connected modes:

- **Content Jury**: a batched 5-agent review plus an optional correction pass for technical text
- **Command Shield**: command interception, threat intel, and risk scoring for shell commands before they run

The same backend powers:

- FastAPI + MCP
- terminal CLI + Textual UI
- VS Code extension
- Chrome extension
- shell and AI-agent hooks
- background daemon

## Current Runtime

| Component | Current implementation |
|---|---|
| Model provider | Google Gemini 2.5 Flash |
| Content verification path | Batched 5-agent jury in one model call |
| Correction path | Second model call only when verdict is `BLOCKED` |
| Command analysis path | Regex + OSV.dev + npm/PyPI intel + Gemini reasoning |
| Health route | `GET /health` |
| Dashboard | `GET /` |
| Storage | SQLite at `~/.juror/verdicts.db` |
| Command history | SQLite table `command_checks` |
| Default server | `http://localhost:8000` |
| Daemon event feed | `http://127.0.0.1:8001/events` |

## What It Does

- verifies AI-generated technical content before it is trusted
- returns `APPROVED`, `FLAGGED`, or `BLOCKED`
- generates a correction when content is blocked
- intercepts risky commands from AI agents and shells
- checks package installs against OSV.dev, npm, and PyPI
- stores verdict history and command history
- exposes the system over HTTP and MCP

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
- create the `juror` command
- install the bundled VS Code `.vsix` when `code` is available

Chrome still requires a one-time manual **Load Unpacked** step.

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

## Core CLI Usage

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

### Install hooks and start the daemon

```bash
juror install
```

### Check a command manually

```bash
juror check "npm install react-query-optimizer"
juror check "rm -rf /"
```

### Daemon controls

```bash
juror daemon start
juror daemon status
juror daemon logs
juror stop
juror wakeup
```

### Status and history

```bash
juror status
juror history
juror logs
```

### Uninstall the installed footprint

```bash
juror uninstall --yes
```

This removes the installed Juror footprint under `~/.juror-app` and `~/.juror`, along with hooks, daemon state, and local VS Code extension copies. If you also have a separate dev clone somewhere else, delete that folder manually when you are done with it.

## Command Shield

Juror can now inspect shell commands before they run.

The command pipeline is:

1. fast regex pattern analysis
2. package extraction
3. free threat intel from:
   - OSV.dev
   - npm registry
   - PyPI
4. Gemini reasoning for suspicious or ambiguous commands

Verdicts:

- `SAFE`
- `WARN`
- `BLOCK`

### Hook assets

Installed by `juror install`:

- `~/.juror/hooks/intercept.py`
- `~/.juror/hooks/shell_hook.sh`
- Claude Code hook template merged into `~/.claude/settings.json` when possible

## API and MCP

### REST routes

- `GET /`
- `GET /health`
- `POST /verify`
- `GET /history`
- `GET /stats`
- `POST /check-command`
- `GET /command-history`

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
- known AI sites auto-scan after a response finishes
- any page can be scanned manually
- floating `JUROR` button stays visible
- sidebar lives in Shadow DOM and pushes the page instead of covering it

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
- **Command Shield** feed with recent intercepted commands
- manual command-check action from inside the sidebar

### Terminal UI

The TUI shows:

- captured AI output
- live jury status
- verdict banner
- recent verdict history

## Demo Scenarios

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

## Active Runtime Notes

### The live jury is batched

The active verification path lives in [server/agents/orchestrator.py](server/agents/orchestrator.py). It sends one batched prompt to Gemini for Agents 1-5, then only calls the correction agent if the result is `BLOCKED`.

### `grok_client.py` is a legacy filename

[server/grok_client.py](server/grok_client.py) no longer calls Grok. It is a thin Gemini REST client kept under the old name to avoid breaking imports.

### Legacy agent modules still exist

These files are not the main live path:

- `server/agents/fact_verifier.py`
- `server/agents/math_validator.py`
- `server/agents/standards_checker.py`
- `server/agents/logic_auditor.py`
- `server/agents/domain_expert.py`

## Repo Map

```text
server/              FastAPI backend, MCP, config, storage, jury, command shield, daemon, hooks
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
