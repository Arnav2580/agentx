/**
 * AI Hallucination Juror - Chrome Extension v4
 * Theme: Warm editorial - parchment + gold accents
 * Sidebar integrates with page (pushes content, no overlap)
 */

const JUROR_URL = "http://localhost:8000";
const PANEL_WIDTH = 340;

const TOKENS = {
  bgBase: "#1a1410",
  bgSurface: "#221c15",
  bgHeader: "#2a2018",
  bgRaised: "#312620",
  border: "#3d3025",
  borderMid: "#4f3d2d",
  textPrimary: "#ede0c8",
  textSecondary: "#a89070",
  textMuted: "#6b5040",
  textDim: "#4a3828",
  gold: "#c8a870",
  goldDim: "#7a6040",
  approved: "#7ab87a",
  flagged: "#c8a040",
  blocked: "#c86060",
  pass: "#7ab87a",
  fail: "#c86060",
  uncertain: "#c8a040",
};

let shadowHost = null;
let shadow = null;
let toggleBtn = null;
let isVerifying = false;
let sidebarOpen = false;
let lastHash = 0;

const SITES = {
  "claude.ai": {
    name: "Claude",
    sel: [
      '[data-is-streaming="false"] .font-claude-message',
      ".font-claude-message",
      '[data-testid="assistant-message"]',
    ],
    done: '[data-is-streaming="false"]',
  },
  "chat.openai.com": {
    name: "ChatGPT",
    sel: [
      '[data-message-author-role="assistant"] .markdown',
      '[data-message-author-role="assistant"]',
    ],
    done: 'button[data-testid="copy-turn-action-button"]',
  },
  "chatgpt.com": {
    name: "ChatGPT",
    sel: ['[data-message-author-role="assistant"] .markdown'],
    done: 'button[data-testid="copy-turn-action-button"]',
  },
  "gemini.google.com": {
    name: "Gemini",
    sel: ["model-response .response-content", ".response-content"],
    done: ".copy-button",
  },
  "aistudio.google.com": {
    name: "AI Studio",
    sel: [".response-container", '[class*="model"] [class*="response"]'],
    done: null,
  },
  "copilot.microsoft.com": {
    name: "Copilot",
    sel: [".ac-textBlock", '[class*="assistant-message"]'],
    done: null,
  },
  "perplexity.ai": {
    name: "Perplexity",
    sel: ['[class*="prose"]', '[data-testid="answer"]'],
    done: 'button[aria-label="Copy"]',
  },
  "www.perplexity.ai": {
    name: "Perplexity",
    sel: ['[class*="prose"]'],
    done: null,
  },
  "grok.com": {
    name: "Grok",
    sel: ['[class*="message"][class*="assistant"]', '[class*="prose"]'],
    done: null,
  },
  "chat.mistral.ai": {
    name: "Mistral",
    sel: ['[class*="assistant"] [class*="message-content"]', '[class*="prose"]'],
    done: null,
  },
  "poe.com": {
    name: "Poe",
    sel: ['[class*="Message_botMessageBubble"] [class*="content"]'],
    done: null,
  },
  "huggingface.co": {
    name: "HuggingChat",
    sel: ['[class*="assistant"] [class*="prose"]'],
    done: null,
  },
  "chat.deepseek.com": {
    name: "DeepSeek",
    sel: ['[class*="ds-markdown"]', '[class*="message"][class*="assistant"]'],
    done: null,
  },
  "you.com": {
    name: "You.com",
    sel: ['[data-testid="ai-response"]'],
    done: null,
  },
  "phind.com": {
    name: "Phind",
    sel: ['[class*="answer"] [class*="prose"]'],
    done: null,
  },
  "www.phind.com": {
    name: "Phind",
    sel: ['[class*="answer"] [class*="prose"]'],
    done: null,
  },
};

function getSite() {
  const hostname = location.hostname.replace(/^www\./, "");
  return SITES[hostname] || SITES[location.hostname] || null;
}

