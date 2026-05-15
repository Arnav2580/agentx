/**
 * AI Hallucination Juror - Chrome content script
 *
 * Goals:
 * - Better dark-mode contrast and typography
 * - Claude-friendly layout that feels native instead of bolted on
 * - More reliable latest-response extraction, especially on Claude
 * - Cleaner page shifting so the panel does not crush the host layout
 */

const JUROR_URL = "http://localhost:8000";
const PANEL_WIDTH = 368;
const MIN_TEXT_LENGTH = 20;

const TOKENS = {
  bg: "var(--bg)",
  bgElevated: "var(--bgElevated)",
  bgRaised: "var(--bgRaised)",
  bgPanel: "var(--bgPanel)",
  border: "var(--border)",
  borderStrong: "var(--borderStrong)",
  text: "var(--text)",
  textSecondary: "var(--textSecondary)",
  textMuted: "var(--textMuted)",
  textFaint: "var(--textFaint)",
  accent: "var(--accent)",
  accentSoft: "var(--accentSoft)",
  accentBg: "var(--accentBg)",
  success: "var(--success)",
  warning: "var(--warning)",
  danger: "var(--danger)",
  info: "var(--info)",
};

let shadowHost = null;
let shadowRootRef = null;
let toggleButton = null;
let isVerifying = false;
let sidebarOpen = false;
let lastVerifiedHash = 0;
let pushedElements = [];
let lastObservedResponseHash = 0;

const SITES = {
  "claude.ai": {
    name: "Claude",
    selectors: [
      '[data-testid="assistant-message"] [data-testid="message-content"]',
      '[data-testid="assistant-message"]',
      '[data-testid="message-content"]',
      '[data-is-streaming="false"] .font-claude-message',
      ".font-claude-message",
      '[class*="assistant"] [class*="prose"]',
      'main [class*="prose"]',
      '.grid-cols-1',
      '[data-message-author-role="assistant"]',
      '.prose'
    ],
    busySelectors: [
      '[data-is-streaming="true"]',
      'button[aria-label*="Stop" i]',
      'button[title*="Stop" i]',
    ],
  },
  "chat.openai.com": {
    name: "ChatGPT",
    selectors: [
      '[data-message-author-role="assistant"] .markdown',
      '[data-message-author-role="assistant"]',
      '.agent-turn [class*="markdown"]',
    ],
    busySelectors: ['button[aria-label*="Stop" i]'],
  },
  "chatgpt.com": {
    name: "ChatGPT",
    selectors: [
      '[data-message-author-role="assistant"] .markdown',
      '[data-message-author-role="assistant"]',
    ],
    busySelectors: ['button[aria-label*="Stop" i]'],
  },
  "gemini.google.com": {
    name: "Gemini",
    selectors: [
      "model-response .response-content",
      ".response-content",
      "message-content",
      '[class*="response"][class*="content"]',
    ],
    busySelectors: ['button[aria-label*="Stop" i]'],
  },
  "aistudio.google.com": {
    name: "AI Studio",
    selectors: [
      ".response-container",
      '[class*="model"] [class*="response"]',
      ".output-content",
    ],
    busySelectors: ['button[aria-label*="Stop" i]'],
  },
  "copilot.microsoft.com": {
    name: "Copilot",
    selectors: [
      ".ac-textBlock",
      '[class*="assistant"] [class*="text"]',
      '[class*="bot"] [class*="content"]',
    ],
    busySelectors: [],
  },
  "perplexity.ai": {
    name: "Perplexity",
    selectors: [
      '[data-testid="answer"]',
      '[class*="answer"] .prose',
      '[class*="response"] .prose',
      ".prose",
    ],
    busySelectors: ['button[aria-label*="Stop" i]'],
  },
  "www.perplexity.ai": {
    name: "Perplexity",
    selectors: [
      '[data-testid="answer"]',
      '[class*="answer"] .prose',
      ".prose",
    ],
    busySelectors: ['button[aria-label*="Stop" i]'],
  },
  "grok.com": {
    name: "Grok",
    selectors: [
      '[class*="assistant"] [class*="message"]',
      '[class*="response"] [class*="content"]',
      ".prose",
    ],
    busySelectors: [],
  },
  "chat.mistral.ai": {
    name: "Mistral",
    selectors: [
      '[class*="assistant"] [class*="message-content"]',
      ".prose",
      '[class*="response"]',
    ],
    busySelectors: [],
  },
  "poe.com": {
    name: "Poe",
    selectors: [
      '[class*="botMessage"] [class*="content"]',
      '[class*="Message_botMessageBubble"]',
      '[class*="message"]',
    ],
    busySelectors: [],
  },
  "huggingface.co": {
    name: "HuggingChat",
    selectors: [
      '[class*="assistant"] [class*="prose"]',
      ".message-content",
      '[class*="chat"] [class*="assistant"]',
    ],
    busySelectors: [],
  },
  "chat.deepseek.com": {
    name: "DeepSeek",
    selectors: [
      '[class*="ds-markdown"]',
      '[class*="message"][class*="assistant"]',
      ".prose",
    ],
    busySelectors: [],
  },
  "you.com": {
    name: "You.com",
    selectors: [
      '[data-testid="ai-response"]',
      '[class*="aiResponse"]',
      '[class*="answer"] .prose',
    ],
    busySelectors: [],
  },
  "phind.com": {
    name: "Phind",
    selectors: [
      '[class*="answer"] [class*="prose"]',
      '[class*="response"]',
      ".prose",
    ],
    busySelectors: [],
  },
  "www.phind.com": {
    name: "Phind",
    selectors: [
      '[class*="answer"] [class*="prose"]',
      '[class*="response"]',
      ".prose",
    ],
    busySelectors: [],
  },
};

