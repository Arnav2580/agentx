# AI Hallucination Juror - Technical Documentation

This document describes the implementation that is in the repo now.

## 1. Executive Summary

AI Hallucination Juror is a local verification and interception layer for AI-assisted development.

It currently has two live safety loops:

- **Content Jury** for AI-generated technical text
- **Command Shield** for AI-generated or manually typed shell commands

The same backend serves:

- REST API
- MCP
- terminal CLI / TUI
- VS Code extension
- Chrome extension
- shell hooks
- background daemon

## 2. Current Build Reality

The current build is not the early draft architecture. The live system now works like this:

- provider is **Gemini 2.5 Flash**
- the content jury is **batched**
- Agents 1-5 run through **one structured model call**
- Agent 6 only runs when the verdict is `BLOCKED`
- `server/grok_client.py` is still named after an older provider, but now wraps **Gemini REST**
- command interception uses:
  - regex checks
  - OSV.dev
  - npm registry
  - PyPI
  - Gemini reasoning
- the repo includes:
  - installers
  - a committed VS Code `.vsix`
  - a Chrome extension
  - daemon + hook assets
  - an uninstall command

## 3. Active Runtime Map

### Backend

- `server/main.py`
- `server/config.py`
- `server/models.py`
- `server/database.py`
- `server/domain_detector.py`
- `server/grok_client.py`
- `server/command_checker.py`
- `server/daemon.py`
- `server/hooks/`
- `server/agents/orchestrator.py`
- `server/agents/correction_agent.py`
- `server/mcp_server.py`

### Terminal

- `terminal/cli.py`
- `terminal/app.py`
- `terminal/widgets/`

### VS Code

- `vscode-extension/src/*.ts`
- `vscode-extension/media/*`
- `vscode-extension/ai-hallucination-juror-1.0.0.vsix`

### Chrome

- `chrome-extension/manifest.json`
- `chrome-extension/background.js`
- `chrome-extension/content/content.js`
- `chrome-extension/popup/*`

### Installers

- `install.sh`
- `install.ps1`

## 4. Content Verification Flow

### REST or UI path

1. A surface captures text
2. It sends `POST /verify`
3. The backend trims content to `REQUEST_CHAR_LIMIT`
4. Domain detection runs
5. The orchestrator sends one batched Gemini request for Agents 1-5
6. The backend counts `FAIL` votes
7. It returns `APPROVED`, `FLAGGED`, or `BLOCKED`
8. If `BLOCKED`, Agent 6 generates a correction
9. The verdict is saved to SQLite
10. The calling surface renders the result

### MCP path

1. An MCP client calls `/mcp`
2. `tools/list` exposes:
   - `verify_output`
   - `get_verdict_history`
   - `get_stats`
3. `verify_output` builds a `VerificationRequest`
4. The same `run_jury()` path is used
5. The result is formatted as readable MCP text

## 5. Command Shield Flow

The command checker lives in [server/command_checker.py](server/command_checker.py).

### Runtime path

1. A shell hook, agent hook, CLI command, or VS Code panel sends `POST /check-command`
2. Fast regex analysis runs first
3. Package names are extracted from install commands
4. Threat intel is fetched concurrently from:
   - OSV.dev
   - npm registry
   - PyPI
5. Gemini reasoning runs for suspicious or ambiguous commands
6. The server returns:
   - `SAFE`
   - `WARN`
   - `BLOCK`
7. The result is stored in `command_checks`
8. VS Code and other surfaces can poll `/command-history`

### Key behavior

- clearly destructive patterns escalate to `BLOCK`
- missing packages escalate to `BLOCK`
- vulnerable or suspiciously new packages escalate to at least `WARN`
- obviously harmless commands can short-circuit locally to avoid wasting model quota

## 6. Backend API

### `GET /`

Returns a lightweight HTML dashboard with:

- total verdicts
- approved count
- flagged count
- blocked count
- block rate
- recent history table

### `GET /health`