function extractResponse() {
  const site = getSite();
  if (!site) return null;

  for (const selector of site.sel) {
    try {
      const elements = document.querySelectorAll(selector);
      if (!elements.length) continue;
      const text = (elements[elements.length - 1].innerText || "").trim();
      if (text.length > 100) return text;
    } catch (_) {
      continue;
    }
  }

  return null;
}

function streamDone() {
  const site = getSite();
  if (!site?.done) return true;
  return document.querySelectorAll(site.done).length > 0;
}

function selectedText() {
  const text = (window.getSelection()?.toString() || "").trim();
  return text.length > 30 ? text : null;
}

function hashOf(text) {
  let value = 0;
  for (let index = 0; index < Math.min(text.length, 200); index += 1) {
    value = (Math.imul(31, value) + text.charCodeAt(index)) | 0;
  }
  return value;
}

function pushPage(open) {
  const padding = open ? `${PANEL_WIDTH}px` : "0px";
  const targets = [document.documentElement, document.body];
  for (const element of targets) {
    if (!element) continue;
    element.style.setProperty(
      "transition",
      "padding-right 0.28s ease, margin-right 0.28s ease",
      "important"
    );
    element.style.setProperty("padding-right", open ? padding : "", "important");
  }

  const wrappers = document.querySelectorAll(
    'main, #main, #app, #root, [role="main"], .main-content, body > div:first-child'
  );
  for (const wrapper of wrappers) {
    if (wrapper.scrollWidth > window.innerWidth * 0.5) {
      wrapper.style.setProperty("transition", "padding-right 0.28s ease", "important");
      wrapper.style.setProperty("padding-right", open ? padding : "", "important");
      break;
    }
  }
}

function makeToggle() {
  toggleBtn = document.createElement("div");
  toggleBtn.id = "juror-toggle";
  toggleBtn.textContent = "⬡";
  applyToggleStyle(false);
  toggleBtn.onclick = () => openSidebar(!sidebarOpen);
  document.documentElement.appendChild(toggleBtn);
}

function applyToggleStyle(open) {
  if (!toggleBtn) return;

  Object.assign(toggleBtn.style, {
    position: "fixed",
    bottom: "28px",
    right: open ? `${PANEL_WIDTH + 10}px` : "10px",
    width: "44px",
    height: "44px",
    background: open ? TOKENS.blocked : TOKENS.gold,
    color: TOKENS.bgBase,
    fontFamily: "Georgia, serif",
    fontWeight: "900",
    fontSize: open ? "18px" : "16px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: "50%",
    cursor: "pointer",
    zIndex: "2147483646",
    boxShadow: `0 3px 20px ${open ? `${TOKENS.blocked}60` : `${TOKENS.gold}60`}`,
    transition: "all 0.28s ease",
    userSelect: "none",
    pointerEvents: "all",
    border: `1px solid ${open ? `${TOKENS.blocked}80` : `${TOKENS.gold}80`}`,
  });
  toggleBtn.textContent = open ? "×" : "⬡";
  toggleBtn.title = open ? "Close Juror" : "Open AI Hallucination Juror";
}