function getSite() {
  const normalized = location.hostname.replace(/^www\./, "");
  return SITES[normalized] || SITES[location.hostname] || null;
}

function normalizeText(value) {
  return String(value || "")
    .replace(/\u00a0/g, " ")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/[ \t]{2,}/g, " ")
    .trim();
}

function isVisible(element) {
  if (!element || !(element instanceof Element)) return false;
  const rect = element.getBoundingClientRect();
  if (!rect.width || !rect.height) return false;
  const style = window.getComputedStyle(element);
  return style.visibility !== "hidden" && style.display !== "none" && Number(style.opacity || "1") > 0;
}

function hasBadAncestor(element) {
  return Boolean(
    element.closest(
      [
        "#juror-shadow-host",
        "#juror-toggle",
        "textarea",
        "input",
        "form",
        "nav",
        "aside",
        "header",
        "footer",
        '[role="textbox"]',
        "[contenteditable='true']",
        '[data-testid*="composer"]',
        '[data-testid*="input"]',
      ].join(",")
    )
  );
}

function looksLikeUtilityText(text) {
  const lower = text.toLowerCase();
  if (text.length < 160) {
    return /(buy more|write a message|share|download|upload|rate limit|openclaw|adaptive)/i.test(lower);
  }
  return false;
}

function collectCandidatesFromSelectors(selectors) {
  const map = new Map();
  for (const selector of selectors) {
    let matches = [];
    try {
      matches = Array.from(document.querySelectorAll(selector));
    } catch (_) {
      matches = [];
    }
    for (const element of matches) {
      if (!map.has(element)) {
        map.set(element, true);
      }
    }
  }
  return Array.from(map.keys());
}

function universalSelectors() {
  return [
    "main article",
    'main [role="article"]',
    'main [class*="message"]',
    'main [class*="response"]',
    'main [class*="assistant"]',
    "main .prose",
    'main [data-testid*="message"]',
    '[role="main"] article',
    '[role="main"] .prose',
  ];
}

function scoreCandidate(element, text, site) {
  const rect = element.getBoundingClientRect();
  let score = Math.min(text.length, 5000);

  if (element.closest("main, article, [role='main']")) score += 240;
  if (element.closest('[data-testid*="assistant"], [data-author="assistant"], [class*="assistant"]')) score += 900;
  if (site?.name === "Claude" && element.closest('[data-testid="assistant-message"]')) score += 1200;
  if (site?.name === "Claude" && /free api setup|osv\.dev|pypi/i.test(text)) score += 500;

  if (rect.width > 340) score += 180;
  if (rect.height > 90) score += 120;
  if (text.split("\n").length > 3) score += 90;

  score += Math.max(0, rect.bottom) * 0.25;
  score -= Math.max(0, 120 - rect.top) * 1.5;

  if (looksLikeUtilityText(text)) score -= 900;
  if (rect.width < 180 || rect.height < 28) score -= 500;

  return score;
}