Returns backend status, model, provider, and server URL.

### `POST /verify`

Accepts content verification requests and returns a full `VerdictResponse`.

### `GET /history`

Returns recent saved content verdicts from SQLite.

### `GET /stats`

Returns aggregate counts and `block_rate`.

### `POST /check-command`

Accepts:

```json
{
  "command": "npm install lodash",
  "source": "vscode_manual",
  "working_dir": "/optional/path",
  "context": "optional AI task context"
}
```

Returns:

```json
{
  "verdict": "SAFE",
  "confidence": 0.98,
  "reasons": [],
  "suggestion": "",
  "category": "safe",
  "packages_checked": []
}
```

### `GET /command-history`

Returns recent command checks for the VS Code Command Shield panel and other local surfaces.

## 7. Configuration

The backend loads environment variables from:

1. `~/.juror/.env`
2. repo `.env`

Important keys:

```env
GEMINI_API_KEY=...
MODEL=gemini-2.5-flash
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
REQUEST_CHAR_LIMIT=8000
APPROVED_THRESHOLD=1
FLAGGED_THRESHOLD=2
BLOCKED_THRESHOLD=3
AGENT_TIMEOUT_SECONDS=30
```

Compatibility note:

- `server/config.py` still accepts `GROK_API_KEY` as a fallback env name
- the live runtime uses `GEMINI_API_KEY`

## 8. Gemini Client

[server/grok_client.py](server/grok_client.py) is the shared model client.

Despite the filename, it now:

- calls Gemini over raw HTTP with `httpx`
- targets `generativelanguage.googleapis.com`
- supports plain text calls
- supports JSON mode
- supports schema-shaped responses

Default behavior:

- low temperature
- no thinking budget
- raises on empty or malformed model output

## 9. Domain Detection

Domain detection happens before the jury call.

### Primary path

Gemini is asked to return one of:

- `civil_engineering`
- `mechanical_engineering`
- `software_development`
- `financial_modeling`
- `healthcare`
- `infrastructure`
- `construction`
- `general`

### Fallback path

If Gemini fails, keyword heuristics are used.

## 10. Jury Logic

The live jury implementation is in [server/agents/orchestrator.py](server/agents/orchestrator.py).

### Batched agent model

The orchestrator builds one structured prompt containing five roles:

1. Fact Verifier
2. Math Validator
3. Standards Checker
4. Logic Auditor
5. Domain Expert

Gemini returns one JSON object containing all five results.

### Final verdict thresholds

- `0-1 FAIL` -> `APPROVED`
- `2 FAIL` -> `FLAGGED`
- `3+ FAIL` -> `BLOCKED`

### Safety guard

If every agent comes back `UNCERTAIN`, the final result is forced to `FLAGGED`.

### Correction flow

If the verdict is `BLOCKED`:

1. issues are flattened and deduped
2. `run_correction_agent()` is called
3. a unified diff is generated against the original content

## 11. Correction Agent

[server/agents/correction_agent.py](server/agents/correction_agent.py) first tries local fallback corrections for known demo cases, then falls back to Gemini when needed.

This keeps demos stable and reduces unnecessary model usage.

## 12. Storage

SQLite is handled in [server/database.py](server/database.py).

Database path:

```text
~/.juror/verdicts.db
```

### Tables

`verdicts`

- request id
- timestamp
- domain
- final verdict
- fail count
- source
- content preview
- full response JSON

`command_checks`

- command preview
- verdict
- category
- source
- reasons
- suggestion
- created timestamp

## 13. Daemon

The background daemon lives in [server/daemon.py](server/daemon.py).

### Responsibilities

- runs silently in the background
- watches sensitive files
- logs activity to `~/.juror/activity.log`
- writes event records to `~/.juror/events.jsonl`
- sends desktop notifications for sensitive changes
- exposes a tiny local event server on `127.0.0.1:8001`

### CLI controls

