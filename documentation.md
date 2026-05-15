# AI Hallucination Juror - Technical Documentation

This document describes the implementation that is in the repo now, not the earlier draft architecture.

## 1. Executive Summary

AI Hallucination Juror is a local verification layer for AI-generated technical output. It sits between an answer and the developer, evaluates the content with a 5-agent jury, and returns a final verdict:

- `APPROVED`
- `FLAGGED`
- `BLOCKED`

If the result is `BLOCKED`, a sixth agent generates a correction.

The same backend powers five access patterns:

- REST API
- MCP
- terminal CLI / TUI
- VS Code extension
- Chrome extension

## 2. What Changed In The Current Build

The current build is different from the earlier multi-file, multi-provider drafts.

### Current reality

- provider is **Gemini 2.5 Flash**
- the main jury is **batched**
- agents 1-5 are run through **one structured model call**
- Agent 6 is only called for `BLOCKED`
- the file named `grok_client.py` now wraps **Gemini REST**, not Grok
- the Chrome extension now uses a **floating toggle pill**, **Shadow DOM sidebar**, and **page push**
- the repo now includes:
  - one-command installers
  - a committed VS Code `.vsix`
  - a live dashboard at `/`

### Legacy but still present

These modules still exist, but they are not the main runtime path:

- `server/agents/fact_verifier.py`
- `server/agents/math_validator.py`
- `server/agents/standards_checker.py`
- `server/agents/logic_auditor.py`
- `server/agents/domain_expert.py`

They are useful as reference prompts and fallback implementation history, but the active verdict path runs through `server/agents/orchestrator.py`.

## 3. Active Runtime Map

### Backend

- `server/main.py`
- `server/config.py`
- `server/models.py`
- `server/database.py`
- `server/domain_detector.py`
- `server/grok_client.py`
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

## 4. End-to-End Request Flow

### REST or UI flow

1. A surface captures text
2. It sends `POST /verify`
3. The backend trims the content to `REQUEST_CHAR_LIMIT`
4. The orchestrator detects the domain
5. The orchestrator sends one batched Gemini request for Agents 1-5
6. The backend counts `FAIL` votes
7. It returns `APPROVED`, `FLAGGED`, or `BLOCKED`
8. If `BLOCKED`, Agent 6 generates a correction
9. The verdict is saved to SQLite
10. The surface renders the result

### MCP flow

1. An MCP client calls `/mcp`
2. `tools/list` exposes:
   - `verify_output`
   - `get_verdict_history`
   - `get_stats`
3. `verify_output` builds a `VerificationRequest`
4. The same `run_jury()` path is used
5. The result is formatted as readable MCP text

## 5. Backend API

### `GET /`

Returns a lightweight HTML dashboard with:

- total verdicts
- approved count
- flagged count
- blocked count
- block rate
- recent history table

### `GET /health`

Current response shape:

```json
{
  "status": "running",
  "version": "1.0.0",
  "model": "gemini-2.5-flash",
  "provider": "Gemini 2.5 Flash",
  "configured": true,
  "server": "http://localhost:8000"
}
```

### `POST /verify`

Accepts:

```json
{
  "content": "AI-generated output to verify",
  "domain": "software_development",
  "context": "optional file path or prompt",
  "source": "chrome"
}
```

Returns a full `VerdictResponse` with:

- per-agent results
- final verdict
- confidence
- issues summary
- optional correction
- optional correction diff

### `GET /history`

Returns recent saved verdicts from SQLite.

### `GET /stats`

Returns aggregate counts and `block_rate`.

## 6. Configuration

The backend loads environment variables from:

1. `~/.juror/.env`
2. repo `.env`

Current important keys:

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

### Important compatibility note

`server/config.py` still accepts `GROK_API_KEY` as a fallback env name, but the live runtime uses `GEMINI_API_KEY`.

## 7. The Gemini Client

The file [server/grok_client.py](server/grok_client.py) is the shared model client.

Despite the filename, it now:

- calls Gemini over raw HTTP with `httpx`
- targets `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
- supports:
  - plain text calls
  - JSON mode
  - response schema hints

Key behavior:

- `temperature=0.1`
- `thinkingBudget=0`
- raises if Gemini returns no candidates or empty text

## 8. Domain Detection

Domain detection happens before the jury call.

### Primary path

`server/domain_detector.py` asks Gemini to return one of:

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

Examples:

- `seismic`, `base shear`, `IS 875` -> `civil_engineering`
- `npm`, `react`, `api`, `typescript` -> `software_development`
- `compound interest`, `IRR`, `principal` -> `financial_modeling`
- `paracetamol`, `mg/kg`, `patient` -> `healthcare`

## 9. Jury Logic

The live jury implementation is in [server/agents/orchestrator.py](server/agents/orchestrator.py).

### Batched agent model

Instead of calling five model endpoints separately, the orchestrator builds one JSON-shaped prompt containing all five roles:

1. Fact Verifier
2. Math Validator
3. Standards Checker
4. Logic Auditor
5. Domain Expert

Gemini returns one JSON object containing five agent payloads.

### Structured response parsing

The orchestrator:

- requests JSON mode
- provides a response schema
- parses the result with `parse_agent_json()`
- converts each agent object into `AgentResult`

### Fail counting

Only `FAIL` values count toward the final verdict.

Thresholds:

- `0-1 FAIL` -> `APPROVED`
- `2 FAIL` -> `FLAGGED`
- `3+ FAIL` -> `BLOCKED`

### Safety guard

If every agent comes back `UNCERTAIN`, the result is forced to `FLAGGED` instead of accidentally passing.

### Correction flow

If the verdict is `BLOCKED`:

1. all issues are flattened and deduped
2. `run_correction_agent()` is called
3. a unified diff is generated against the original content

## 10. Correction Agent

The correction path lives in [server/agents/correction_agent.py](server/agents/correction_agent.py).

### Current behavior

- first tries local fallback corrections for known demo cases
- only calls Gemini when no local correction matches

Current built-in fallback corrections exist for:

- hallucinated React Query package usage
- incorrect compound interest formula
- unsafe pediatric paracetamol dose
- unsafe seismic conclusion wording

This keeps demo behavior stable and reduces unnecessary model usage.

## 11. Storage

SQLite is handled in [server/database.py](server/database.py).

Verdicts are stored in:

```text
~/.juror/verdicts.db
```

Each row stores:

- request id
- timestamp
- domain
- final verdict
- fail count
- source
- content preview
- full response JSON

## 12. Terminal Surface

The terminal experience has two layers:

### CLI

[terminal/cli.py](terminal/cli.py) provides:

- `juror start`
- `juror start --no-tui`
- `juror run <command>`
- `juror verify <file>`
- `juror status`
- `juror history`
- `juror logs`
- `juror install-service`

### Textual dashboard

[terminal/app.py](terminal/app.py) shows:

- captured AI output
- live jury log
- verdict banner
- recent history

The current TUI has been polished for demo use with clearer placeholders, verdict coloring, and summary output.

## 13. VS Code Extension

The VS Code extension lives under `vscode-extension/`.

### Current user-facing behavior

- activity bar Juror panel
- verify current file
- verify selected text
- status bar button
- optional auto-verify on save
- decorated warning states for flagged or blocked results

### Important files

- `src/extension.ts`
- `src/jurorClient.ts`
- `src/sidebarProvider.ts`
- `src/fileWatcher.ts`
- `src/decorationProvider.ts`
- `media/sidebar.html`
- `media/sidebar.css`
- `media/sidebar.js`

### Packaged artifact

The repo includes:

```text
vscode-extension/ai-hallucination-juror-1.0.0.vsix
```

That is the easiest installation path for judges.

## 14. Chrome Extension

The Chrome extension now behaves very differently from the earlier draft.

### Current model

- content script loads on `<all_urls>`
- auto-monitor only runs on known AI sites
- manual verification works on any page
- a floating `JUROR` pill is always available
- the sidebar is rendered in a Shadow DOM host
- opening the sidebar pushes the page left with `padding-right`

### Known AI sites with auto-detection

Examples currently covered:

- Claude
- ChatGPT
- Gemini
- AI Studio
- Copilot
- Perplexity
- Grok
- Mistral
- Poe
- HuggingChat
- DeepSeek
- You.com
- Phind

### Manual fallback

On any page:

- select text
- press `Ctrl+Shift+J`

or:

- click the floating `JUROR` pill
- use `SELECTION`

### Extension pieces

- `manifest.json`
- `background.js`
- `content/content.js`
- `popup/popup.html`
- `popup/popup.js`

`content/sidebar.css` is intentionally empty now because the sidebar styles live inside the Shadow DOM content script.

## 15. MCP Integration

The MCP router is in [server/mcp_server.py](server/mcp_server.py).

### Supported methods

- `initialize`
- `notifications/initialized`
- `tools/list`
- `tools/call`

### Exposed tools

- `verify_output`
- `get_verdict_history`
- `get_stats`

### Example setup

```bash
claude mcp add juror http://localhost:8000/mcp
```

The MCP output is formatted as readable text so it is easy to inspect inside tool-enabled clients.

## 16. Installers

The repo now includes cross-platform installers at the repo root:

- `install.sh`
- `install.ps1`

### What they do

- clone or update the repo in `~/.juror-app`
- install Python dependencies
- ask for and save a Gemini key in `~/.juror/.env`
- create the `juror` command
- install the bundled VS Code `.vsix` if possible

### What they do not do

They do not install the Chrome extension automatically. Judges still need to load `chrome-extension/` manually from `chrome://extensions`.

## 17. Demo Scenarios

Demo scenarios live in `tests/demo_scenarios/` and now include runnable HTTP clients.

Expected outputs:

| File | Expected |
|---|---|
| `civil_engineering.py` | `BLOCKED` |
| `financial_modeling.py` | `FLAGGED` |
| `software_dev.py` | `BLOCKED` |
| `healthcare.py` | `BLOCKED` |

## 18. Known Limitations

These are the real limitations of the current implementation:

1. the live jury is prompt-batched, not truly five independent model processes
2. legacy agent files are still in the repo, which can confuse new contributors
3. Agent 6 correction output is not re-verified by a second jury pass
4. the Chrome selectors for auto-monitoring will still need maintenance as AI sites change
5. the floating Chrome UI is local-browser tested by code and syntax, but still benefits from manual real-site smoke tests
6. the dashboard HTML still contains some text-encoding cleanup opportunities from earlier edits

## 19. Recommended Next Cleanup

If you want to harden the project further, the best follow-up tasks are:

1. clean encoding artifacts in UI copy
2. move legacy agent files into a clearly labeled `legacy/` folder
3. re-verify correction output after Agent 6
4. add a `.vscodeignore` and `LICENSE`
5. add lightweight browser smoke tests against localhost

## 20. File Structure

```text
server/                      FastAPI backend, MCP, config, models, storage
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