function findBestResponseCandidate() {
  const site = getSite();
  const selectors = site ? [...site.selectors, ...universalSelectors()] : universalSelectors();
  const candidates = collectCandidatesFromSelectors(selectors);

  const ranked = [];
  for (const element of candidates) {
    if (!isVisible(element) || hasBadAncestor(element)) continue;
    const text = normalizeText(element.innerText || element.textContent || "");
    if (text.length < MIN_TEXT_LENGTH) continue;
    ranked.push({
      element,
      text,
      score: scoreCandidate(element, text, site),
    });
  }

  ranked.sort((left, right) => right.score - left.score);
  return ranked[0] || null;
}

function extractResponse() {
  const best = findBestResponseCandidate();
  return best ? best.text : null;
}

function isStreamDone() {
  const site = getSite();
  if (!site || !site.busySelectors?.length) return true;
  return !site.busySelectors.some((selector) => {
    try {
      return document.querySelector(selector);
    } catch (_) {
      return false;
    }
  });
}

function selectedText() {
  const text = normalizeText(window.getSelection()?.toString() || "");
  return text.length > 30 ? text : null;
}

function hashOf(text) {
  let value = 0;
  for (let index = 0; index < Math.min(text.length, 200); index += 1) {
    value = (Math.imul(31, value) + text.charCodeAt(index)) | 0;
  }
  return value;
}

function findPushTarget() {
  const selectors = [
    "main",
    '[role="main"]',
    "#__next",
    "#root",
    "#app",
    '[data-testid="conversation"]',
    "body > div:first-child",
  ];

  let best = null;
  let bestArea = 0;
  for (const selector of selectors) {
    let matches = [];
    try {
      matches = Array.from(document.querySelectorAll(selector));
    } catch (_) {
      matches = [];
    }
    for (const element of matches) {
      if (!isVisible(element)) continue;
      const rect = element.getBoundingClientRect();
      const area = rect.width * rect.height;
      if (area > bestArea && rect.width > window.innerWidth * 0.35) {
        best = element;
        bestArea = area;
      }
    }
  }
  return best || document.body;
}

function resetPushStyles() {
  for (const element of pushedElements) {
    if (!element) continue;
    element.style.removeProperty("margin-right");
    element.style.removeProperty("transition");
  }
  pushedElements = [];
  document.documentElement.style.removeProperty("overflow-x");
}

function pushPage(open) {
  // We no longer push the page content. The sidebar floats elegantly as an overlay.
  // We just handle overflow gracefully to prevent double scrollbars.
  resetPushStyles();
  if (!open) return;
  document.documentElement.style.setProperty("overflow-x", "hidden", "important");
}

function makeToggle() {
  toggleButton = document.createElement("button");
  toggleButton.id = "juror-toggle";
  toggleButton.type = "button";
  applyToggleStyle(false);
  toggleButton.addEventListener("click", () => openSidebar(!sidebarOpen));
  document.documentElement.appendChild(toggleButton);
}

