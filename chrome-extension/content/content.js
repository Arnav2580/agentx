/**
 * AI Hallucination Juror - Content Script v3
 * Fixes: persistent toggle button, responsive page shift, clean open/close
 */

const JUROR_URL = "http://localhost:8000";
const SIDEBAR_WIDTH = 310;

let shadowRoot = null;
let toggleBtn = null;
let isVerifying = false;
let lastVerifiedHash = "";
let sidebarOpen = false;

const AI_SITES = {
  "claude.ai": {
    name: "Claude",
    selectors: [
      '[data-is-streaming="false"] .font-claude-message',
      '[data-is-streaming="false"] [class*="font-claude"]',
      ".font-claude-message",
      '[data-testid="assistant-message"]',
    ],
    doneSelector: '[data-is-streaming="false"]',
  },
  "chat.openai.com": {
    name: "ChatGPT",
    selectors: [
      '[data-message-author-role="assistant"] .markdown',
      '[data-message-author-role="assistant"]',
    ],
    doneSelector: 'button[data-testid="copy-turn-action-button"]',
  },
  "chatgpt.com": {
    name: "ChatGPT",
    selectors: ['[data-message-author-role="assistant"] .markdown'],
    doneSelector: 'button[data-testid="copy-turn-action-button"]',
  },
  "gemini.google.com": {
    name: "Gemini",
    selectors: ["model-response .response-content", ".response-content"],
    doneSelector: ".copy-button",
  },
  "aistudio.google.com": {
    name: "AI Studio",
    selectors: [".response-container", '[class*="model"] [class*="response"]'],
    doneSelector: null,
  },
  "copilot.microsoft.com": {
    name: "Copilot",
    selectors: [".ac-textBlock", '[class*="assistant-message"]'],
    doneSelector: null,
  },
  "perplexity.ai": {
    name: "Perplexity",
    selectors: ['[class*="prose"]', '[data-testid="answer"]'],
    doneSelector: 'button[aria-label="Copy"]',
  },
  "www.perplexity.ai": {
    name: "Perplexity",
    selectors: ['[class*="prose"]'],
    doneSelector: null,
  },
  "grok.com": {
    name: "Grok",
    selectors: ['[class*="message"][class*="assistant"]', '[class*="prose"]'],
    doneSelector: null,
  },
  "chat.mistral.ai": {
    name: "Mistral",
    selectors: ['[class*="assistant"] [class*="message-content"]', '[class*="prose"]'],
    doneSelector: null,
  },
  "poe.com": {
    name: "Poe",
    selectors: ['[class*="Message_botMessageBubble"] [class*="content"]'],
    doneSelector: null,
  },
  "huggingface.co": {
    name: "HuggingChat",
    selectors: ['[class*="assistant"] [class*="prose"]'],
    doneSelector: null,
  },
  "chat.deepseek.com": {
    name: "DeepSeek",
    selectors: ['[class*="ds-markdown"]', '[class*="message"][class*="assistant"]'],
    doneSelector: null,
  },
  "you.com": {
    name: "You.com",
    selectors: ['[data-testid="ai-response"]', '[class*="youchat-text"]'],
    doneSelector: null,
  },
  "phind.com": {
    name: "Phind",
    selectors: ['[class*="answer"] [class*="prose"]'],
    doneSelector: null,
  },
  "www.phind.com": {
    name: "Phind",
    selectors: ['[class*="answer"] [class*="prose"]'],
    doneSelector: null,
  },
};

function getSiteConfig() {
  const host = window.location.hostname.replace(/^www\./, "");
  return AI_SITES[host] || AI_SITES[window.location.hostname] || null;
}