function buildSidebar() {
  shadowHost = document.createElement("div");
  shadowHost.id = "juror-shadow-host";
  Object.assign(shadowHost.style, {
    position: "fixed",
    top: "0",
    right: "0",
    width: "0",
    height: "0",
    zIndex: "2147483647",
    pointerEvents: "none",
  });
  document.documentElement.appendChild(shadowHost);

  shadow = shadowHost.attachShadow({ mode: "open" });

  const site = getSite();
  const T = TOKENS;

  shadow.innerHTML = `
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :host { all: initial; }

  #panel {
    position: fixed;
    top: 0;
    right: -${PANEL_WIDTH + 8}px;
    width: ${PANEL_WIDTH}px;
    height: 100vh;
    background: ${T.bgBase};
    border-left: 1px solid ${T.border};
    display: flex;
    flex-direction: column;
    font-family: Georgia, "Palatino Linotype", serif;
    font-size: 14px;
    color: ${T.textPrimary};
    transition: right 0.28s cubic-bezier(0.4, 0, 0.2, 1);
    pointer-events: all;
    overflow: hidden;
    box-shadow: -8px 0 40px rgba(0,0,0,0.5);
  }
  #panel.open { right: 0; }

  .hdr {
    background: ${T.bgHeader};
    border-bottom: 1px solid ${T.border};
    padding: 14px 16px 12px;
    flex-shrink: 0;
  }
  .hdr-top {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
  }
  .logo {
    color: ${T.gold};
    font-size: 20px;
    flex-shrink: 0;
    line-height: 1;
  }
  .brand {
    flex: 1;
    min-width: 0;
  }
  .brand-name {
    display: block;
    color: ${T.gold};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    font-family: "Courier New", monospace;
  }
  .brand-site {
    display: block;
    color: ${T.textMuted};
    font-size: 11px;
    margin-top: 2px;
    font-family: "Courier New", monospace;
    letter-spacing: 0.5px;
  }
  .close-btn {
    background: transparent;
    border: 1px solid ${T.borderMid};
    color: ${T.textMuted};
    width: 28px;
    height: 28px;
    border-radius: 50%;
    cursor: pointer;
    font-size: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: all 0.15s;
    font-family: Georgia, serif;
  }
  .close-btn:hover {
    border-color: ${T.blocked};
    color: ${T.blocked};
    background: ${T.blocked}15;
  }

  .btn-row {
    display: flex;
    gap: 8px;
  }
  .btn {
    flex: 1;
    padding: 8px 10px;
    border-radius: 6px;
    cursor: pointer;
    font-family: "Courier New", monospace;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
    text-align: center;
    transition: all 0.15s;
    border: 1px solid;
  }
  .btn-primary {
    background: ${T.gold}18;
    border-color: ${T.gold}50;
    color: ${T.gold};
  }
  .btn-primary:hover { background: ${T.gold}28; border-color: ${T.gold}80; }
  .btn-secondary {
    background: transparent;
    border-color: ${T.border};
    color: ${T.textSecondary};
  }
  .btn-secondary:hover { border-color: ${T.borderMid}; color: ${T.textPrimary}; }

  .strip {
    padding: 6px 16px;
    background: ${T.bgBase};
    border-bottom: 1px solid ${T.border};
    font-family: "Courier New", monospace;
    font-size: 10px;
    color: ${T.textDim};
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: 8px;
    letter-spacing: 0.5px;
  }
  .dot { font-size: 7px; }
  .dot.auto { color: ${T.approved}; }
  .dot.manual { color: ${T.flagged}; }
  kbd {
    background: ${T.bgRaised};
    border: 1px solid ${T.border};
    border-radius: 3px;
    padding: 1px 5px;
    font-size: 10px;
    color: ${T.textMuted};
    font-family: "Courier New", monospace;
  }

  .body {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 16px;
    scrollbar-width: thin;
    scrollbar-color: ${T.border} transparent;
  }
  .body::-webkit-scrollbar { width: 4px; }
  .body::-webkit-scrollbar-thumb { background: ${T.border}; border-radius: 2px; }

  .idle {
    text-align: center;
    padding: 32px 16px;
    color: ${T.textMuted};
    line-height: 1.8;
  }
  .idle-icon { font-size: 32px; color: ${T.textDim}; margin-bottom: 12px; }
  .idle-title { color: ${T.textSecondary}; font-size: 14px; margin-bottom: 6px; }
  .idle-sub { font-size: 12px; color: ${T.textMuted}; line-height: 1.7; }
  .idle-sub b { color: ${T.gold}; font-style: normal; }

  .loading { text-align: center; padding: 32px 16px; }
  .spin {
    font-size: 30px;
    color: ${T.gold};
    display: inline-block;
    animation: rot 1.4s ease-in-out infinite;
    margin-bottom: 12px;
  }
  @keyframes rot { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
  .loading-title { color: ${T.textSecondary}; font-size: 14px; margin-bottom: 6px; }
  .loading-sub { color: ${T.textMuted}; font-size: 12px; font-family: "Courier New", monospace; }

  .err-box {
    background: ${T.blocked}12;
    border: 1px solid ${T.blocked}40;
    border-radius: 8px;
    padding: 14px 16px;
    color: ${T.blocked};
    font-size: 13px;
    line-height: 1.6;
  }
  .err-hint {
    display: block;
    margin-top: 8px;
    font-family: "Courier New", monospace;
    font-size: 11px;
    color: ${T.textMuted};
    background: ${T.bgRaised};
    padding: 5px 8px;
    border-radius: 4px;
  }
  .warn-box {
    background: ${T.flagged}12;
    border: 1px solid ${T.flagged}40;
    border-radius: 8px;
    padding: 12px 14px;
    color: ${T.flagged};
    font-size: 13px;
    line-height: 1.6;
  }

  .verdict-badge {
    border-radius: 10px;
    border: 1px solid;
    padding: 18px 16px;
    text-align: center;
    margin-bottom: 14px;
  }
  .verdict-icon { font-size: 28px; margin-bottom: 6px; display: block; }
  .verdict-label {
    font-size: 18px;
    font-weight: 700;
    letter-spacing: 3px;
    text-transform: uppercase;
    font-family: "Courier New", monospace;
    margin-bottom: 8px;
    display: block;
  }
  .verdict-meta {
    font-size: 11px;
    color: ${T.textMuted};
    font-family: "Courier New", monospace;
    display: flex;
    justify-content: center;
    gap: 10px;
    flex-wrap: wrap;
  }
  .verdict-meta span { white-space: nowrap; }
  .domain-tag {
    display: inline-block;
    font-family: "Courier New", monospace;
    font-size: 10px;
    color: ${T.textMuted};
    background: ${T.bgSurface};
    border: 1px solid ${T.border};
    border-radius: 4px;
    padding: 3px 8px;
    margin-bottom: 14px;
    letter-spacing: 1px;
    text-transform: uppercase;
  }

  .section-label {
    font-family: "Courier New", monospace;
    font-size: 9px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: ${T.textMuted};
    margin-bottom: 8px;
    border-bottom: 1px solid ${T.border};
    padding-bottom: 5px;
  }

  .agents { display: flex; flex-direction: column; gap: 6px; margin-bottom: 14px; }
  .agent {
    background: ${T.bgSurface};
    border: 1px solid ${T.border};
    border-radius: 7px;
    padding: 9px 12px;
    transition: border-color 0.15s;
  }
  .agent.fail { border-color: ${T.fail}35; background: ${T.fail}08; }
  .agent.pass { border-color: ${T.pass}20; }

  .agent-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2px;
    gap: 8px;
  }
  .agent-id {
    font-family: "Courier New", monospace;
    font-size: 10px;
    color: ${T.textMuted};
    margin-right: 6px;
    flex-shrink: 0;
  }
  .agent-name { font-size: 12px; color: ${T.textSecondary}; flex: 1; }
  .agent-verd {
    font-family: "Courier New", monospace;
    font-size: 11px;
    font-weight: 700;
    flex-shrink: 0;
  }
  .agent-issue {
    font-size: 11px;
    color: ${T.textMuted};
    padding-left: 14px;
    margin-top: 4px;
    line-height: 1.5;
    border-left: 2px solid ${T.fail}40;
    margin-left: 2px;
  }

  .issues-block {
    background: ${T.bgSurface};
    border: 1px solid ${T.border};
    border-radius: 7px;
    padding: 10px 12px;
    margin-bottom: 14px;
  }
  .issue-line {
    font-size: 12px;
    color: ${T.textSecondary};
    padding: 3px 0;
    border-bottom: 1px solid ${T.border};
    line-height: 1.5;
  }
  .issue-line:last-child { border-bottom: none; }
  .issue-dot { color: ${T.flagged}; margin-right: 6px; }

  .correction {
    background: ${T.bgSurface};
    border: 1px solid ${T.goldDim}50;
    border-radius: 7px;
    padding: 12px;
    margin-bottom: 14px;
  }
  .correction-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 10px;
  }
  .correction-icon { color: ${T.gold}; font-size: 14px; }
  .correction-title {
    font-family: "Courier New", monospace;
    font-size: 10px;
    letter-spacing: 1.5px;
    color: ${T.gold};
    text-transform: uppercase;
  }
  .correction-body {
    font-size: 12px;
    color: ${T.textSecondary};
    line-height: 1.7;
    max-height: 150px;
    overflow-y: auto;
    white-space: pre-wrap;
    margin-bottom: 10px;
    font-family: "Courier New", monospace;
    scrollbar-width: thin;
    scrollbar-color: ${T.border} transparent;
  }
  .copy-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: ${T.gold}18;
    border: 1px solid ${T.gold}40;
    color: ${T.gold};
    padding: 6px 12px;
    border-radius: 5px;
    cursor: pointer;
    font-family: "Courier New", monospace;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    transition: all 0.15s;
  }
  .copy-btn:hover { background: ${T.gold}28; }

  .footer {
    flex-shrink: 0;
    padding: 10px 16px;
    border-top: 1px solid ${T.border};
    background: ${T.bgHeader};
  }
  .hist-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 4px 0;
    border-bottom: 1px solid ${T.border};
    font-size: 11px;
    font-family: "Courier New", monospace;
    gap: 8px;
  }
  .hist-row:last-child { border-bottom: none; }
  .hist-verdict { font-weight: 700; letter-spacing: 0.5px; }
  .hist-domain { color: ${T.textMuted}; font-size: 10px; text-align: right; }
</style>

<div id="panel">
  <div class="hdr">
    <div class="hdr-top">
      <span class="logo">⬡</span>
      <div class="brand">
        <span class="brand-name">Hallucination Juror</span>
        <span class="brand-site" id="site-label">${site ? `${site.name} · auto-scan` : location.hostname}</span>
      </div>
      <button class="close-btn" id="btn-close" title="Close sidebar">×</button>
    </div>
    <div class="btn-row">
      <button class="btn btn-primary" id="btn-scan">▶ Scan Response</button>
      <button class="btn btn-secondary" id="btn-sel">◈ Selection</button>
    </div>
  </div>

  <div class="strip">
    <span class="dot ${site ? "auto" : "manual"}">●</span>
    <span>${site ? "Auto-scanning" : "Manual mode"}</span>
    <span style="flex:1"></span>
    <kbd>Ctrl+Shift+J</kbd>
  </div>

  <div class="body" id="body">
    <div class="idle">
      <div class="idle-icon">⬡</div>
      <div class="idle-title">Ready to verify</div>
      <div class="idle-sub">${site
        ? `Click <b>Scan Response</b> after ${site.name} replies`
        : 'Select any text then click <b>Selection</b>'}</div>
    </div>
  </div>

  <div class="footer">
    <div class="section-label" style="margin-bottom:6px">Recent verdicts</div>
    <div id="hist-list"></div>
  </div>
</div>
  `;

  shadow.getElementById("btn-close").onclick = () => openSidebar(false);
  shadow.getElementById("btn-scan").onclick = scanResponse;
  shadow.getElementById("btn-sel").onclick = scanSelection;

  void loadHistory();
}