function applyToggleStyle(open) {
  if (!toggleButton) return;

  Object.assign(toggleButton.style, {
    position: "fixed",
    right: open ? `${PANEL_WIDTH + 16}px` : "16px",
    bottom: "20px",
    height: "42px",
    minWidth: open ? "86px" : "92px",
    padding: "0 16px",
    borderRadius: "999px",
    border: `1px solid ${open ? TOKENS.borderStrong : TOKENS.accentSoft}`,
    background: open ? TOKENS.bgRaised : TOKENS.accentBg,
    color: open ? TOKENS.text : TOKENS.accent,
    fontFamily: "Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    fontSize: "13px",
    fontWeight: "700",
    letterSpacing: "0.02em",
    cursor: "pointer",
    zIndex: "2147483646",
    boxShadow: "0 12px 30px rgba(0,0,0,0.28)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    transition: "right 180ms ease, background 180ms ease, color 180ms ease, border-color 180ms ease",
  });

  toggleButton.textContent = open ? "Close" : "Juror";
  toggleButton.title = open ? "Close Juror sidebar" : "Open Juror sidebar";
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

  shadowRootRef = shadowHost.attachShadow({ mode: "open" });
  const site = getSite();
  const siteName = site ? site.name : location.hostname.replace(/^www\./, "");
  const modeLabel = "Manual Mode Active";

  shadowRootRef.innerHTML = `
<style>
  :root {
    color-scheme: light dark;
    --bgPanel: linear-gradient(145deg, #ffffff, #f8fafc);
    --bgElevated: rgba(255, 255, 255, 0.6);
    --bgRaised: rgba(241, 245, 249, 0.8);
    --border: #e2e8f0;
    --borderStrong: #cbd5e1;
    --text: #0f172a;
    --textSecondary: #334155;
    --textMuted: #64748b;
    --textFaint: #94a3b8;
    --accent: #0f172a;
    --accentSoft: #94a3b8;
    --accentBg: #f1f5f9;
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
    --info: #38bdf8;
  }

  @media (prefers-color-scheme: dark) {
    :root {
      --bgPanel: radial-gradient(circle at top right, rgba(30, 27, 75, 0.95) 0%, rgba(2, 6, 23, 0.98) 40%);
      --bgElevated: rgba(15, 23, 42, 0.6);
      --bgRaised: rgba(30, 41, 59, 0.6);
      --border: rgba(255, 255, 255, 0.1);
      --borderStrong: rgba(255, 255, 255, 0.15);
      --text: #f8fafc;
      --textSecondary: #cbd5e1;
      --textMuted: #94a3b8;
      --textFaint: #64748b;
      --accent: #38bdf8;
      --accentSoft: rgba(56, 189, 248, 0.2);
      --accentBg: rgba(56, 189, 248, 0.1);
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --info: #38bdf8;
    }
  }

  *, *::before, *::after { box-sizing: border-box; }

  #panel {
    position: fixed;
    top: 0;
    right: -${PANEL_WIDTH + 10}px;
    width: ${PANEL_WIDTH}px;
    height: 100vh;
    background: var(--bgPanel);
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    color: var(--text);
    display: flex;
    flex-direction: column;
    border-left: 1px solid color-mix(in srgb, var(--border) 60%, transparent);
    box-shadow: -24px 0 64px rgba(0, 0, 0, 0.35);
    transition: right 240ms cubic-bezier(0.16, 1, 0.3, 1);
    pointer-events: all;
    overflow: hidden;
    font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }

  #panel.open { right: 0; }

  .header {
    padding: 16px;
    background: ${TOKENS.bg};
    border-bottom: 1px solid ${TOKENS.border};
    flex-shrink: 0;
  }

  .header-top {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .brand-mark {
    width: 22px;
    height: 22px;
    border-radius: 7px;
    border: 1px solid ${TOKENS.accentSoft};
    background: ${TOKENS.accentBg};
    color: ${TOKENS.accent};
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.04em;
    flex-shrink: 0;
  }

  .brand-copy {
    min-width: 0;
    flex: 1;
  }

  .brand-title {
    color: ${TOKENS.text};
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.02em;
  }

  .brand-subtitle {
    margin-top: 2px;
    color: ${TOKENS.textMuted};
    font-size: 12px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .close-button {
    width: 32px;
    height: 32px;
    border: 1px solid ${TOKENS.borderStrong};
    border-radius: 999px;
    background: ${TOKENS.bgRaised};
    color: ${TOKENS.textSecondary};
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 14px;
    font-weight: 700;
  }

  .close-button:hover {
    border-color: ${TOKENS.textMuted};
    color: ${TOKENS.text};
  }

  .button-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-top: 14px;
  }

  .button {
    height: 42px;
    border-radius: 10px;
    border: 1px solid ${TOKENS.borderStrong};
    background: ${TOKENS.bgRaised};
    color: ${TOKENS.text};
    font-family: inherit;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
  }

  .button:hover {
    border-color: ${TOKENS.accentSoft};
    background: #35342f;
  }

  .button.primary {
    background: ${TOKENS.accentBg};
    border-color: ${TOKENS.accentSoft};
    color: ${TOKENS.accent};
  }

  .status-strip {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    border-bottom: 1px solid ${TOKENS.border};
    background: ${TOKENS.bgPanel};
    color: ${TOKENS.textMuted};
    font-size: 12px;
    flex-shrink: 0;
  }

  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 999px;
    background: ${site ? TOKENS.success : TOKENS.warning};
    box-shadow: 0 0 0 4px rgba(125, 211, 122, 0.08);
    flex-shrink: 0;
  }

  .shortcut-chip {
    margin-left: auto;
    padding: 4px 8px;
    border: 1px solid ${TOKENS.borderStrong};
    border-radius: 8px;
    background: ${TOKENS.bgElevated};
    color: ${TOKENS.textFaint};
    font-size: 11px;
  }

  .body {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    background: ${TOKENS.bgPanel};
  }

  .body::-webkit-scrollbar {
    width: 6px;
  }

  .body::-webkit-scrollbar-thumb {
    background: ${TOKENS.borderStrong};
    border-radius: 999px;
  }

  .empty-state,
  .loading-state,
  .message-card,
  .summary-card,
  .correction-card,
  .agent-card {
    border: 1px solid ${TOKENS.border};
    border-radius: 14px;
    background: ${TOKENS.bgElevated};
  }

  .empty-state,
  .loading-state,
  .message-card {
    padding: 16px;
  }

  .empty-title,
  .loading-title {
    color: ${TOKENS.text};
    font-size: 16px;
    font-weight: 700;
    margin-bottom: 8px;
  }

  .empty-copy,
  .loading-copy,
  .message-copy {
    color: ${TOKENS.textSecondary};
    line-height: 1.65;
    font-size: 13px;
  }

  .loading-copy {
    color: ${TOKENS.textMuted};
  }

  .message-card.warn {
    border-color: rgba(241, 197, 93, 0.28);
    background: rgba(241, 197, 93, 0.08);
  }

  .message-card.error {
    border-color: rgba(239, 127, 127, 0.30);
    background: rgba(239, 127, 127, 0.09);
  }

  .message-title {
    color: ${TOKENS.text};
    font-size: 14px;
    font-weight: 700;
    margin-bottom: 6px;
  }

  .message-hint {
    margin-top: 10px;
    padding: 10px 12px;
    border-radius: 10px;
    background: ${TOKENS.bg};
    color: ${TOKENS.textMuted};
    font-size: 12px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }

  .verdict-banner {
    margin-bottom: 14px;
    border-radius: 16px;
    border: 1px solid;
    padding: 16px;
    background: ${TOKENS.bg};
  }

  .verdict-label {
    font-size: 18px;
    font-weight: 800;
    letter-spacing: 0.04em;
  }

  .verdict-meta {
    margin-top: 8px;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    color: ${TOKENS.textMuted};
    font-size: 12px;
  }

  .chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 9px;
    border-radius: 999px;
    border: 1px solid ${TOKENS.borderStrong};
    background: ${TOKENS.bg};
  }

  .section-title {
    margin: 16px 0 10px;
    color: ${TOKENS.textMuted};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .agent-list {
    display: grid;
    gap: 8px;
  }

  .agent-card {
    padding: 12px;
  }

  .agent-card.fail {
    border-color: rgba(239, 127, 127, 0.28);
  }

  .agent-card.pass {
    border-color: rgba(125, 211, 122, 0.22);
  }

  .agent-top {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .agent-id {
    color: ${TOKENS.textFaint};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.05em;
  }

  .agent-name {
    flex: 1;
    color: ${TOKENS.text};
    font-size: 13px;
    font-weight: 600;
  }

  .agent-verdict {
    font-size: 12px;
    font-weight: 700;
  }

  .agent-issue {
    margin-top: 8px;
    padding-left: 10px;
    border-left: 2px solid rgba(239, 127, 127, 0.25);
    color: ${TOKENS.textSecondary};
    font-size: 12px;
    line-height: 1.6;
  }

  .summary-card,
  .correction-card {
    padding: 14px;
  }

  .summary-line {
    color: ${TOKENS.textSecondary};
    font-size: 13px;
    line-height: 1.6;
    margin-top: 6px;
  }

  .correction-card {
    border-color: rgba(141, 182, 255, 0.24);
    background: rgba(141, 182, 255, 0.07);
  }

  .correction-copy {
    max-height: 180px;
    overflow-y: auto;
    color: ${TOKENS.textSecondary};
    font-size: 12px;
    line-height: 1.7;
    white-space: pre-wrap;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }

  .copy-button {
    margin-top: 12px;
    height: 36px;
    border-radius: 10px;
    border: 1px solid rgba(141, 182, 255, 0.32);
    background: rgba(141, 182, 255, 0.10);
    color: ${TOKENS.info};
    font-family: inherit;
    font-size: 12px;
    font-weight: 700;
    cursor: pointer;
  }

  .footer {
    padding: 14px 16px 16px;
    border-top: 1px solid ${TOKENS.border};
    background: ${TOKENS.bg};
    flex-shrink: 0;
  }

  .history-list {
    display: grid;
    gap: 8px;
    max-height: 128px;
    overflow-y: auto;
  }

  .history-row {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    padding: 9px 10px;
    border: 1px solid ${TOKENS.border};
    border-radius: 10px;
    background: ${TOKENS.bgElevated};
    font-size: 12px;
  }

  .history-domain {
    color: ${TOKENS.textMuted};
    text-align: right;
  }
</style>

<div id="panel">
  <div class="header">
    <div class="header-top">
      <div class="brand-mark">J</div>
      <div class="brand-copy">
        <div class="brand-title">Hallucination Juror</div>
        <div class="brand-subtitle">${escapeHtml(siteName)} | ${escapeHtml(modeLabel)}</div>
      </div>
      <button id="juror-close" class="close-button" type="button">x</button>
    </div>
    <div class="button-row">
      <button id="juror-scan" class="button primary" type="button">Scan response</button>
      <button id="juror-selection" class="button" type="button">Selection</button>
    </div>
  </div>

  <div class="status-strip">
    <span class="status-dot"></span>
    <span>${site ? "Watching this AI page" : "Use text selection on any page"}</span>
    <span class="shortcut-chip">Ctrl+Shift+J</span>
  </div>

  <div id="juror-body" class="body">
    <div class="empty-state">
      <div class="empty-title">Ready to verify</div>
      <div class="empty-copy">${site
        ? `Click "Scan response" after ${escapeHtml(siteName)} finishes replying, or select part of the answer and use "Selection".`
        : 'Select any block of text on the page, then use "Selection" or press Ctrl+Shift+J.'}</div>
    </div>
  </div>

  <div class="footer">
    <div class="section-title" style="margin-top:0">Recent verdicts</div>
    <div id="juror-history" class="history-list"></div>
  </div>
</div>
  `;

  shadowRootRef.getElementById("juror-close").addEventListener("click", () => openSidebar(false));
  shadowRootRef.getElementById("juror-scan").addEventListener("click", () => {
    void scanResponse("manual");
  });
  shadowRootRef.getElementById("juror-selection").addEventListener("click", () => {
    void scanSelection("manual");
  });

  void loadHistory();
}