- `juror daemon start`
- `juror daemon status`
- `juror daemon logs`
- `juror stop`
- `juror wakeup`

## 14. Hooks

Hook assets live in [server/hooks](server/hooks).

### `intercept.py`

For AI agents that support pre-tool hooks.

Current behavior:

- reads JSON from stdin
- extracts shell commands
- calls `/check-command`
- logs activity
- shows desktop notifications
- exits with `2` on `BLOCK` for compatible tools

### `shell_hook.sh`

For Bash and Zsh style shell integration.

Current behavior:

- looks for risky command patterns
- calls `/check-command`
- prints warnings inline to the terminal
- logs results to `~/.juror/activity.log`

### Claude template

`claude_settings_template.json` is merged by `juror install` when `~/.claude/settings.json` is present.

## 15. Terminal Surface

[terminal/cli.py](terminal/cli.py) now provides:

- `juror start`
- `juror start --no-tui`
- `juror run <command>`
- `juror verify <file>`
- `juror check "<command>"`
- `juror install`
- `juror uninstall --yes`
- `juror daemon start`
- `juror daemon status`
- `juror daemon logs`
- `juror stop`
- `juror wakeup`
- `juror status`
- `juror history`
- `juror logs`
- `juror install-service`

The TUI still shows captured AI output, live jury status, verdict banners, and history.

## 16. VS Code Extension

The VS Code extension now has two live responsibilities:

- content verification
- command monitoring

### User-facing behavior

- activity bar Juror panel
- verify current file
- verify selected text
- status bar item
- optional auto-verify on save
- verdict sidebar with agent details
- **Command Shield** feed for recent intercepted commands
- **Check a command** action from the sidebar

## 17. Chrome Extension

The Chrome extension remains the browser-side content surface.

### Current behavior

- content script runs on `<all_urls>`
- auto-monitoring on known AI sites
- manual selection scan on any page
- floating `JUROR` button
- Shadow DOM sidebar
- page push instead of overlap

`content/sidebar.css` is intentionally empty because the real styles live inside the Shadow DOM content script.

## 18. Installers And Uninstall

Installers:

- `install.sh`
- `install.ps1`

They:

- clone or update `~/.juror-app`
- install Python dependencies
- save the Gemini key to `~/.juror/.env`
- create the `juror` command
- install the bundled VS Code extension when possible

### Uninstall

`juror uninstall --yes` removes the installed Juror footprint:

- `~/.juror-app`
- `~/.juror`
- installed hook files
- daemon state
- local VS Code extension folders that match Juror
- shell hook lines
- Claude hook entries
- platform service files when present

It intentionally does **not** auto-delete an unrelated developer checkout of the repo.

## 19. Demo Scenarios

Expected outputs:

| File | Expected |
|---|---|
| `civil_engineering.py` | `BLOCKED` |
| `financial_modeling.py` | `FLAGGED` |
| `software_dev.py` | `BLOCKED` |
| `healthcare.py` | `BLOCKED` |

## 20. Known Limitations

1. the live jury is prompt-batched, not five separate model workers
2. legacy agent files still exist and can confuse contributors
3. Agent 6 output is not re-verified by a second jury pass
4. browser selectors will still need maintenance as AI sites change
5. shell hooks are advisory in some environments and cannot always hard-block execution
6. command intel depends on public registry availability

## 21. Current File Structure

```text
server/                      FastAPI backend, command shield, daemon, hooks, MCP, jury
server/agents/               active orchestrator + correction agent, legacy agent modules
terminal/                    CLI and Textual dashboard
vscode-extension/            VS Code source, media, compiled output, bundled VSIX
chrome-extension/            manifest, content script, popup, icons
tests/demo_scenarios/        repeatable demo inputs with runnable client code
install.sh                   macOS / Linux one-command installer
install.ps1                  Windows one-command installer
README.md                    repo quick-start
JUDGE_SETUP.md               fast install guide for judges
ARCHITECTURE_MERMAID.md      system map
```