function openSidebar(open) {
  sidebarOpen = open;
  const panel = shadow?.getElementById("panel");
  if (!panel) return;

  if (open) {
    panel.classList.add("open");
    shadowHost.style.pointerEvents = "all";
    pushPage(true);
  } else {
    panel.classList.remove("open");
    shadowHost.style.pointerEvents = "none";
    pushPage(false);
  }

  applyToggleStyle(open);
}

function setBody(html) {
  const body = shadow?.getElementById("body");
  if (body) body.innerHTML = html;
}

const T = TOKENS;

function showIdle() {
  const site = getSite();
  setBody(`<div class="idle">
    <div class="idle-icon">⬡</div>
    <div class="idle-title">Ready to verify</div>
    <div class="idle-sub">${site
      ? `Click <b>Scan Response</b> after ${site.name} replies`
      : 'Select any text then click <b>Selection</b>'}</div>
  </div>`);
}

function showLoading(label) {
  setBody(`<div class="loading">
    <div class="spin">⬡</div>
    <div class="loading-title">Jury deliberating...</div>
    <div class="loading-sub">5 agents · Gemini 2.5 Flash<br>${label || ""}</div>
  </div>`);
}

function showErr(message, hint) {
  setBody(`<div class="err-box">
    ${esc(message)}
    ${hint ? `<code class="err-hint">${esc(hint)}</code>` : ""}
  </div>`);
}