function openSidebar(open) {
  sidebarOpen = open;
  const panel = shadowRootRef?.getElementById("panel");
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
  const body = shadowRootRef?.getElementById("juror-body");
  if (body) body.innerHTML = html;
}

function showIdle() {
  const site = getSite();
  const siteName = site ? site.name : location.hostname.replace(/^www\./, "");
  setBody(`
    <div class="empty-state">
      <div class="empty-title">Ready to verify</div>
      <div class="empty-copy">${site
        ? `Click "Scan response" after ${escapeHtml(siteName)} finishes replying, or select part of the answer and use "Selection".`
        : 'Select any block of text on the page, then use "Selection" or press Ctrl+Shift+J.'}</div>
    </div>
  `);
}

function showLoading(label) {
  setBody(`
    <div class="loading-state">
      <div class="loading-title">Checking the latest response</div>
      <div class="loading-copy">Running the 5-agent jury with Gemini 2.5 Flash.<br>${escapeHtml(label || "")}</div>
    </div>
  `);
}

function showWarn(message) {
  setBody(`
    <div class="message-card warn">
      <div class="message-title">Need a clearer response</div>
      <div class="message-copy">${escapeHtml(message)}</div>
    </div>
  `);
}

function showError(message, hint) {
  setBody(`
    <div class="message-card error">
      <div class="message-title">Juror could not verify this response</div>
      <div class="message-copy">${escapeHtml(message)}</div>
      ${hint ? `<div class="message-hint">${escapeHtml(hint)}</div>` : ""}
    </div>
  `);
}