function extractResponse() {
  const config = getSiteConfig();
  if (!config) return null;

  for (const selector of config.selectors) {
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

function isStreamDone() {
  const config = getSiteConfig();
  if (!config?.doneSelector) return true;
  return document.querySelectorAll(config.doneSelector).length > 0;
}

function getSelectedText() {
  const text = (window.getSelection()?.toString() || "").trim();
  return text.length > 30 ? text : null;
}

function hash(text) {
  let value = 0;
  for (let index = 0; index < Math.min(text.length, 200); index += 1) {
    value = (Math.imul(31, value) + text.charCodeAt(index)) | 0;
  }
  return String(value);
}

function createToggleButton() {
  toggleBtn = document.createElement("div");
  toggleBtn.id = "juror-float-btn";
  setToggleStyle(false);
  toggleBtn.onclick = () => setSidebar(!sidebarOpen);
  document.documentElement.appendChild(toggleBtn);
}

function setToggleStyle(open) {
  if (!toggleBtn) return;

  toggleBtn.textContent = open ? "× CLOSE" : "⬡ JUROR";
  Object.assign(toggleBtn.style, {
    position: "fixed",
    bottom: "24px",
    right: open ? `${SIDEBAR_WIDTH + 12}px` : "12px",
    background: open ? "#f87171" : "#00ff9d",
    color: "#060a0f",
    fontFamily: "'Courier New', monospace",
    fontWeight: "900",
    fontSize: "10px",
    letterSpacing: "1.5px",
    padding: "9px 14px",
    borderRadius: "20px",
    cursor: "pointer",
    zIndex: "2147483646",
    boxShadow: open
      ? "0 2px 16px rgba(248,113,113,0.5)"
      : "0 2px 16px rgba(0,255,157,0.5)",
    transition: "all 0.25s cubic-bezier(0.4,0,0.2,1)",
    userSelect: "none",
    pointerEvents: "all",
    whiteSpace: "nowrap",
  });
}

function buildSidebar() {
  const host = document.createElement("div");
  host.id = "juror-host";
  Object.assign(host.style, {
    position: "fixed",
    top: "0",
    right: "0",
    width: "0",
    height: "0",
    zIndex: "2147483647",
    pointerEvents: "none",
  });
  document.documentElement.appendChild(host);

  shadowRoot = host.attachShadow({ mode: "open" });
  const config = getSiteConfig();

  shadowRoot.innerHTML = `
    <style>
      *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

      #panel {
        position: fixed;
        top: 0;
        right: -${SIDEBAR_WIDTH + 4}px;
        width: ${SIDEBAR_WIDTH}px;
        height: 100vh;
        background: #060a0f;
        border-left: 1px solid #00ff9d28;
        box-shadow: -6px 0 40px rgba(0,0,0,0.6);
        display: flex;
        flex-direction: column;
        font-family: "Courier New", Courier, monospace;
        font-size: 12px;
        color: #e2e8f0;
        transition: right 0.25s cubic-bezier(0.4,0,0.2,1);
        pointer-events: all;
        overflow: hidden;
      }
      #panel.open { right: 0; }

      .hdr {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 10px 12px;
        background: #0a0f1a;
        border-bottom: 1px solid #00ff9d18;
        flex-shrink: 0;
      }
      .logo { color: #00ff9d; font-size: 15px; }
      .titles { flex: 1; min-width: 0; }
      .title { display: block; color: #00ff9d; font-size: 9px; font-weight: 700; letter-spacing: 1.5px; }
      .site { display: block; color: #334155; font-size: 9px; margin-top: 1px; }

      .btns { display: flex; gap: 4px; align-items: center; flex-shrink: 0; }
      button {
        font-family: "Courier New", monospace;
        font-weight: 700;
        cursor: pointer;
        border-radius: 4px;
        transition: background 0.15s, border-color 0.15s;
        border: 1px solid;
        line-height: 1;
      }
      .b-scan { background:#00ff9d10; border-color:#00ff9d38; color:#00ff9d; padding:3px 8px; font-size:9px; letter-spacing:.5px; }
      .b-scan:hover { background:#00ff9d22; }
      .b-sel { background:#00d4ff0e; border-color:#00d4ff32; color:#00d4ff; padding:3px 8px; font-size:9px; letter-spacing:.5px; }
      .b-sel:hover { background:#00d4ff20; }
      .b-close { background:transparent; border-color:transparent; color:#475569; padding:3px 7px; font-size:16px; }
      .b-close:hover { color:#94a3b8; border-color:#ffffff15; }

      .hint {
        padding: 4px 12px;
        background: #060d18;
        border-bottom: 1px solid #ffffff06;
        font-size: 9px;
        color: #1e293b;
        flex-shrink: 0;
        display: flex;
        align-items: center;
        gap: 6px;
        flex-wrap: wrap;
      }
      .dot-auto { color: #34d399; font-size: 8px; }
      .dot-man { color: #fbbf24; font-size: 8px; }
      kbd {
        background: #1a2332;
        border: 1px solid #2d3f55;
        border-radius: 2px;
        padding: 1px 4px;
        font-size: 8px;
        color: #475569;
        font-family: "Courier New", monospace;
      }

      .body {
        flex: 1;
        overflow-y: auto;
        overflow-x: hidden;
        padding: 12px;
        scrollbar-width: thin;
        scrollbar-color: #1e293b transparent;
      }
      .body::-webkit-scrollbar { width: 3px; }
      .body::-webkit-scrollbar-track { background: transparent; }
      .body::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 2px; }

      .idle { text-align: center; padding: 28px 12px; color: #1e293b; line-height: 1.8; }
      .idle-icon { font-size: 30px; color: #0d1117; margin-bottom: 10px; }
      .idle-main { color: #334155; font-size: 11px; }
      .idle-sub { font-size: 10px; color: #1a2332; margin-top: 6px; line-height: 1.6; }

      .loading { text-align: center; padding: 28px 12px; }
      .spin { font-size: 28px; display: inline-block; color: #fbbf24; animation: rot 1.2s linear infinite; margin-bottom: 8px; }
      @keyframes rot { to { transform: rotate(360deg); } }
      .loading-main { color: #fbbf24; font-size: 11px; }
      .loading-sub { color: #475569; font-size: 10px; margin-top: 4px; }

      .err-box {
        background: #f8717110;
        border: 1px solid #f8717130;
        border-radius: 6px;
        padding: 12px;
        color: #f87171;
        font-size: 11px;
        line-height: 1.6;
      }
      .err-box code {
        display: block;
        margin-top: 6px;
        background: #060a0f;
        padding: 5px 8px;
        border-radius: 3px;
        font-size: 10px;
        color: #94a3b8;
      }
      .warn-box {
        background: #fbbf2410;
        border: 1px solid #fbbf2428;
        border-radius: 6px;
        padding: 10px 12px;
        color: #fbbf24;
        font-size: 11px;
        line-height: 1.6;
      }

      .v-banner {
        border: 1px solid;
        border-radius: 8px;
        padding: 14px;
        text-align: center;
        margin-bottom: 10px;
      }
      .v-main { font-weight: 900; font-size: 16px; letter-spacing: 2px; margin-bottom: 4px; }
      .v-sub { font-size: 10px; color: #64748b; }
      .v-dom {
        font-size: 9px;
        color: #334155;
        letter-spacing: 1px;
        text-transform: uppercase;
        margin-bottom: 10px;
      }

      .agents { display: flex; flex-direction: column; gap: 5px; }
      .agent {
        background: #0a0f1a;
        border: 1px solid #ffffff06;
        border-radius: 5px;
        padding: 7px 10px;
      }
      .agent.fail { border-color: #f8717120; background: #f8717106; }
      .agent.pass { border-color: #34d39910; }
      .a-row { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
      .a-name { color: #64748b; font-size: 10px; }
      .a-verd { font-size: 10px; font-weight: 700; }
      .a-issue { color: #475569; font-size: 9px; padding-left: 10px; margin-top: 3px; line-height: 1.5; }

      .iss-block {
        margin-top: 8px;
        padding: 8px 10px;
        background: #0a0f1a;
        border: 1px solid #ffffff06;
        border-radius: 5px;
      }
      .iss-title { color: #334155; font-size: 9px; letter-spacing: 1px; margin-bottom: 5px; }
      .iss-line { color: #475569; font-size: 10px; margin-bottom: 3px; line-height: 1.4; }

      .fix {
        margin-top: 10px;
        padding: 10px;
        background: #f472b608;
        border: 1px solid #f472b622;
        border-radius: 6px;
      }
      .fix-title { color: #f472b6; font-size: 10px; font-weight: 700; margin-bottom: 6px; }
      .fix-body {
        color: #94a3b8;
        font-size: 9px;
        line-height: 1.6;
        max-height: 130px;
        overflow-y: auto;
        white-space: pre-wrap;
        margin-bottom: 8px;
        scrollbar-width: thin;
        scrollbar-color: #1e293b transparent;
      }
      .copy-btn {
        background: #f472b610;
        border: 1px solid #f472b630;
        color: #f472b6;
        padding: 4px 10px;
        border-radius: 3px;
        cursor: pointer;
        font-family: "Courier New", monospace;
        font-size: 9px;
      }
      .copy-btn:hover { background: #f472b620; }

      .footer {
        flex-shrink: 0;
        padding: 8px 12px;
        border-top: 1px solid #0d1117;
        background: #060a0f;
      }
      .f-title { color: #1a2332; font-size: 9px; letter-spacing: 1.5px; margin-bottom: 5px; }
      .hist { font-size: 10px; padding: 2px 0; border-bottom: 1px solid #0a0f1a; }
    </style>

    <div id="panel">
      <div class="hdr">
        <span class="logo">⬡</span>
        <div class="titles">
          <span class="title">HALLUCINATION JUROR</span>
          <span class="site" id="site-lbl">${config ? `${config.name} · auto-scan ON` : `${window.location.hostname} · manual scan`}</span>
        </div>
        <div class="btns">
          <button class="b-scan" id="btn-scan">SCAN</button>
          <button class="b-sel" id="btn-sel">SELECTION</button>
          <button class="b-close" id="btn-x">×</button>
        </div>
      </div>

      <div class="hint">
        <span class="${config ? "dot-auto" : "dot-man"}">●</span>
        <span style="color:#334155">${config ? "Auto-scan active" : "Select text to scan"}</span>
        <span>&middot;</span>
        <kbd>Ctrl+Shift+J</kbd>
        <span style="color:#1e293b">shortcut</span>
      </div>

      <div class="body" id="body">
        <div class="idle">
          <div class="idle-icon">⬡</div>
          <div class="idle-main">Ready to verify</div>
          <div class="idle-sub">
            ${config
              ? `Click <b style="color:#00ff9d">SCAN</b> for latest ${config.name} response`
              : `Select text → click <b style="color:#00d4ff">SELECTION</b>`}
          </div>
        </div>
      </div>

      <div class="footer">
        <div class="f-title">RECENT VERDICTS</div>
        <div id="hist"></div>
      </div>
    </div>
  `;

  shadowRoot.getElementById("btn-scan").onclick = scanLatest;
  shadowRoot.getElementById("btn-sel").onclick = scanSel;
  shadowRoot.getElementById("btn-x").onclick = () => setSidebar(false);

  void loadHistory();
}

function setSidebar(open) {
  sidebarOpen = open;
  const panel = shadowRoot?.getElementById("panel");
  const host = document.getElementById("juror-host");
  if (!panel || !host) return;

  if (open) {
    panel.classList.add("open");
    host.style.pointerEvents = "all";
    document.documentElement.style.setProperty("padding-right", `${SIDEBAR_WIDTH}px`, "important");
    document.documentElement.style.setProperty("transition", "padding-right 0.25s ease", "important");
  } else {
    panel.classList.remove("open");
    host.style.pointerEvents = "none";
    document.documentElement.style.removeProperty("padding-right");
    document.documentElement.style.removeProperty("transition");
  }

  setToggleStyle(open);
}

function setBody(html) {
  const body = shadowRoot?.getElementById("body");
  if (body) body.innerHTML = html;
}

function showLoading(label) {
  setBody(`
    <div class="loading">
      <div class="spin">⬡</div>
      <div class="loading-main">Jury convening...</div>
      <div class="loading-sub">5 agents · Gemini 2.5 Flash<br>${label}</div>
    </div>
  `);
}

function showError(message, hint) {
  setBody(`
    <div class="err-box">
      🔴 ${esc(message)}
      ${hint ? `<code>${esc(hint)}</code>` : ""}
    </div>
  `);
}

function showWarn(message) {
  setBody(`<div class="warn-box">⚠️ ${esc(message)}</div>`);
}

function showVerdict(data) {
  if (!data?.final_verdict) {
    showError("Invalid server response");
    return;
  }

  const verdict = data.final_verdict;
  const color = { APPROVED: "#34d399", FLAGGED: "#fbbf24", BLOCKED: "#f87171" }[verdict] || "#94a3b8";
  const icon = { APPROVED: "✅", FLAGGED: "⚠️", BLOCKED: "🚫" }[verdict] || "?";

  const agents = (data.agent_results || [])
    .map((agent) => {
      const verdictColor = { PASS: "#34d399", FAIL: "#f87171", UNCERTAIN: "#fbbf24" }[agent.verdict] || "#64748b";
      const verdictIcon = { PASS: "✓", FAIL: "✗", UNCERTAIN: "?" }[agent.verdict] || "?";
      const klass = agent.verdict === "FAIL" ? "fail" : agent.verdict === "PASS" ? "pass" : "";
      const issues = (agent.issues || [])
        .slice(0, 2)
        .map((issue) => `<div class="a-issue">• ${esc(issue)}</div>`)
        .join("");
      return `
        <div class="agent ${klass}">
          <div class="a-row">
            <span class="a-name">A${agent.agent_id} ${esc(agent.agent_name)}</span>
            <span class="a-verd" style="color:${verdictColor}">${verdictIcon} ${agent.verdict}</span>
          </div>
          ${issues}
        </div>
      `;
    })
    .join("");

  const issueSummary = (() => {
    const issues = (data.issues_summary || []).filter(Boolean).slice(0, 4);
    if (!issues.length) return "";
    return `
      <div class="iss-block">
        <div class="iss-title">ISSUES FOUND</div>
        ${issues.map((issue) => `<div class="iss-line">• ${esc(issue)}</div>`).join("")}
      </div>
    `;
  })();

  const fixBlock = verdict === "BLOCKED" && data.correction
    ? `
      <div class="fix">
        <div class="fix-title">✦ CORRECTED (Agent 6)</div>
        <div class="fix-body">${esc(data.correction.substring(0, 500))}${data.correction.length > 500 ? "\n..." : ""}</div>
        <button class="copy-btn" id="copy-fix">Copy Correction</button>
      </div>
    `
    : "";

  setBody(`
    <div class="v-banner" style="border-color:${color}; background:${color}14">
      <div class="v-main" style="color:${color}">${icon} ${verdict}</div>
      <div class="v-sub">${data.fail_count}/5 failed · ${Math.round((data.overall_confidence || 0) * 100)}% conf · ${data.execution_time_ms}ms</div>
    </div>
    <div class="v-dom">${esc(data.domain || "general")}</div>
    <div class="agents">${agents}</div>
    ${issueSummary}
    ${fixBlock}
  `);

  const copyButton = shadowRoot?.getElementById("copy-fix");
  if (copyButton && data.correction) {
    copyButton.onclick = () => {
      void navigator.clipboard.writeText(data.correction);
      copyButton.textContent = "Copied!";
      setTimeout(() => {
        copyButton.textContent = "Copy Correction";
      }, 2000);
    };
  }

  addHist(verdict, data.domain, color);
}

function addHist(verdict, domain, color) {
  const history = shadowRoot?.getElementById("hist");
  if (!history) return;

  const item = document.createElement("div");
  item.className = "hist";
  item.style.color = color;
  item.textContent = `${verdict} · ${domain || "general"}`;
  history.insertBefore(item, history.firstChild);

  while (history.children.length > 5) {
    history.removeChild(history.lastChild);
  }
}

async function loadHistory() {
  try {
    const response = await fetch(`${JUROR_URL}/history?limit=5`, { signal: AbortSignal.timeout(3000) });
    if (!response.ok) return;
    const payload = await response.json();
    for (const entry of (payload.history || []).slice(0, 5)) {
      const color = { APPROVED: "#34d399", FLAGGED: "#fbbf24", BLOCKED: "#f87171" }[entry.final_verdict] || "#64748b";
      addHist(entry.final_verdict, entry.domain, color);
    }
  } catch (_) {
    return;
  }
}

async function verify(content, label) {
  if (isVerifying) {
    showWarn("Already verifying. Please wait.");
    return;
  }

  const contentHash = hash(content);
  if (contentHash === lastVerifiedHash) {
    showWarn("Already verified this content. Get a new AI response first.");
    return;
  }

  isVerifying = true;
  setSidebar(true);
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

    if (!response.ok) {
      throw new Error(`Server ${response.status}`);
    }

    const data = await response.json();
    if (!data.final_verdict || !Array.isArray(data.agent_results)) {
      throw new Error("Malformed response from server");
    }

    lastVerifiedHash = contentHash;
    showVerdict(data);
  } catch (error) {
    if (error?.name === "AbortError") {
      showError("Request timed out", "Check that the Juror server is still running.");
    } else if (error instanceof Error && (error.message.includes("fetch") || error.message.includes("NetworkError"))) {
      showError("Cannot reach server on localhost:8000", "python -m server.main");
    } else if (error instanceof Error) {
      showError(error.message);
    } else {
      showError("Unknown Chrome extension error");
    }
  } finally {
    isVerifying = false;
  }
}

async function scanLatest() {
  const content = extractResponse();
  const config = getSiteConfig();
  if (!content) {
    setSidebar(true);
    showWarn(
      config
        ? `No completed response found on ${config.name}. Ask a question first, then click SCAN once the response finishes.`
        : "SCAN only works on known AI sites. Use SELECTION: highlight any text then click SELECTION."
    );
    return;
  }

  await verify(content, getSiteConfig()?.name || "page");
}

async function scanSel() {
  const text = getSelectedText();
  if (!text) {
    setSidebar(true);
    showWarn("No text selected. Highlight any text on the page first, then click SELECTION.");
    return;
  }

  await verify(text, "selected text");
}

function startMonitor() {
  if (!getSiteConfig()) return;

  let timer = null;
  let lastSeen = "";

  new MutationObserver(() => {
    if (isVerifying) return;
    clearTimeout(timer);
    timer = setTimeout(() => {
      if (!isStreamDone()) return;
      const text = extractResponse();
      if (!text || text === lastSeen || text.length < 100) return;
      if (hash(text) === lastVerifiedHash) return;
      lastSeen = text;
      void verify(text, `${getSiteConfig().name} · auto`);
    }, 2000);
  }).observe(document.body, { childList: true, subtree: true });
}

document.addEventListener("keydown", (event) => {
  if (event.ctrlKey && event.shiftKey && event.key === "J") {
    event.preventDefault();
    setSidebar(true);

    const selected = getSelectedText();
    if (selected) {
      void verify(selected, "keyboard · selected text");
      return;
    }

    const response = extractResponse();
    if (response) {
      void verify(response, "keyboard · latest response");
      return;
    }

    showWarn("Select text first, or wait for an AI response.");
  }

  if (event.key === "Escape" && sidebarOpen) {
    setSidebar(false);
  }
});

chrome.runtime.onMessage.addListener((message) => {
  if (message.type === "MANUAL_VERIFY") void scanLatest();
  if (message.type === "VERIFY_SELECTED_TEXT") void scanSel();
  if (message.type === "TOGGLE_SIDEBAR") setSidebar(!sidebarOpen);
});

function esc(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

createToggleButton();
buildSidebar();
startMonitor();