function showWarn(message) {
  setBody(`<div class="warn-box">${esc(message)}</div>`);
}

function verdictColor(verdict) {
  return { APPROVED: T.approved, FLAGGED: T.flagged, BLOCKED: T.blocked }[verdict] || T.textMuted;
}

function verdictIcon(verdict) {
  return { APPROVED: "✓", FLAGGED: "⚠", BLOCKED: "✕" }[verdict] || "?";
}

function showVerdict(data) {
  if (!data?.final_verdict) {
    showErr("Invalid server response");
    return;
  }

  const verdict = data.final_verdict;
  const color = verdictColor(verdict);
  const icon = verdictIcon(verdict);

  let html = `
    <div class="verdict-badge" style="border-color:${color}40;background:${color}10">
      <span class="verdict-icon" style="color:${color}">${icon}</span>
      <span class="verdict-label" style="color:${color}">${verdict}</span>
      <div class="verdict-meta">
        <span>${data.fail_count}/5 agents flagged</span>
        <span>·</span>
        <span>${Math.round((data.overall_confidence || 0) * 100)}% confidence</span>
        <span>·</span>
        <span>${data.execution_time_ms}ms</span>
      </div>
    </div>
    <div class="domain-tag">${esc((data.domain || "general").replace(/_/g, " "))}</div>
  `;

  html += '<div class="section-label">Agent verdicts</div><div class="agents">';
  for (const agent of data.agent_results || []) {
    const verdictColorValue = {
      PASS: T.pass,
      FAIL: T.fail,
      UNCERTAIN: T.uncertain,
    }[agent.verdict] || T.textMuted;
    const verdictMarker = { PASS: "✓", FAIL: "✕", UNCERTAIN: "?" }[agent.verdict] || "?";
    const klass = agent.verdict === "FAIL" ? "fail" : agent.verdict === "PASS" ? "pass" : "";
    const issues = (agent.issues || [])
      .slice(0, 2)
      .map((issue) => `<div class="agent-issue">${esc(issue)}</div>`)
      .join("");
    html += `<div class="agent ${klass}">
      <div class="agent-row">
        <span class="agent-id">A${agent.agent_id}</span>
        <span class="agent-name">${esc(agent.agent_name)}</span>
        <span class="agent-verd" style="color:${verdictColorValue}">${verdictMarker} ${agent.verdict}</span>
      </div>${issues}
    </div>`;
  }
  html += "</div>";

  const issues = (data.issues_summary || []).filter(Boolean).slice(0, 5);
  if (issues.length) {
    html += `<div class="section-label">Issues found</div>
    <div class="issues-block">
      ${issues.map((issue) => `<div class="issue-line"><span class="issue-dot">▸</span>${esc(issue)}</div>`).join("")}
    </div>`;
  }

  if (verdict === "BLOCKED" && data.correction) {
    html += `<div class="correction">
      <div class="correction-header">
        <span class="correction-icon">✦</span>
        <span class="correction-title">Corrected output</span>
      </div>
      <div class="correction-body">${esc(data.correction.substring(0, 600))}${data.correction.length > 600 ? "\n..." : ""}</div>
      <button class="copy-btn" id="copy-fix">⎘ Copy full correction</button>
    </div>`;
  }

  setBody(html);

  const copyButton = shadow?.getElementById("copy-fix");
  if (copyButton) {
    copyButton.onclick = () => {
      void navigator.clipboard.writeText(data.correction);
      copyButton.textContent = "✓ Copied";
      setTimeout(() => {
        copyButton.innerHTML = "⎘ Copy full correction";
      }, 2000);
    };
  }

  addHistory(verdict, data.domain, color);
}