function verdictColor(verdict) {
  return {
    APPROVED: TOKENS.success,
    FLAGGED: TOKENS.warning,
    BLOCKED: TOKENS.danger,
  }[verdict] || TOKENS.textMuted;
}

function showVerdict(data) {
  if (!data?.final_verdict) {
    showError("Unexpected response from the Juror server.");
    return;
  }

  const verdict = data.final_verdict;
  const color = verdictColor(verdict);
  let html = `
    <div class="verdict-banner" style="border-color:${color}55">
      <div class="verdict-label" style="color:${color}">${escapeHtml(verdict)}</div>
      <div class="verdict-meta">
        <span class="chip">${Number(data.fail_count || 0)}/5 agents flagged</span>
        <span class="chip">${Math.round((data.overall_confidence || 0) * 100)}% confidence</span>
        <span class="chip">${escapeHtml(String(data.execution_time_ms || 0))} ms</span>
      </div>
    </div>
    <div class="section-title">Domain</div>
    <div class="summary-card">
      <div class="summary-line">${escapeHtml((data.domain || "general").replace(/_/g, " "))}</div>
    </div>
    <div class="section-title">Agent verdicts</div>
    <div class="agent-list">
  `;

  for (const agent of data.agent_results || []) {
    const agentColor = {
      PASS: TOKENS.success,
      FAIL: TOKENS.danger,
      UNCERTAIN: TOKENS.warning,
    }[agent.verdict] || TOKENS.textMuted;
    const cardClass = agent.verdict === "FAIL" ? "fail" : agent.verdict === "PASS" ? "pass" : "";
    html += `
      <div class="agent-card ${cardClass}">
        <div class="agent-top">
          <div class="agent-id">A${escapeHtml(String(agent.agent_id))}</div>
          <div class="agent-name">${escapeHtml(agent.agent_name)}</div>
          <div class="agent-verdict" style="color:${agentColor}">${escapeHtml(agent.verdict)}</div>
        </div>
        ${(agent.issues || []).slice(0, 2).map((issue) => `<div class="agent-issue">${escapeHtml(issue)}</div>`).join("")}
      </div>
    `;
  }
  html += "</div>";

  const issues = (data.issues_summary || []).filter(Boolean).slice(0, 5);
  if (issues.length) {
    html += `
      <div class="section-title">Issues found</div>
      <div class="summary-card">
        ${issues.map((issue) => `<div class="summary-line">${escapeHtml(issue)}</div>`).join("")}
      </div>
    `;
  }

  if (verdict === "BLOCKED" && data.correction) {
    html += `
      <div class="section-title">Corrected output</div>
      <div class="correction-card">
        <div class="correction-copy">${escapeHtml(data.correction.substring(0, 900))}${data.correction.length > 900 ? "\n..." : ""}</div>
        <button id="juror-copy" class="copy-button" type="button">Copy correction</button>
      </div>
    `;
  }

  setBody(html);

  const copyButton = shadowRootRef?.getElementById("juror-copy");
  if (copyButton && data.correction) {
    copyButton.addEventListener("click", () => {
      void navigator.clipboard.writeText(data.correction);
      copyButton.textContent = "Copied";
      setTimeout(() => {
        copyButton.textContent = "Copy correction";
      }, 1800);
    });
  }

  addHistory(verdict, data.domain, color);
}

