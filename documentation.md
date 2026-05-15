# AI Hallucination Juror — Complete Technical Documentation

> **Hackathon:** PS1 — AI Automation + DevTools  
> **Theme:** Multi-agent verification system for AI-generated technical content  
> **Stack:** Python + FastAPI + Grok API + Textual TUI + VS Code Extension + Chrome Extension  
> **Version:** 1.0.0

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Problem Statement](#2-problem-statement)
3. [System Architecture](#3-system-architecture)
4. [Backend — MCP Server](#4-backend--mcp-server)
5. [The Six Agents](#5-the-six-agents)
6. [Agent Orchestration Logic](#6-agent-orchestration-logic)
7. [MCP Protocol Deep Dive](#7-mcp-protocol-deep-dive)
8. [Database Layer](#8-database-layer)
9. [API Reference](#9-api-reference)
10. [Terminal UI & CLI](#10-terminal-ui--cli)
11. [VS Code Extension](#11-vs-code-extension)
12. [Chrome Extension](#12-chrome-extension)
13. [Persistence & Auto-Start](#13-persistence--auto-start)
14. [Domain Detection](#14-domain-detection)
15. [Demo Scenarios](#15-demo-scenarios)
16. [Configuration](#16-configuration)
17. [File Structure](#17-file-structure)
18. [Setup & Installation](#18-setup--installation)
19. [How AI Agents Connect](#19-how-ai-agents-connect)
20. [Voting Logic & Verdicts](#20-voting-logic--verdicts)
21. [Error Handling](#21-error-handling)
22. [Security Notes](#22-security-notes)
23. [Known Limitations](#23-known-limitations)
24. [Presentation Guide](#24-presentation-guide)

---

## 1. Project Overview

The **AI Hallucination Juror** is a multi-surface, multi-agent verification system that intercepts outputs from any AI coding agent before they reach the developer. It acts as an autonomous jury — running six specialized AI sub-agents in parallel — and returns one of three verdicts:

| Verdict | Meaning | Action |
|---|---|---|
| ✅ APPROVED | 0–1 agents failed | Output shown normally |
| ⚠️ FLAGGED | Exactly 2 agents failed | Output shown with inline warnings |
| 🚫 BLOCKED | 3+ agents failed | Output blocked, corrected version generated |

The system works across three surfaces simultaneously:

- **Terminal** — wraps any CLI AI agent (`juror run claude "..."`)
- **VS Code** — sidebar panel with file watcher and right-click verification
- **Chrome** — injected sidebar on Claude.ai, ChatGPT, Gemini, Copilot

All three surfaces call the same backend: a FastAPI + MCP server running on `localhost:8000`.

---

## 2. Problem Statement

### What Is Happening Right Now

- **84%** of developers use AI coding tools. Only **29%** trust the output (down from 40% in 2024).
- **40–62%** of AI-generated code contains security vulnerabilities at **2.74×** the rate of human-written code.
- **35 new CVEs** in March 2026 alone were directly caused by AI-generated code (Georgia Tech Vibe Security Radar).
- Real incidents in 2025–2026:
  - Replit AI deleted an entire production database
  - Cursor AI hallucinated a company policy, causing mass subscription cancellations
  - Google Antigravity deleted a user's entire D: drive
  - Claude Code leaked 512,000 lines of source code via npm packaging error

### The Gap

Every existing tool — Snyk, Semgrep, Socket, CodeQL — works **after** code is written or in CI/CD. Nothing intercepts AI output **at the moment it is generated**, before the developer accepts it. That is the gap this system fills.

### The PS1 Requirements Met

| PS Requirement | Implementation |
|---|---|
| Technical content generation | Claude Code / Gemini CLI / Codex (primary agent) |
| Fact verification | Agent 1 — autonomous |
| Mathematical validation | Agent 2 — autonomous |
| Standards/codebook verification | Agent 3 — domain-aware |
| Reasoning consistency analysis | Agent 4 — autonomous |
| Automatic correction + retry | Agent 6 — triggered on BLOCK |
| Cross-agent reasoning | Agent 5 reads results of Agents 1–4 |
| Source-grounded decision making | All agents reference domain standards |
| Reliability scoring | Confidence % per agent + overall score |
| Automated escalation | BLOCK triggers Agent 6 without human input |

---

## 3. System Architecture

### High-Level Flow

```
Developer uses any AI tool (Claude Code / ChatGPT / Gemini / Copilot)
                          ↓
            AI agent generates technical output
                          ↓
    ┌─────────────────────────────────────────┐
    │         SURFACE INTERCEPTION            │
    │                                         │
    │  Terminal: Shell wrapper captures stdout │
    │  VS Code:  File watcher detects change  │
    │  Chrome:   DOM content script reads DOM │
    └────────────────┬────────────────────────┘
                     ↓
         HTTP POST → localhost:8000/verify
                     ↓
    ┌─────────────────────────────────────────┐
    │         JUROR MCP SERVER                │
    │         FastAPI + MCP Protocol          │
    │                                         │
    │  1. Domain auto-detection               │
    │  2. asyncio.gather() → 5 agents         │
    │  3. Agent 5 reads Agents 1–4 results    │
    │  4. Majority vote → verdict             │
    │  5. Agent 6 if BLOCKED                  │
    │  6. SQLite verdict saved                │
    └────────────────┬────────────────────────┘
                     ↓
           VerdictResponse (JSON)
                     ↓
    ┌─────────────────────────────────────────┐
    │         DISPLAY LAYER                   │
    │                                         │
    │  Terminal: Rich split panel             │
    │  VS Code:  WebView sidebar + squiggles  │
    │  Chrome:   Injected sidebar             │
    └─────────────────────────────────────────┘
```

### Component Map

```
juror/
├── server/              # Python FastAPI + MCP backend
│   ├── main.py          # App entry point, routes
│   ├── mcp_server.py    # MCP JSON-RPC handler
│   ├── grok_client.py   # Shared Grok API client
│   ├── domain_detector  # Auto-detect domain from content
│   ├── database.py      # SQLite verdict history
│   ├── models.py        # Pydantic data models
│   ├── config.py        # Settings
│   └── agents/          # 6 verification agents
├── terminal/            # Textual TUI + Click CLI
├── vscode-extension/    # TypeScript VS Code extension
├── chrome-extension/    # JavaScript Manifest V3
└── persistence/         # OS service configs
```

---

## 4. Backend — MCP Server

### Technology Choices

| Component | Technology | Reason |
|---|---|---|
| HTTP Framework | FastAPI | Async-native, automatic OpenAPI docs |
| AI Client | Grok API via openai SDK | OpenAI-compatible, fast inference |
| Concurrency | Python asyncio | Parallel agent execution |
| Database | SQLite + aiosqlite | Zero setup, local, persistent |
| Validation | Pydantic v2 | Type-safe request/response models |
| Server | Uvicorn | ASGI, production-grade |

### Data Models

#### `VerificationRequest`
```python
class VerificationRequest(BaseModel):
    content: str          # The AI-generated text to verify (max 4000 chars)
    domain: Optional[Domain] = None   # Auto-detected if not provided
    context: Optional[str] = None     # Original prompt or file path
    source: Optional[str] = None      # "chrome" | "vscode" | "terminal" | "mcp"
```

#### `VerdictResponse`
```python
class VerdictResponse(BaseModel):
    request_id: str               # Short UUID (8 chars)
    timestamp: datetime
    domain: Domain                # Detected or provided domain
    agent_results: List[AgentResult]   # One per agent (5 primary + 1 correction)
    final_verdict: FinalVerdict   # APPROVED | FLAGGED | BLOCKED
    overall_confidence: float     # Average confidence across agents
    fail_count: int               # How many of 5 agents failed
    issues_summary: List[str]     # All issues from all agents
    correction: Optional[str]     # Only present if BLOCKED
    execution_time_ms: int        # Total wall-clock time
```

#### `AgentResult`
```python
class AgentResult(BaseModel):
    agent_id: int           # 1–6
    agent_name: str         # Human-readable name
    verdict: AgentVerdict   # PASS | FAIL | UNCERTAIN
    confidence: float       # 0.0–1.0 (how certain the agent is)
    issues: List[str]       # Specific problems found
    reasoning: str          # One-sentence explanation
    execution_time_ms: int  # Per-agent timing
```

### FastAPI Routes

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Server status, model info, uptime |
| POST | `/verify` | Main verification endpoint |
| GET | `/history` | Past verdicts (paginated) |
| GET | `/stats` | Aggregated statistics |
| POST | `/mcp/` | MCP JSON-RPC handler |

### Server Startup Sequence

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()          # Create ~/.juror/verdicts.db if missing
    print("Server started")  # Log to ~/.juror/juror.log
    yield
    print("Server stopped")
```

On startup the server:
1. Creates `~/.juror/` directory if missing
2. Initialises SQLite database with verdicts table
3. Binds to `0.0.0.0:8000`
4. Enables CORS for all origins (required for Chrome extension)

---

## 5. The Six Agents

All agents call the Grok API via the shared `grok_client.py`. Each has a specialized system prompt and returns a strict JSON structure.

### Agent 1 — Fact Verifier

**Purpose:** Detect fabricated technical facts — non-existent packages, fake APIs, made-up version numbers, hallucinated standards.

**Checks:**
- Does this npm/pip/gem package actually exist?
- Is this API endpoint/function real?
- Are these version numbers accurate?
- Are these standard numbers (IS 875, Eurocode 2) real documents?

**Most common findings:**
- `react-query-optimizer` — does not exist on npm
- `axios-cache-interceptor` — exists but API shown is wrong
- `IS 1893:2019` — wrong year, document is IS 1893:2016

**Output JSON:**
```json
{
  "verdict": "FAIL",
  "confidence": 0.95,
  "issues": ["Package 'react-query-optimizer' does not exist on npm registry"],
  "reasoning": "The AI hallucinated a package name by combining two real packages"
}
```

---

### Agent 2 — Math Validator

**Purpose:** Verify numerical correctness — formulas, calculations, unit conversions, statistical values.

**Checks by domain:**
- Civil/Mechanical: load factors, safety factors, seismic coefficients
- Financial: compound interest, NPV, IRR, Black-Scholes
- Healthcare: dosage calculations (mg/kg), unit conversions
- Software: Big-O claims, benchmark numbers

**Most common findings:**
- Compound interest formula missing compounding frequency `n`
- Safety factor 1.2 used where IS 875 requires 1.5 for seismic zones
- Pediatric dose calculation using adult weight (70kg) instead of actual weight

**Output JSON:**
```json
{
  "verdict": "FAIL",
  "confidence": 0.98,
  "issues": ["Formula A=P(1+r)^t missing compounding frequency. Correct: A=P(1+r/n)^(nt)"],
  "reasoning": "Monthly compounding (n=12) was specified but formula uses annual compounding"
}
```

---

### Agent 3 — Standards Checker

**Purpose:** Verify compliance with domain-specific standards, codes, and regulations.

**Standards by domain:**

| Domain | Standards Applied |
|---|---|
| Civil Engineering | IS 456, IS 875, IS 1893, Eurocode 2/3/8, AISC, ACI 318 |
| Cloud/Infrastructure | AWS CIS Benchmark, OWASP Top 10, NIST SP 800-53, ISO 27001 |
| Healthcare | WHO Essential Medicines, FDA Guidelines, HIPAA |
| Financial | IFRS, GAAP, Basel III, SEC Regulations |
| Software | OWASP Top 10, GDPR, PCI-DSS |
| Mechanical | ASME, ISO 9001, DIN |
| Construction | IBC, NFPA 101 |

**Most common findings:**
- SSH port 22 open to 0.0.0.0/0 violates AWS CIS Benchmark Rule 4.1
- Safety factor below IS 1893 minimum for seismic zone classification
- Hardcoded API key in config violates OWASP A02:2021 Cryptographic Failures

---

### Agent 4 — Logic Auditor

**Purpose:** Verify that the reasoning within the content is internally consistent and logically sound.

**Checks:**
- Do conclusions follow from premises?
- Are there internal contradictions?
- Are conditional statements correct?
- Are edge cases handled?
- Are there hidden assumptions that could fail?
- Does the solution actually solve the stated problem?

**Most common findings:**
- Conclusion "design is safe" not supported by numbers in the calculation
- Code handles the happy path but not null/empty input
- Authentication check added but authorization (role check) missing

---

### Agent 5 — Domain Expert

**Purpose:** Synthesize the findings of Agents 1–4 and provide the final expert judgment: "Would a senior professional in this domain approve this for production?"

**Unique behaviour:** Agent 5 is the only agent that receives the results of Agents 1–4 as input. It reads their verdicts and reasoning before making its own assessment. This gives it context-aware synthesis capability.

**Input it receives:**
```
Agent 1 (Fact Verifier): PASS — No fabricated references found
Agent 2 (Math Validator): FAIL — Safety factor 1.2 should be 1.5 per IS 875
Agent 3 (Standards Checker): FAIL — Violates IS 1893:2016 Zone IV requirements
Agent 4 (Logic Auditor): PASS — Reasoning chain is internally consistent
```

**Output JSON:**
```json
{
  "verdict": "FAIL",
  "confidence": 0.97,
  "issues": ["A licensed structural engineer would not sign off on this calculation for Zone IV"],
  "reasoning": "The combined math and standards failures make this unsafe for seismic design"
}
```

---

### Agent 6 — Correction Agent

**Purpose:** Generate a corrected version of the BLOCKED content. Only triggered when final verdict is BLOCKED (3+ agents failed).

**Behaviour:**
1. Receives original content + all issues from all failing agents
2. Generates corrected version that addresses every identified issue
3. Returns corrected content as a string (not JSON)
4. The correction is included in `VerdictResponse.correction`

**Note on re-verification:** In the current implementation, Agent 6's output is not re-verified by Agents 1–4. This is a known limitation. For the hackathon scope, single-pass correction is sufficient. Full re-verification loop is planned for v1.1.

---

## 6. Agent Orchestration Logic

### Execution Order

```python
# Step 1: Domain detection (single fast call)
domain = await detect_domain(content)

# Step 2: Agents 1–4 fire simultaneously
agent_1, agent_2, agent_3, agent_4 = await asyncio.gather(
    run_fact_verifier(content, domain),
    run_math_validator(content, domain),
    run_standards_checker(content, domain),
    run_logic_auditor(content, domain),
)

# Step 3: Agent 5 runs with context from 1–4
agent_5 = await run_domain_expert(content, domain, [agent_1, agent_2, agent_3, agent_4])

# Step 4: Count failures across all 5 agents
fail_count = sum(1 for r in [agent_1...agent_5] if r.verdict == "FAIL")

# Step 5: Determine verdict
if fail_count <= 1:   final = APPROVED
elif fail_count == 2: final = FLAGGED
else:                 final = BLOCKED

# Step 6: Trigger Agent 6 only if BLOCKED
if final == BLOCKED:
    correction = await run_correction_agent(content, domain, all_issues)
```

### Timing Breakdown

| Phase | Time | Notes |
|---|---|---|
| Domain detection | ~300ms | Single Grok call |
| Agents 1–4 (parallel) | ~2000ms | asyncio.gather() |
| Agent 5 | ~600ms | Sequential, needs 1–4 results |
| Agent 6 (if BLOCKED) | ~800ms | Correction generation |
| **Total (APPROVED)** | **~2.9s** | |
| **Total (BLOCKED)** | **~3.7s** | Includes correction |

### UNCERTAIN Handling

If an agent throws an exception (API timeout, JSON parse failure, network error), it returns `UNCERTAIN` with `confidence: 0.5`. `UNCERTAIN` verdicts are **not counted as failures** in the voting. This prevents false positives from agent errors causing unnecessary blocks.

---

## 7. MCP Protocol Deep Dive

### What Is MCP?

Model Context Protocol is Anthropic's open standard for connecting AI agents to external tools. It uses JSON-RPC 2.0 over HTTP/SSE or stdio. Claude Code, Gemini CLI, Codex CLI, and Copilot CLI all support it natively.

### How the Juror Uses MCP

The Juror exposes itself as an MCP server. AI agents (like Claude Code) can discover and call its tools automatically.

**Registration (one-time):**
```bash
claude mcp add juror http://localhost:8000/mcp
```

**What happens at Claude Code startup:**
1. Claude Code reads `~/.claude/claude_desktop_config.json`
2. Finds `juror` MCP server registered at `http://localhost:8000/mcp`
3. Sends `initialize` handshake
4. Sends `tools/list` to discover available tools
5. Tools are now available for Claude Code to call during any session

### MCP Message Sequence

#### Handshake
```json
// Client → Server
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{
  "protocolVersion":"2024-11-05",
  "capabilities":{"tools":{}}
}}

// Server → Client
{"jsonrpc":"2.0","id":1,"result":{
  "protocolVersion":"2024-11-05",
  "capabilities":{"tools":{}},
  "serverInfo":{"name":"ai-hallucination-juror","version":"1.0.0"}
}}
```

#### Tool Discovery
```json
// Client → Server
{"jsonrpc":"2.0","id":2,"method":"tools/list"}

// Server → Client
{"jsonrpc":"2.0","id":2,"result":{"tools":[
  {
    "name":"verify_output",
    "description":"Verify AI-generated technical content using a 6-agent jury...",
    "inputSchema":{
      "type":"object",
      "properties":{
        "content":{"type":"string"},
        "domain":{"type":"string","enum":["civil_engineering","software_development",...]},
        "context":{"type":"string"}
      },
      "required":["content"]
    }
  }
]}}
```

#### Tool Call
```json
// Claude Code → Juror
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{
  "name":"verify_output",
  "arguments":{
    "content":"F = 1.2 × DL + 1.6 × LL for Zone 4 seismic",
    "domain":"civil_engineering"
  }
}}

// Juror → Claude Code
{"jsonrpc":"2.0","id":3,"result":{
  "content":[{"type":"text","text":"JUROR VERDICT: BLOCKED\nConfidence: 94%\n..."}],
  "isError":true
}}
```

### Exposed MCP Tools

| Tool | Description | Parameters |
|---|---|---|
| `verify_output` | Run 6-agent jury on content | `content` (required), `domain`, `context` |
| `get_verdict_history` | Get past verification history | `limit` (default: 10) |
| `get_stats` | Get block/flag/approve rates | none |

### CLAUDE.md Integration

When added to a project's `CLAUDE.md`, Claude Code will automatically call the Juror before presenting technical outputs:

```markdown
## Output Verification Policy

Before presenting any technical solution, calculation, infrastructure config,
or code that will be used in production, call verify_output() from the Juror MCP tool.

If verdict is BLOCKED: present the corrected output from the Juror instead.
If verdict is FLAGGED: present original output with the flagged warnings noted clearly.
If verdict is APPROVED: present normally.
```

---

## 8. Database Layer

### Schema

```sql
CREATE TABLE verdicts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id      TEXT NOT NULL,           -- Short UUID
    timestamp       TEXT NOT NULL,           -- ISO 8601
    domain          TEXT NOT NULL,           -- Domain enum value
    final_verdict   TEXT NOT NULL,           -- APPROVED | FLAGGED | BLOCKED
    fail_count      INTEGER NOT NULL,        -- 0–5
    source          TEXT DEFAULT 'unknown',  -- chrome | vscode | terminal | mcp
    content_preview TEXT,                    -- First 100 chars of input
    full_response   TEXT,                    -- Full JSON VerdictResponse
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### Location

```
~/.juror/verdicts.db
```

The `~/.juror/` directory is created automatically on first server start. SQLite requires no external database server — it runs entirely as a local file.

### Key Queries

```python
# Save a verdict
await db.execute("""
    INSERT INTO verdicts 
    (request_id, timestamp, domain, final_verdict, fail_count, source, content_preview, full_response)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", (...))

# Get history (most recent first)
await db.execute("SELECT * FROM verdicts ORDER BY id DESC LIMIT ?", (limit,))

# Stats
SELECT final_verdict, COUNT(*) FROM verdicts GROUP BY final_verdict
```

---

## 9. API Reference

### `GET /health`

Returns server status and configuration.

**Response:**
```json
{
  "status": "running",
  "version": "1.0.0",
  "model": "grok-3-mini",
  "grok_configured": true,
  "server": "http://localhost:8000"
}
```

---

### `POST /verify`

Main verification endpoint. Runs full 6-agent jury.

**Request body:**
```json
{
  "content": "npm install react-query-optimizer",
  "domain": "software_development",
  "context": "package.json dependency",
  "source": "chrome"
}
```

**Response:**
```json
{
  "request_id": "a3f9b2c1",
  "timestamp": "2026-05-15T14:23:11.432Z",
  "domain": "software_development",
  "agent_results": [
    {
      "agent_id": 1,
      "agent_name": "Fact Verifier",
      "verdict": "FAIL",
      "confidence": 0.97,
      "issues": ["Package 'react-query-optimizer' does not exist on npm"],
      "reasoning": "Hallucinated package name — likely a conflation of react-query and query-optimizer",
      "execution_time_ms": 643
    },
    ...
  ],
  "final_verdict": "BLOCKED",
  "overall_confidence": 0.91,
  "fail_count": 3,
  "issues_summary": ["Package does not exist", "API signature is wrong", "useOptimizedQuery hook not in any real library"],
  "correction": "npm install @tanstack/react-query\n\nimport { useQuery } from '@tanstack/react-query';\n...",
  "execution_time_ms": 3247
}
```

**Error responses:**

| Status | Reason |
|---|---|
| 400 | Content too short (< 10 chars) |
| 500 | Grok API key invalid or unreachable |

---

### `GET /history?limit=20`

Returns past verdicts, most recent first.

**Response:**
```json
{
  "history": [
    {
      "id": 42,
      "request_id": "a3f9b2c1",
      "timestamp": "2026-05-15T14:23:11",
      "domain": "software_development",
      "final_verdict": "BLOCKED",
      "fail_count": 3,
      "source": "chrome",
      "content_preview": "npm install react-query-optimizer"
    }
  ],
  "count": 1
}
```

---

### `GET /stats`

Aggregated verdict statistics.

**Response:**
```json
{
  "total": 47,
  "approved": 28,
  "flagged": 11,
  "blocked": 8,
  "block_rate": "17.0%"
}
```

---

## 10. Terminal UI & CLI

### CLI Commands

All commands are accessed via the `juror` entrypoint (installed as a Python script via `pyproject.toml`).

#### `juror start`
Starts the MCP server and launches the Textual TUI in split-panel mode.

```bash
juror start           # Server + TUI
juror start --no-tui  # Server only (for system service use)
```

#### `juror run <command>`
Wraps any CLI AI agent. Captures stdout, sends to Juror, displays verdict.

```bash
juror run claude "write a structural load calculation for Zone 4"
juror run gemini "explain compound interest formula"
juror run codex "create a REST API with authentication"
```

**How it works:**
1. `subprocess.run(cmd, capture_output=True)` captures full output
2. Output echoed to terminal first (developer sees AI response)
3. Output sent to `/verify` endpoint
4. Verdict displayed below with per-agent breakdown
5. If BLOCKED: correction printed

#### `juror verify <file>`
Verify the contents of any file.

```bash
juror verify ./calculations.py
juror verify ./infrastructure/main.tf
```

#### `juror status`
Check if server is running.

```bash
juror status
# ✅ Juror server is RUNNING
#    Version: 1.0.0
#    Model: grok-3-mini
#    URL: http://localhost:8000
```

#### `juror history`
Show recent verdict history in terminal.

#### `juror install-service`
Install Juror as a system service (auto-starts on login). See Section 13.

### Textual TUI Layout

```
┌─────────────────────────────────────────────────────────────┐
│  AI HALLUCINATION JUROR                      14:23:11       │
├──────────────────────────────┬──────────────────────────────┤
│  ◈ AI OUTPUT STREAM          │  ⬡ JURY PANEL                │
│                              │                              │
│  Content being verified:     │  ⬡ JURY CONVENING...        │
│                              │                              │
│  F = 1.2 × DL + 1.6 × LL   │  ✓ A1 Fact Verifier: PASS   │
│  for Zone 4 seismic design   │  ✗ A2 Math Validator: FAIL  │
│                              │    • Safety factor 1.2≠1.5   │
│  [OUTPUT BLOCKED]            │  ✗ A3 Standards: FAIL       │
│                              │    • Violates IS 1893 Zone 4 │
│  ✦ CORRECTED (Agent 6):      │  ✓ A4 Logic Auditor: PASS   │
│  F = 1.5 × DL + 1.5 × LL   │  ✗ A5 Domain Expert: FAIL   │
│  per IS 875 Zone IV          │                              │
│                              │  VERDICT: BLOCKED 3/5        │
├──────────────────────────────┴──────────────────────────────┤
│  🚫 BLOCKED | Fail: 3/5 | Confidence: 94% | 3.2s           │
├─────────────────────────────────────────────────────────────┤
│  HISTORY                                                     │
│  14:23  BLOCKED  civil_engineering  3/5  terminal           │
│  14:18  APPROVED software_dev       0/5  chrome             │
│  14:10  FLAGGED  financial          2/5  vscode             │
└─────────────────────────────────────────────────────────────┘
```

### Textual Widget Architecture

| Widget | File | Purpose |
|---|---|---|
| `JurorApp` | `terminal/app.py` | Root Textual application |
| `RichLog` (left) | Built-in | Streams AI output |
| `RichLog` (right) | Built-in | Shows agent status cards |
| `Static` (bottom bar) | Built-in | Final verdict banner |
| `DataTable` | Built-in | Verdict history table |

The TUI calls `/verify` via `httpx.AsyncClient` in a `@work` decorated method, allowing the UI to remain responsive during the API call.

---

## 11. VS Code Extension

### Extension Architecture

```
vscode-extension/
├── src/
│   ├── extension.ts          # Entry point, command registration
│   ├── jurorClient.ts        # HTTP client to localhost:8000
│   ├── sidebarProvider.ts    # WebView sidebar panel
│   ├── fileWatcher.ts        # Watch AI-modified files
│   ├── decorationProvider.ts # Inline red squiggles
│   └── statusBar.ts          # Status bar item
└── media/
    └── sidebar.html/css/js   # WebView content
```

### Activation

The extension activates `onStartupFinished` — immediately when VS Code loads, without requiring any specific file to be opened. This ensures the file watcher is always running.

### How File Watching Works

```typescript
// fileWatcher.ts
const watcher = vscode.workspace.createFileSystemWatcher("**/*");

watcher.onDidChange(async (uri) => {
    // Check if this file was recently modified by an AI agent
    // (heuristic: modification within last 5 seconds, external process)
    const stat = await vscode.workspace.fs.stat(uri);
    const recentlyModified = Date.now() - stat.mtime < 5000;
    
    if (recentlyModified && isCodeFile(uri)) {
        const content = await readFile(uri);
        const verdict = await client.verify(content, 'vscode');
        sidebarProvider.showVerdict(verdict);
        decorationProvider.applyDecorations(editor, verdict);
    }
});
```

### Inline Decorations

When a FLAGGED or BLOCKED verdict is returned, the extension applies VS Code text decorations (coloured underlines and margin icons) to the affected lines:

```typescript
// decorationProvider.ts
const blockedDecoration = vscode.window.createTextEditorDecorationType({
    borderWidth: '1px',
    borderStyle: 'solid',
    borderColor: '#f87171',
    overviewRulerColor: '#f87171',
    overviewRulerLane: vscode.OverviewRulerLane.Right,
    gutterIconPath: context.asAbsolutePath('media/blocked.svg'),
});
```

### Commands Registered

| Command | Shortcut | Description |
|---|---|---|
| `juror.verifySelection` | Right-click menu | Verify highlighted text |
| `juror.verifyFile` | Command palette | Verify entire current file |
| `juror.openPanel` | Status bar click | Open jury sidebar |

### WebView Sidebar

The sidebar is implemented as a VS Code WebView — essentially a sandboxed iframe running HTML/CSS/JS. It communicates with the extension host via `vscode.postMessage()`:

```
Extension Host (TypeScript)          WebView (HTML/JS)
        |                                    |
        |  postMessage({type:'verdict',...}) →|
        |                                    | → Renders agent cards
        |                                    |
        |← postMessage({command:'verify'})   |
        | → calls client.verify()            |
        | → gets verdict                     |
        |  postMessage({type:'verdict',...}) →|
```

### VS Code Settings

```json
{
  "juror.serverUrl": "http://localhost:8000",
  "juror.autoVerify": true
}
```

---

## 12. Chrome Extension

### Manifest V3 Configuration

```json
{
  "manifest_version": 3,
  "permissions": ["activeTab", "storage", "scripting"],
  "host_permissions": [
    "https://claude.ai/*",
    "https://chat.openai.com/*",
    "https://chatgpt.com/*",
    "https://gemini.google.com/*",
    "https://copilot.microsoft.com/*",
    "http://localhost:8000/*"
  ]
}
```

The `localhost:8000` host permission is critical — without it, the content script cannot call the Juror server from the browser context.

### Site-Specific DOM Selectors

Different AI platforms structure their DOM differently. The extension maintains a config map:

| Platform | Response Selector | Stream-End Signal |
|---|---|---|
| Claude.ai | `[data-is-streaming="false"] .font-claude-message` | `[data-is-streaming="false"]` |
| ChatGPT | `[data-message-author-role="assistant"] .markdown` | `button[aria-label="Copy"]` |
| Gemini | `.response-content` | `.copy-button` |
| Copilot | `.ac-textBlock` | `.copy-btn` |

### Response Detection Logic

```javascript
const observer = new MutationObserver(() => {
    const responses = document.querySelectorAll(config.responseSelector);
    const latestResponse = responses[responses.length - 1];
    const content = latestResponse?.textContent?.trim();
    
    // Only verify if:
    // 1. Content is new (not same as last verified)
    // 2. Content is long enough (> 50 chars)
    // 3. Stream is complete (copy button visible)
    if (content && content !== lastVerifiedContent && content.length > 50) {
        const streamComplete = document.querySelectorAll(config.streamEndSignal).length > 0;
        if (streamComplete) {
            lastVerifiedContent = content;
            verifyContent(content);
        }
    }
});

observer.observe(document.body, { childList: true, subtree: true, characterData: true });
```

### Keyboard Shortcut

**Ctrl+Shift+J** — Manually trigger verification of the latest AI response on the current page. Useful when the auto-detection misses a response.

### Sidebar Injection

The sidebar is injected as a `<div id="juror-sidebar">` appended to `document.body`. It uses `position: fixed; right: 0; width: 320px; height: 100vh` to overlay on the right side of any AI interface without disrupting the page layout.

### CORS Requirement

The FastAPI server is configured with `allow_origins=["*"]` specifically because the Chrome extension calls `localhost:8000` from a web page context (e.g., `https://claude.ai`). Without this, the browser would block the request as a CORS violation.

---

## 13. Persistence & Auto-Start

### The Problem

If you run `juror start` manually, the server dies when the laptop turns off, sleeps, or reboots. Judges cannot install and test the extension if the server isn't running.

### The Solution

Register the Juror server as an OS-level service that starts automatically on every login, restarts if it crashes, and runs silently in the background.

### macOS — launchd LaunchAgent

**File location:** `~/Library/LaunchAgents/com.juror.mcp.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "...">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.juror.mcp</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/juror</string>
        <string>start</string>
        <string>--no-tui</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

**Install:** `launchctl load ~/Library/LaunchAgents/com.juror.mcp.plist`

### Linux — systemd User Service

**File location:** `~/.config/systemd/user/juror.service`

```ini
[Unit]
Description=AI Hallucination Juror MCP Server
After=network.target

[Service]
Type=simple
ExecStart=/path/to/juror start --no-tui
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
```

**Install:**
```bash
systemctl --user daemon-reload
systemctl --user enable juror
systemctl --user start juror
```

### Windows — Task Scheduler

```powershell
$action = New-ScheduledTaskAction -Execute "juror.exe" -Argument "start --no-tui"
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "JurorMCPServer" -Action $action -Trigger $trigger
```

### One-Command Install

```bash
juror install-service   # Detects OS, installs appropriate service, starts it
```

After this command, the server starts automatically on every login. No manual action ever needed again.

---

## 14. Domain Detection

Domain detection is a pre-call made before the 5 verification agents fire. It identifies which domain the content belongs to so agents can apply the correct standards.

### Detection Prompt

```
Analyze this technical content and return ONLY one of these exact strings:
civil_engineering, mechanical_engineering, software_development,
financial_modeling, healthcare, infrastructure, construction, general

Content: {content}

Return only the domain string.
```

### Detection Heuristics (Fallback)

If the Grok API call fails or returns an unrecognised string, the system falls back to keyword matching:

| Keywords | Domain |
|---|---|
| `kN`, `MPa`, `seismic`, `load`, `beam`, `column` | civil_engineering |
| `npm`, `pip`, `import`, `function`, `async`, `API` | software_development |
| `NPV`, `IRR`, `compound interest`, `portfolio` | financial_modeling |
| `dosage`, `mg/kg`, `patient`, `clinical` | healthcare |
| `Terraform`, `AWS`, `kubernetes`, `docker` | infrastructure |

### Supported Domains

```python
class Domain(str, Enum):
    CIVIL_ENGINEERING = "civil_engineering"
    MECHANICAL_ENGINEERING = "mechanical_engineering"
    SOFTWARE_DEVELOPMENT = "software_development"
    FINANCIAL_MODELING = "financial_modeling"
    HEALTHCARE = "healthcare"
    INFRASTRUCTURE = "infrastructure"
    CONSTRUCTION = "construction"
    GENERAL = "general"
```

---

## 15. Demo Scenarios

Four pre-built hallucinations for the hackathon demo, each designed to trigger specific agents.

### Scenario 1 — Civil Engineering (BLOCKED)

**Planted hallucination:** Wrong load factor (1.2 instead of 1.5) for IS 875 seismic Zone IV.

**Agents that fire:** Agent 2 (wrong math), Agent 3 (violates IS 875), Agent 5 (expert: unsafe)

**Expected verdict:** BLOCKED (3/5 fail)

**Correction generated:** Correct IS 875 load combination with 1.5 × DL + 1.5 × LL

---

### Scenario 2 — Financial Modeling (FLAGGED)

**Planted hallucination:** Compound interest formula missing compounding frequency `n`.

**Agents that fire:** Agent 2 (formula incorrect), Agent 4 (logic gap: n=12 stated but not used)

**Expected verdict:** FLAGGED (2/5 fail)

---

### Scenario 3 — Software Development (BLOCKED)

**Planted hallucination:** `react-query-optimizer` npm package (does not exist). Wrong hook API.

**Agents that fire:** Agent 1 (package doesn't exist), Agent 3 (OWASP supply chain risk), Agent 5 (expert: would not deploy)

**Expected verdict:** BLOCKED (3/5 fail)

**Correction generated:** Correct `@tanstack/react-query` with proper `useQuery` API

---

### Scenario 4 — Healthcare (BLOCKED)

**Planted hallucination:** Adult paracetamol dose (1000mg) given for a 20kg child. Correct pediatric dose is 15mg/kg = 300mg.

**Agents that fire:** Agent 2 (wrong calculation: 200mg/kg/day exceeds 150mg/kg toxic threshold), Agent 3 (WHO: weight-based dosing required for children), Agent 5 (expert: potentially fatal)

**Expected verdict:** BLOCKED (3/5 fail)

---

## 16. Configuration

### Environment Variables (`.env`)

```bash
GROK_API_KEY=xai-your-key-here    # Required
MODEL=grok-3-mini                  # Model to use
SERVER_PORT=8000                   # Port for FastAPI server
```

### Config Class (`server/config.py`)

```python
class Config:
    GROK_API_KEY: str       # From .env
    MODEL: str              # Default: grok-3-mini
    SERVER_HOST: str        # Default: 0.0.0.0
    SERVER_PORT: int        # Default: 8000
    DB_PATH: str            # Default: ~/.juror/verdicts.db
    APPROVED_THRESHOLD: int # Default: 1  (0-1 fails = APPROVED)
    FLAGGED_THRESHOLD: int  # Default: 2  (exactly 2 = FLAGGED)
    BLOCKED_THRESHOLD: int  # Default: 3  (3+ = BLOCKED)
    AGENT_TIMEOUT_SECONDS: int  # Default: 30
```

### VS Code Settings

```json
{
  "juror.serverUrl": "http://localhost:8000",
  "juror.autoVerify": true
}
```

---

## 17. File Structure

```
juror/
│
├── .env                         # API keys — NEVER commit
├── .env.example                 # Template (safe to commit)
├── requirements.txt             # Python dependencies
├── pyproject.toml               # Package config (juror CLI entrypoint)
├── README.md                    # Quick start guide
│
├── server/                      # Python FastAPI + MCP backend
│   ├── __init__.py
│   ├── main.py                  # FastAPI app, routes, lifespan
│   ├── mcp_server.py            # MCP JSON-RPC handler
│   ├── grok_client.py           # Shared Grok API client + JSON parser
│   ├── domain_detector.py       # Domain auto-detection
│   ├── database.py              # SQLite init, save, query
│   ├── models.py                # All Pydantic models
│   ├── config.py                # Settings from .env
│   └── agents/
│       ├── __init__.py
│       ├── orchestrator.py      # asyncio.gather() + voting logic
│       ├── fact_verifier.py     # Agent 1
│       ├── math_validator.py    # Agent 2
│       ├── standards_checker.py # Agent 3
│       ├── logic_auditor.py     # Agent 4
│       ├── domain_expert.py     # Agent 5 (reads 1–4 results)
│       └── correction_agent.py  # Agent 6 (BLOCK only)
│
├── terminal/                    # Textual TUI + Click CLI
│   ├── __init__.py
│   ├── app.py                   # Textual application
│   └── cli.py                   # Click CLI commands
│
├── vscode-extension/            # VS Code extension (TypeScript)
│   ├── package.json
│   ├── tsconfig.json
│   ├── src/
│   │   ├── extension.ts         # Entry point
│   │   ├── jurorClient.ts       # HTTP client
│   │   ├── sidebarProvider.ts   # WebView panel
│   │   ├── fileWatcher.ts       # File change watcher
│   │   └── decorationProvider.ts
│   └── out/                     # Compiled JS (gitignored)
│
├── chrome-extension/            # Chrome Extension (MV3)
│   ├── manifest.json
│   ├── background.js            # Service worker
│   ├── content/
│   │   ├── content.js           # DOM injection + monitoring
│   │   └── sidebar.css          # Injected sidebar styles
│   └── popup/
│       ├── popup.html
│       └── popup.js
│
├── persistence/                 # Auto-start service configs
│   ├── macos/com.juror.mcp.plist
│   ├── linux/juror.service
│   └── windows/install-service.ps1
│
├── scripts/
│   ├── install.sh               # One-command install (macOS/Linux)
│   └── install.ps1              # One-command install (Windows)
│
└── tests/
    ├── test_agents.py
    ├── test_mcp.py
    └── demo_scenarios/
        ├── civil_engineering.py
        ├── financial_modeling.py
        ├── software_dev.py
        └── healthcare.py
```

---

## 18. Setup & Installation

### Prerequisites

- Python 3.11+
- Node.js 18+ (for VS Code extension)
- Google Chrome (for Chrome extension)
- VS Code (for VS Code extension)
- A valid Grok API key from [console.x.ai](https://console.x.ai)

### Full Installation

```bash
# 1. Clone / enter project
cd juror

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env → add your GROK_API_KEY

# 4. Start the server
python -m server.main

# 5. Verify health
curl http://localhost:8000/health

# 6. Install as system service (auto-start on login)
juror install-service

# 7. Connect Claude Code
claude mcp add juror http://localhost:8000/mcp

# 8. Install VS Code extension
# Drag vscode-extension/ into VS Code Extensions panel
# Or: cd vscode-extension && npm install && npm run compile → F5

# 9. Install Chrome extension
# chrome://extensions → Enable Developer Mode → Load Unpacked → select chrome-extension/
```

### Quick Verification

```bash
# Test Grok connection
python -c "
import asyncio
from server.grok_client import call_grok
print(asyncio.run(call_grok('Say hello in one word')))
"

# Test verification
curl -X POST http://localhost:8000/verify \
  -H "Content-Type: application/json" \
  -d '{"content":"npm install react-query-optimizer","source":"test"}'
```

---

## 19. How AI Agents Connect

### Claude Code CLI

```bash
# Register Juror MCP server (one time)
claude mcp add juror http://localhost:8000/mcp

# Verify registration
claude mcp list

# Config stored at: ~/.claude/claude_desktop_config.json
```

### Gemini CLI

Add to `~/.gemini/settings.json`:
```json
{
  "mcpServers": {
    "juror": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### Codex CLI

Add to `~/.codex/config.json`:
```json
{
  "mcpServers": {
    "juror": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### VS Code (any AI extension)

Add to VS Code `settings.json`:
```json
{
  "mcp.servers": {
    "juror": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### Direct API (Any Tool)

Any tool can call the REST API directly:
```python
import httpx

response = httpx.post("http://localhost:8000/verify", json={
    "content": "your AI-generated content here",
    "source": "my-tool"
})
verdict = response.json()
print(verdict["final_verdict"])  # APPROVED | FLAGGED | BLOCKED
```

---

## 20. Voting Logic & Verdicts

### Vote Count → Verdict

```
Agents 1–5 each return: PASS | FAIL | UNCERTAIN

Count only FAIL votes (UNCERTAIN is neutral):

fail_count = 0 or 1  →  ✅ APPROVED  (output shown normally)
fail_count = 2       →  ⚠️ FLAGGED   (shown with warnings)
fail_count = 3, 4, 5 →  🚫 BLOCKED   (Agent 6 triggered)
```

### Why This Threshold?

- **0–1 fail:** A single agent being cautious should not block output. One false positive is acceptable noise.
- **2 fail:** Two independent agents flagging the same output is a meaningful signal. Worth warning the developer but not blocking.
- **3+ fail:** Majority of the jury failed. The output has systemic problems. Block and correct.

### Confidence Score

Each agent returns a `confidence` float (0.0–1.0) representing how certain it is of its verdict. The overall confidence in `VerdictResponse` is the simple average:

```python
overall_confidence = sum(a.confidence for a in results) / len(results)
```

A high confidence BLOCKED verdict (e.g., 0.97) means the jury is extremely certain. A lower confidence (e.g., 0.68) means agents are less certain — the developer should look carefully at the issues.

---

## 21. Error Handling

### Agent-Level Error Handling

Every agent wraps its execution in `try/except`. On any error:
- Returns `AgentVerdict.UNCERTAIN` (not counted in fail vote)
- Sets `confidence: 0.5`
- Includes error message in `issues`
- Does NOT raise the exception (orchestrator continues)

```python
except Exception as e:
    return AgentResult(
        agent_id=1,
        agent_name="Fact Verifier",
        verdict=AgentVerdict.UNCERTAIN,
        confidence=0.5,
        issues=[f"Agent error: {str(e)}"],
        reasoning="Error during verification",
        execution_time_ms=int((time.time() - start) * 1000)
    )
```

### JSON Parse Errors

Grok sometimes wraps JSON in markdown fences despite explicit instructions not to. The `parse_agent_json()` function handles this:

```python
def parse_agent_json(raw: str) -> dict:
    cleaned = raw.strip()
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()
    
    # Find JSON boundaries if Grok added surrounding text
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start != -1 and end > start:
        cleaned = cleaned[start:end]
    
    return json.loads(cleaned)  # Raises JSONDecodeError if truly malformed
```

### Server Unreachable

When any surface (Chrome, VS Code, Terminal) cannot reach the server:
- Chrome: Shows red error message in sidebar
- VS Code: Shows error in WebView + VS Code notification
- Terminal CLI: Shows coloured error with `juror start` hint

The surfaces are designed to degrade gracefully — they never crash because the server is down.

---

## 22. Security Notes

### API Key Management

- **Never** hardcode API keys in source files
- **Never** paste API keys in chat interfaces or commit them to Git
- Store only in `juror/.env` which is listed in `.gitignore`
- Rotate keys immediately if accidentally exposed

### CORS Policy

The server uses `allow_origins=["*"]`. This is intentional for local-only operation — the server is only accessible on localhost. If you ever expose this server publicly, change CORS to allow only specific origins.

### Local-Only by Default

The server binds to `0.0.0.0:8000`. While this technically means it listens on all interfaces, it's only accessible to processes on the same machine by default (no firewall exceptions made). Do not expose port 8000 to the internet.

### Content Privacy

The content you send to `/verify` is:
1. Sent to the Grok API (xAI) for agent processing
2. Stored locally in `~/.juror/verdicts.db` (first 100 chars as preview, full response as JSON)

Do not verify content containing secrets, passwords, PII, or proprietary code if your organisation has data handling restrictions.

---

## 23. Known Limitations

| Limitation | Impact | Planned Fix |
|---|---|---|
| Agent 6 correction not re-verified | Correction might still have issues | v1.1: Re-run Agents 1–4 on correction |
| Gemini SDK deprecated (`google-generativeai`) | Deprecation warnings | Migrated to Grok; no longer relevant |
| Chrome extension requires localhost server | Won't work without server running | Persistence service fixes this |
| DOM selectors hardcoded per AI site | Breaks when sites update their HTML | CSS selector config file planned |
| No rate limiting on `/verify` | Could be called rapidly | Token bucket planned for v1.1 |
| Agent prompts not domain-fine-tuned | General prompts may miss niche errors | Domain-specific prompt variants planned |
| VS Code file watcher heuristic | May trigger on non-AI file changes | Content fingerprinting planned |

---

## 24. Presentation Guide

### 10-Minute Structure

**Minutes 0–1: The Pain**
> "84% of developers use AI tools. Only 29% trust the output. Last month — three weeks ago — attackers poisoned 170 npm packages including TanStack and Mistral in a single campaign. In 2025, Replit's AI deleted a production database. Google's AI deleted a user's entire hard drive. These aren't edge cases. They happen every week. And right now, there is nothing between your AI agent and your production system."

**Minutes 1–2: The Gap**
> "Every tool in this space tells you what your AI is doing. None of them verify whether what it's doing is actually correct. We built the missing layer."

**Minutes 2–4: The Architecture**
Show the system diagram. Key points:
- One MCP server, three thin clients
- Zero change to developer workflow
- Works with every major AI CLI and web interface
- Covers six industries, not just software

**Minutes 4–9: Live Demo**

| Time | Scenario | Surface | Expected |
|---|---|---|---|
| 1 min | Civil engineering calculation | Terminal | BLOCKED |
| 1 min | Financial formula | Chrome/Claude.ai | FLAGGED |
| 1 min | Hallucinated npm package | VS Code | BLOCKED + correction |
| 2 min | Judge types own prompt | Judge's machine | Live verdict |

**Minute 9–10: The Close**
> "One MCP connection. Every AI agent. Every domain. The jury is always watching. Install it once, and it runs forever."

### Demo Setup Checklist

Before the presentation:

- [ ] Server running: `curl http://localhost:8000/health` returns `running`
- [ ] Claude Code connected: `claude mcp list` shows `juror`
- [ ] Chrome extension loaded and sidebar visible on Claude.ai
- [ ] VS Code extension compiled and sidebar panel open
- [ ] All 4 demo scenarios tested and returning correct verdicts
- [ ] Judge's machine ready: install script prepared, ready to run in 90 seconds
- [ ] `.env` has valid Grok API key — test with one-word probe

### Likely Judge Questions

**Q: Is this agentic AI or just a classifier?**
A: It's fully agentic. Claude Code is the primary agent making autonomous tool calls. The Juror orchestrates 6 sub-agents with cross-agent reasoning. Agent 5 reads the outputs of Agents 1–4. Agent 6 is triggered autonomously without human input. Every PS requirement for agentic architecture is met.

**Q: Why not just use a linter or static analyser?**
A: Linters check syntax and known patterns. They cannot detect a hallucinated package name, a wrong safety factor in a structural calculation, or a pediatric dosage error. This system uses AI to verify AI — semantic understanding, not pattern matching.

**Q: What happens when the server is down?**
A: All surfaces degrade gracefully with a clear error message. The system service (installed via `juror install-service`) ensures the server is always running after a single setup step.

**Q: Is it slow? 3 seconds seems long.**
A: The 5 primary agents run in parallel via `asyncio.gather()` — not sequentially. The bottleneck is the API call latency, not computation. For content going into production systems (structural calculations, financial models, medical dosages), 3 seconds is a worthwhile investment.

**Q: Does it work for languages other than English?**
A: Grok processes technical content in any language. Domain detection and agent prompts work on the technical content itself, not the natural language framing.

---

*Documentation version 1.0.0 — AI Hallucination Juror — Hackathon Build*