function addHistory(verdict, domain, color) {
  const history = shadow?.getElementById("hist-list");
  if (!history) return;

  const row = document.createElement("div");
  row.className = "hist-row";
  row.innerHTML = `
    <span class="hist-verdict" style="color:${color}">${esc(verdict)}</span>
    <span class="hist-domain">${esc((domain || "general").replace(/_/g, " "))}</span>
  `;
  history.insertBefore(row, history.firstChild);
  while (history.children.length > 5) {
    history.removeChild(history.lastChild);
  }
}

async function loadHistory() {
  try {
    const response = await fetch(`${JUROR_URL}/history?limit=5`, { signal: AbortSignal.timeout(3000) });
    if (!response.ok) return;
    const data = await response.json();
    for (const item of (data.history || []).slice(0, 5)) {
      addHistory(item.final_verdict, item.domain, verdictColor(item.final_verdict));
    }
  } catch (_) {
    return;
  }
}

async function verify(content, label) {
  if (isVerifying) {
    showWarn("Already verifying — please wait a moment");
    return;
  }

  const contentHash = hashOf(content);
  if (contentHash === lastHash) {
    showWarn("Already verified this content. Get a new AI response first.");
    return;
  }

  isVerifying = true;
  openSidebar(true);
  showLoading(label);

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60000);
    const response = await fetch(`${JUROR_URL}/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content: content.substring(0, 3000),
        source: "chrome",
      }),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!response.ok) throw new Error(`Server returned ${response.status}`);
    const data = await response.json();
    if (!data.final_verdict || !Array.isArray(data.agent_results)) {
      throw new Error("Unexpected response from server");
    }

    lastHash = contentHash;
    showVerdict(data);
  } catch (error) {
    if (error?.name === "AbortError") {
      showErr("Request timed out", "python -m server.main");
    } else if (error instanceof Error && (error.message.includes("fetch") || error.message.includes("NetworkError"))) {
      showErr("Cannot reach Juror server on localhost:8000", "python -m server.main");
    } else if (error instanceof Error) {
      showErr(error.message);
    } else {
      showErr("Unknown Chrome extension error");
    }
  } finally {
    isVerifying = false;
  }
}

async function scanResponse() {
  const text = extractResponse();
  if (!text) {
    openSidebar(true);
    showWarn(
      getSite()
        ? `No complete response found yet — wait for ${getSite().name} to finish responding, then click Scan Response.`
        : "Scan Response only works on known AI sites. Select text and use Selection instead."
    );
    return;
  }
  await verify(text, `${getSite()?.name || "page"} response`);
}

async function scanSelection() {
  const text = selectedText();
  if (!text) {
    openSidebar(true);
    showWarn("No text selected. Highlight any text on the page first, then click Selection.");
    return;
  }
  await verify(text, "selected text");
}

function startMonitor() {
  if (!getSite()) return;

  let debounce = null;
  let lastSeen = "";
  new MutationObserver(() => {
    if (isVerifying) return;
    clearTimeout(debounce);
    debounce = setTimeout(() => {
      if (!streamDone()) return;
      const text = extractResponse();
      if (!text || text === lastSeen || text.length < 100) return;
      if (hashOf(text) === lastHash) return;
      lastSeen = text;
      void verify(text, `${getSite().name} · auto`);
    }, 2200);
  }).observe(document.body, { childList: true, subtree: true });
}

document.addEventListener("keydown", (event) => {
  if (event.ctrlKey && event.shiftKey && event.key === "J") {
    event.preventDefault();
    openSidebar(true);
    const text = selectedText();
    if (text) {
      void verify(text, "keyboard · selected text");
    } else {
      const response = extractResponse();
      if (response) {
        void verify(response, "keyboard · latest response");
      } else {
        showWarn("Select text to verify, or wait for an AI response.");
      }
    }
  }

  if (event.key === "Escape" && sidebarOpen) {
    openSidebar(false);
  }
});

chrome.runtime.onMessage.addListener((message) => {
  if (message.type === "MANUAL_VERIFY") void scanResponse();
  if (message.type === "VERIFY_SELECTED_TEXT") void scanSelection();
  if (message.type === "TOGGLE_SIDEBAR") openSidebar(!sidebarOpen);
});

function esc(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

makeToggle();
buildSidebar();
startMonitor();
