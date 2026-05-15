```mermaid
flowchart TB

classDef surface fill:#0b1220,stroke:#38bdf8,color:#e2e8f0,stroke-width:1px;
classDef backend fill:#0f172a,stroke:#22c55e,color:#e2e8f0,stroke-width:1px;
classDef agent fill:#111827,stroke:#f59e0b,color:#f8fafc,stroke-width:1px;
classDef data fill:#172554,stroke:#a78bfa,color:#e2e8f0,stroke-width:1px;
classDef external fill:#1f2937,stroke:#f472b6,color:#f8fafc,stroke-width:1px;
classDef decision fill:#3f3f46,stroke:#facc15,color:#f8fafc,stroke-width:1px;
classDef fallback fill:#3b0764,stroke:#c084fc,color:#f8fafc,stroke-width:1px;
classDef runtime fill:#052e16,stroke:#4ade80,color:#f0fdf4,stroke-width:1px;

U["Developer, Judge, or AI Agent Output"]:::surface

subgraph S0["Project Layout and Code Ownership"]
  R0["README.md<br/>project setup, quick start, MCP wiring"]:::data
  R1["server/<br/>FastAPI backend, MCP endpoint, agents, models, config, database"]:::backend
  R2["terminal/<br/>Textual dashboard and CLI wrapper"]:::surface
  R3["vscode-extension/<br/>TypeScript extension, sidebar, auto-verify, decorations"]:::surface
  R4["chrome-extension/<br/>Manifest V3, content script, sidebar, popup"]:::surface
  R5["tests/<br/>demo scenarios plus backend and MCP tests"]:::data
  R6["persistence/<br/>launchd, systemd, Task Scheduler templates"]:::runtime
  R7["scripts/<br/>install helpers and demo bootstrap"]:::runtime
end

subgraph S1["Input Surfaces and Trigger Points"]
  T1["terminal/cli.py<br/>juror start"]:::surface
  T2["terminal/cli.py<br/>juror run some_ai_command"]:::surface
  T3["terminal/cli.py<br/>juror verify file"]:::surface
  T4["terminal/app.py<br/>Textual TUI dashboard"]:::surface
  V1["VS Code command<br/>Verify Selected Text"]:::surface
  V2["VS Code command<br/>Verify Current File"]:::surface
  V3["VS Code file watcher<br/>onDidSaveTextDocument"]:::surface
  V4["VS Code sidebar webview<br/>manual verify button"]:::surface
  C1["Chrome content script<br/>MutationObserver watches AI chat DOM"]:::surface
  C2["Chrome popup<br/>toggle sidebar and check backend"]:::surface
  M1["External MCP client<br/>Claude Code, Gemini-compatible clients, Codex CLI, other MCP-aware tools"]:::surface
  A1["Direct REST caller<br/>POST verify, GET history, GET stats, GET health"]:::surface
end

subgraph S2["HTTP and MCP Server Boundary"]
  F0["server/main.py<br/>FastAPI app factory and lifespan"]:::backend
  F1["GET /health<br/>status, model, server URL, grok_configured"]:::backend
  F2["POST /verify<br/>accept VerificationRequest and return VerdictResponse"]:::backend
  F3["GET /history<br/>recent verdicts from SQLite"]:::backend
  F4["GET /stats<br/>aggregate approved, flagged, blocked counts"]:::backend
  F5["/mcp JSON-RPC router<br/>initialize, tools/list, tools/call"]:::backend
  F6["CORS middleware<br/>allows localhost extensions and browser calls"]:::backend
end

subgraph S3["Configuration, Models, and Runtime State"]
  Cfg0["server/config.py<br/>load .env and ~/.juror/.env<br/>GEMINI_API_KEY, MODEL, PORT, DB_PATH, LOG_PATH,<br/>thresholds, timeouts, request char limit"]:::data
  Cfg1["server/models.py<br/>Domain, AgentVerdict, FinalVerdict,<br/>AgentResult, VerificationRequest, VerdictResponse, HistoryEntry"]:::data
  Env0["juror/.env<br/>GEMINI_API_KEY, MODEL, SERVER_PORT"]:::data
  Env1["~/.juror/.env<br/>optional machine-level overrides"]:::data
  Db0["~/.juror/verdicts.db<br/>SQLite verdict history"]:::data
  Log0["~/.juror/juror.log and server.log<br/>runtime logs"]:::data
end

subgraph S4["Verification Orchestration Core"]
  O0["server/agents/orchestrator.py<br/>run_jury(request)"]:::backend
  O1["Create request_id and timestamp"]:::backend
  O2["Determine domain<br/>request.domain or auto-detect"]:::backend
  O3["Run Agents 1 to 4 in parallel with asyncio.gather"]:::backend
  O4["Wrap each agent in asyncio.wait_for via _with_timeout"]:::backend
  O5["Run Agent 5 after Agents 1 to 4 finish<br/>passes their reasoning into domain expert"]:::backend
  O6["Collect all AgentResult objects"]:::backend
  O7["Count FAIL verdicts only"]:::backend
  D0{"fail_count <= APPROVED_THRESHOLD"}:::decision
  D1{"fail_count == FLAGGED_THRESHOLD"}:::decision
  O8["APPROVED"]:::backend
  O9["FLAGGED"]:::backend
  O10["BLOCKED"]:::backend
  O11["Flatten and dedupe issues_summary"]:::backend
  O12["Average all agent confidences for overall_confidence"]:::backend
  O13["If BLOCKED, run Agent 6 correction agent"]:::backend
  O14["Generate correction_diff via unified diff"]:::backend
  O15["Return VerdictResponse"]:::backend
end

subgraph S5["Domain Detection"]
  DD0["server/domain_detector.py<br/>detect_domain(content)"]:::backend
  DD1["Gemini domain prompt<br/>return exact enum string only"]:::agent
  DD2["Normalize Gemini result<br/>lowercase and replace spaces with underscores"]:::backend
  DD3["Domain enum cast"]:::backend
  DD4["Keyword heuristic fallback<br/>civil, mechanical, software, financial, healthcare,<br/>infrastructure, construction, general"]:::fallback
end

subgraph S6["Shared Gemini Client and JSON Parsing"]
  G0["server/grok_client.py"]:::backend
  G1["gemini_available<br/>requires GEMINI_API_KEY"]:::backend
  G2["call_grok(prompt, max_tokens)<br/>Gemini generateContent request"]:::backend
  G3["Gemini REST client configured with<br/>https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"]:::backend
  G4["Use config.MODEL such as gemini-2.5-flash"]:::backend
  G5["Request options<br/>max_tokens, temperature 0.1"]:::backend
  G6["candidates[0].content.parts[].text"]:::agent
  G7["parse_agent_json(raw)<br/>strip markdown fences, isolate first JSON object, json.loads"]:::backend
  G8["Failure modes<br/>invalid key, parse error, SDK error, timeout, empty text"]:::fallback
end

subgraph S7["Agent 1 Fact Verifier"]
  A10["server/agents/fact_verifier.py"]:::agent
  A11["Checks hallucinated packages, fake APIs, fake citations,<br/>wrong versions, fabricated standards, non-existent products"]:::agent
  A12["Gemini prompt requests strict JSON PASS or FAIL"]:::agent
  A13["Fallback heuristic<br/>react-query-optimizer, useOptimizedQuery,<br/>fabricated package credibility claims,<br/>adult-equivalent pediatric dosing warning"]:::fallback
  A14["Produces AgentResult id 1"]:::agent
end

subgraph S8["Agent 2 Math Validator"]
  A20["server/agents/math_validator.py"]:::agent
  A21["Checks formulas, unit conversions, numerical calculations,<br/>coefficients, exponents, dosage math, domain-specific math"]:::agent
  A22["Gemini prompt requests strict JSON PASS or FAIL"]:::agent
  A23["Fallback heuristic<br/>compound interest formula error,<br/>civil load factor mismatch,<br/>pediatric dose and max daily dose mismatch"]:::fallback
  A24["Produces AgentResult id 2"]:::agent
end

subgraph S9["Agent 3 Standards Checker"]
  A30["server/agents/standards_checker.py"]:::agent
  A31["Checks standards and compliance references<br/>IS codes, OWASP, NIST, HIPAA, IFRS, ASME, NFPA"]:::agent
  A32["Gemini prompt requests strict JSON PASS or FAIL"]:::agent
  A33["Fallback heuristic<br/>IS load guidance mismatch,<br/>software supply-chain risk from fake package,<br/>pediatric dosing guidance conflict"]:::fallback
  A34["Produces AgentResult id 3"]:::agent
end

subgraph S10["Agent 4 Logic Auditor"]
  A40["server/agents/logic_auditor.py"]:::agent
  A41["Checks reasoning chain, contradictions, missing steps,<br/>edge cases, conclusion validity, hidden assumptions"]:::agent
  A42["Gemini prompt requests strict JSON PASS or FAIL"]:::agent
  A43["Fallback heuristic<br/>unsafe design conclusion,<br/>adult-dose child logic flaw,<br/>monthly compounding conclusion mismatch"]:::fallback
  A44["Produces AgentResult id 4"]:::agent
end

subgraph S11["Agent 5 Domain Expert"]
  A50["server/agents/domain_expert.py"]:::agent
  A51["Receives original content plus summarized verdicts from Agents 1 to 4"]:::agent
  A52["Answers senior professional question<br/>would this be approved for production use"]:::agent
  A53["Fallback heuristic<br/>hard fail for pediatric harm,<br/>hard fail for hallucinated software supply chain guidance,<br/>civil fail when earlier agents indicate structural issues,<br/>general fail when fail_count is high"]:::fallback
  A54["Produces AgentResult id 5"]:::agent
end

subgraph S12["Agent 6 Correction Agent"]
  A60["server/agents/correction_agent.py"]:::agent
  A61["Runs only when final verdict is BLOCKED"]:::agent
  A62["Receives domain, full issue list, and original content"]:::agent
  A63["Gemini correction prompt<br/>preserve intent, fix all issues, output corrected content only"]:::agent
  A64["Fallback correction library<br/>software package correction,<br/>financial formula correction,<br/>healthcare dose correction,<br/>civil cautionary rewrite"]:::fallback
  A65["Returns corrected content string"]:::agent
end

subgraph S13["Persistence Layer"]
  P0["server/database.py"]:::backend
  P1["init_db<br/>create ~/.juror and verdicts table if missing"]:::backend
  P2["save_verdict<br/>request_id, timestamp, domain, final_verdict,<br/>fail_count, source, content_preview, full_response JSON"]:::backend
  P3["get_history(limit)<br/>latest rows ordered by id desc"]:::backend
  P4["stats route derives counts from history rows"]:::backend
end

subgraph S14["MCP Protocol Exposure"]
  MP0["server/mcp_server.py"]:::backend
  MP1["initialize<br/>returns protocolVersion, capabilities, serverInfo"]:::backend
  MP2["tools/list<br/>verify_output, get_verdict_history, get_stats"]:::backend
  MP3["tools/call verify_output<br/>build VerificationRequest source mcp and call run_jury"]:::backend
  MP4["tools/call get_verdict_history<br/>dump recent history as JSON text"]:::backend
  MP5["tools/call get_stats<br/>dump aggregate stats as JSON text"]:::backend
  MP6["Format human-readable MCP text result<br/>verdict, confidence, domain, fail count,<br/>per-agent issues, corrected output, issue summary"]:::backend
end

subgraph S15["Terminal Surface Internals"]
  TT0["terminal/cli.py start<br/>spawn server.main and launch Textual app"]:::surface
  TT1["terminal/cli.py run<br/>execute external AI command, capture stdout and stderr,<br/>then POST verify"]:::surface
  TT2["terminal/cli.py verify<br/>read file content and POST verify"]:::surface
  TT3["terminal/cli.py status history logs install-service"]:::surface
  TT4["terminal/app.py JurorApp<br/>two-panel dashboard plus verdict bar and history table"]:::surface
  TT5["Left panel<br/>AI output stream"]:::surface
  TT6["Right panel<br/>live jury log"]:::surface
  TT7["Bottom verdict panel<br/>APPROVED, FLAGGED, BLOCKED"]:::surface
  TT8["History table<br/>recent verdicts"]:::surface
  TT9["HTTP client to backend via httpx"]:::surface
end

subgraph S16["VS Code Extension Internals"]
  VS0["src/extension.ts<br/>activate extension, register commands and providers"]:::surface
  VS1["src/jurorClient.ts<br/>verify, getHistory, getStats, checkHealth"]:::surface
  VS2["src/sidebarProvider.ts<br/>webview rendering and message bridge"]:::surface
  VS3["src/fileWatcher.ts<br/>auto-verify on save with debounce"]:::surface
  VS4["src/decorationProvider.ts<br/>whole-line highlights for FLAGGED and BLOCKED"]:::surface
  VS5["src/statusBar.ts<br/>status bar entry point"]:::surface
  VS6["media/sidebar.html css js<br/>interactive sidebar UI"]:::surface
  VS7["User sees verdict banner, agent cards, issues,<br/>and optional correction preview"]:::surface
end

subgraph S17["Chrome Extension Internals"]
  CH0["manifest.json<br/>permissions, host permissions, content scripts, popup, service worker"]:::surface
  CH1["background.js<br/>toggle sidebar state"]:::surface
  CH2["content/sidebar.js<br/>inject sidebar shell and render UI states"]:::surface
  CH3["content/content.js<br/>site config, MutationObserver, POST verify, history load"]:::surface
  CH4["content/sidebar.css<br/>cyber-style sidebar visuals"]:::surface
  CH5["popup/popup.html js css<br/>backend status and sidebar toggle"]:::surface
  CH6["Observed AI sites<br/>claude.ai, chat.openai.com, chatgpt.com,<br/>gemini.google.com, copilot.microsoft.com"]:::surface
  CH7["User sees live verdict, agent cards, history, correction copy button"]:::surface
end

subgraph S18["Persistence and Auto-Start Integrations"]
  PS0["persistence/macos/com.juror.mcp.plist"]:::runtime
  PS1["persistence/linux/juror.service"]:::runtime
  PS2["persistence/windows/install-service.ps1"]:::runtime
  PS3["scripts/install.sh"]:::runtime
  PS4["scripts/install.ps1"]:::runtime
  PS5["Auto-start strategy<br/>run juror start --no-tui at login"]:::runtime
end

subgraph S19["Testing and Demo Scenarios"]
  TE0["tests/test_agents.py<br/>domain detection and agent smoke tests"]:::data
  TE1["tests/test_mcp.py<br/>health, tools/list, short-content rejection"]:::data
  TE2["tests/demo_scenarios/civil_engineering.py"]:::data
  TE3["tests/demo_scenarios/financial_modeling.py"]:::data
  TE4["tests/demo_scenarios/software_dev.py"]:::data
  TE5["tests/demo_scenarios/healthcare.py"]:::data
  TE6["Expected storyline<br/>civil blocked, finance flagged,<br/>software blocked, healthcare blocked"]:::data
end

subgraph S20["External Services and Dependencies"]
  X0["Google Gemini API<br/>generateContent endpoint"]:::external
  X1["httpx client<br/>POST to https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"]:::external
  X2["FastAPI and Uvicorn"]:::external
  X3["SQLite and aiosqlite"]:::external
  X4["httpx async client"]:::external
  X5["Textual and Rich"]:::external
  X6["VS Code Extension API"]:::external
  X7["Chrome Extension APIs"]:::external
  X8["dotenv environment loading"]:::external
end

U --> T1
U --> T2
U --> T3
U --> V1
U --> V2
U --> V3
U --> V4
U --> C1
U --> C2
U --> M1
U --> A1

T1 --> TT0 --> F0
T2 --> TT1 -->|POST verify| F2
T3 --> TT2 -->|POST verify| F2
T4 --> TT4
V1 --> VS0
V2 --> VS0
V3 --> VS3
V4 --> VS2
VS0 --> VS1
VS1 -->|POST verify or GET routes| F2
VS1 -->|GET history| F3
VS1 -->|GET stats| F4
VS1 -->|GET health| F1
VS2 --> VS6 --> VS7
VS3 --> VS1
VS4 --> VS7
VS5 --> VS2
C1 --> CH3
C2 --> CH5
CH0 --> CH1
CH0 --> CH2
CH0 --> CH3
CH0 --> CH5
CH3 -->|POST verify| F2
CH3 -->|GET history| F3
CH5 -->|GET health| F1
CH2 --> CH7
CH3 --> CH7
M1 -->|JSON-RPC to /mcp| F5
A1 -->|REST| F1
A1 -->|REST| F2
A1 -->|REST| F3
A1 -->|REST| F4

F0 --> F6
F0 --> P1
F0 --> Cfg0
F0 --> Cfg1
F1 --> Cfg0
F2 --> Cfg1
F2 --> O0
F3 --> P3
F4 --> P4
F5 --> MP0

Env0 --> Cfg0
Env1 --> Cfg0
Cfg0 --> Db0
Cfg0 --> Log0
Cfg0 --> G0
Cfg0 --> DD0
Cfg1 --> F2
Cfg1 --> O0
Cfg1 --> P0

O0 --> O1 --> O2 --> DD0
DD0 --> DD1 --> G2
G2 --> G3 --> G4 --> G5 --> G6 --> X0
G6 --> DD2 --> DD3 --> O3
DD0 -->|Gemini failure or invalid result| DD4 --> O3

O3 --> O4
O4 --> A10
O4 --> A20
O4 --> A30
O4 --> A40

A10 --> A11 --> A12 --> G2
A10 -->|Gemini failure or parse error| A13 --> A14
A20 --> A21 --> A22 --> G2
A20 -->|Gemini failure or parse error| A23 --> A24
A30 --> A31 --> A32 --> G2
A30 -->|Gemini failure or parse error| A33 --> A34
A40 --> A41 --> A42 --> G2
A40 -->|Gemini failure or parse error| A43 --> A44

G2 --> G7
G7 --> A14
G7 --> A24
G7 --> A34
G7 --> A44

A14 --> O5
A24 --> O5
A34 --> O5
A44 --> O5

O5 --> A50
A50 --> A51 --> A52 --> G2
A50 -->|Gemini failure or parse error| A53 --> A54
G7 --> A54
A54 --> O6

O6 --> O7 --> D0
D0 -->|yes| O8 --> O11
D0 -->|no| D1
D1 -->|yes| O9 --> O11
D1 -->|no| O10 --> O13

O13 --> A60 --> A61 --> A62 --> A63 --> G2
A60 -->|Gemini failure| A64 --> A65
G2 -->|raw corrected text| A65
A65 --> O14 --> O11

O11 --> O12 --> O15
O15 --> P2
O15 --> F2
P2 --> Db0
P3 --> Db0
P4 --> Db0

MP0 --> MP1
MP0 --> MP2
MP0 --> MP3 --> O0
MP0 --> MP4 --> P3
MP0 --> MP5 --> P4
MP3 --> MP6

TT4 --> TT5
TT4 --> TT6
TT4 --> TT7
TT4 --> TT8
TT4 --> TT9 --> F2
F3 --> TT8
F2 --> TT6
F2 --> TT7
F2 --> TT5

F2 --> VS1
F2 --> CH3
F3 --> CH3
F1 --> CH5

P0 --> X3
G0 --> X1
F0 --> X2
TT4 --> X5
VS0 --> X6
CH0 --> X7
Cfg0 --> X8
VS1 --> X4
TT9 --> X4

PS0 --> PS5 --> F0
PS1 --> PS5
PS2 --> PS5
PS3 --> PS5
PS4 --> PS5

TE0 --> A10
TE0 --> A20
TE0 --> A30
TE0 --> A40
TE1 --> MP0
TE1 --> F1
TE1 --> F2
TE2 --> O0
TE3 --> O0
TE4 --> O0
TE5 --> O0
TE6 --> O15

G8 --> A13
G8 --> A23
G8 --> A33
G8 --> A43
G8 --> A53
G8 --> A64
G8 --> DD4
O4 -->|timeout creates UNCERTAIN AgentResult| O6
F2 -->|source field can be terminal, vscode, chrome, api, mcp, test| P2
P2 -->|content preview and full response JSON| Db0
Db0 -->|history rows| F3
Db0 -->|stats aggregation input| F4
```