function addHistory(verdict, domain, color) {
  const history = shadowRootRef?.getElementById("juror-history");
  if (!history) return;

  const row = document.createElement("div");
  row.className = "history-row";
  row.innerHTML = `
    <span style="color:${color}; font-weight:700">${escapeHtml(verdict)}</span>
    <span class="history-domain">${escapeHtml((domain || "general").replace(/_/g, " "))}</span>
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
    const history = shadowRootRef?.getElementById("juror-history");
    if (history) history.innerHTML = "";
    for (const item of (data.history || []).slice(0, 5)) {
      addHistory(item.final_verdict, item.domain, verdictColor(item.final_verdict));
    }
  } catch (_) {
    return;
  }
}

async function verifyContent(content, modeLabel) {
  if (isVerifying) {
    showWarn("Juror is already checking another response. Give it a moment.");
    return;
  }

  const responseHash = hashOf(content);
  if (responseHash === lastVerifiedHash) {
    showWarn("That exact response was already verified. Try a fresh answer or select a different block.");
    return;
  }

  isVerifying = true;
  openSidebar(true);
  showLoading(modeLabel);

  const site = getSite();
  const source = `chrome:${location.hostname.replace(/^www\./, "")}`;
  const context = `${site ? site.name : "Web page"} | ${modeLabel}`;

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60000);
    const response = await fetch(`${JUROR_URL}/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content: content.substring(0, 3000),
        source,
        context,
      }),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!response.ok) {
      throw new Error(`Server returned ${response.status}`);
    }

    const data = await response.json();
    if (!data.final_verdict || !Array.isArray(data.agent_results)) {
      throw new Error("The Juror server returned an unexpected response.");
    }

    lastVerifiedHash = responseHash;
    showVerdict(data);
  } catch (error) {
    if (error?.name === "AbortError") {
      showError("The request timed out before Juror finished the review.", "python -m server.main");
    } else if (error instanceof Error && (error.message.includes("fetch") || error.message.includes("NetworkError"))) {
      showError("Juror could not reach the local server on localhost:8000.", "python -m server.main");
    } else if (error instanceof Error) {
      showError(error.message);
    } else {
      showError("An unknown Chrome extension error occurred.");
    }
  } finally {
    isVerifying = false;
  }
}

async function scanResponse(trigger) {
  const candidate = findBestResponseCandidate();
  if (!candidate) {
    openSidebar(true);
    showWarn(
      getSite()
        ? `Juror could not find a solid assistant response on ${getSite().name} yet. Wait for the answer to finish, or highlight the text and use Selection.`
        : "Scan response works best on supported AI sites. On any page, highlight text and use Selection instead."
    );
    return;
  }

  if (trigger === "auto" && !isStreamDone()) {
    return;
  }

  lastObservedResponseHash = hashOf(candidate.text);
  await verifyContent(candidate.text, `${getSite()?.name || "Page"} | ${trigger}`);
}

async function scanSelection(trigger) {
  const text = selectedText();
  if (!text) {
    openSidebar(true);
    showWarn("Select the exact answer text you want checked, then try Selection again.");
    return;
  }
  await verifyContent(text, `Selection | ${trigger}`);
}

function startMonitor() {
  // Auto-watch feature has been disabled to save Gemini API rate limits.
  // The user must manually click 'Scan latest response' or use the shortcut.
  return;
}

document.addEventListener("keydown", (event) => {
  if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "j") {
    event.preventDefault();
    openSidebar(true);
    const text = selectedText();
    if (text) {
      void verifyContent(text, "Keyboard selection");
    } else {
      void scanResponse("keyboard");
    }
  }

  if (event.key === "Escape" && sidebarOpen) {
    openSidebar(false);
  }
});

chrome.runtime.onMessage.addListener((message) => {
  if (message.type === "MANUAL_VERIFY") {
    void scanResponse("popup");
  }
  if (message.type === "VERIFY_SELECTED_TEXT") {
    void scanSelection("popup");
  }
  if (message.type === "TOGGLE_SIDEBAR") {
    openSidebar(!sidebarOpen);
  }
});

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

makeToggle();
buildSidebar();
showIdle();
// startMonitor();
