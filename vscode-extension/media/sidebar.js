const vscode = acquireVsCodeApi();

const content = document.getElementById("content");
const verifyButton = document.getElementById("verify-button");
const serverStatus = document.getElementById("server-status");

verifyButton?.addEventListener("click", () => {
  verifyButton.disabled = true;
  verifyButton.textContent = "Verifying...";
  content.innerHTML = `
    <div class="loading">
      <div class="loading-title">Jury convening...</div>
      <div class="loading-copy">Running the 5-agent review against your current file or selection.</div>
    </div>
  `;
  vscode.postMessage({ command: "verify" });
});

window.addEventListener("message", (event) => {
  const message = event.data;

  if (message.type === "health") {
    renderHealth(Boolean(message.healthy));
    if (!message.healthy) {
      content.innerHTML = `<div class="error">Juror server is unreachable. Run <code>juror start</code> and try again.</div>`;
    }
    return;
  }

  if (message.type === "error") {
    resetButton();
    content.innerHTML = `<div class="error">${escapeHtml(message.message)}</div>`;
    return;
  }

  if (message.type === "loading") {
    resetButton();
    content.innerHTML = `
      <div class="loading">
        <div class="loading-title">Jury convening...</div>
        <div class="loading-copy">${escapeHtml(message.message)}</div>
      </div>
    `;
    return;
  }

  if (message.type === "verdict") {
    resetButton();
    renderVerdict(message.data);
  }
});

function renderVerdict(data) {
  const colors = {
    APPROVED: "#34d399",
    FLAGGED: "#fbbf24",
    BLOCKED: "#f87171"
  };
  const color = colors[data.final_verdict] || "#94a3b8";

  const verdictHtml = `
    <div class="verdict-banner" style="border-color:${color}; background:${color}14">
      <div class="verdict-main" style="color:${color}">${escapeHtml(data.final_verdict)}</div>
      <div class="verdict-details">${data.fail_count}/5 failed · ${(data.overall_confidence * 100).toFixed(0)}% confidence · ${data.execution_time_ms}ms</div>
    </div>
  `;

  const domainHtml = `
    <div class="domain-row">
      <div class="domain-pill">${escapeHtml(data.domain || "general")}</div>
      <div class="meta-pill">5-agent jury</div>
    </div>
  `;

  const agentHtml = (data.agent_results || []).map((agent) => {
    const verdictClass = {
      PASS: "verdict-pass",
      FAIL: "verdict-fail",
      UNCERTAIN: "verdict-uncertain"
    }[agent.verdict] || "";

    const issues = (agent.issues || [])
      .slice(0, 2)
      .map((issue) => `<div class="issue">- ${escapeHtml(issue)}</div>`)
      .join("");

    return `
      <div class="agent">
        <div class="agent-header">
          <span class="agent-name">A${agent.agent_id} ${escapeHtml(agent.agent_name)}</span>
          <span class="${verdictClass}">${escapeHtml(agent.verdict)}</span>
        </div>
        ${issues}
      </div>
    `;
  }).join("");

  const summaryHtml = (data.issues_summary || []).length
    ? `
      <div class="issues-summary">
        <div class="issues-summary-title">Issues Found</div>
        ${(data.issues_summary || []).slice(0, 4).map((issue) => `<div class="summary-line">- ${escapeHtml(issue)}</div>`).join("")}
      </div>
    `
    : "";

  const correctionHtml = data.final_verdict === "BLOCKED" && data.correction
    ? `
      <div class="correction">
        <div class="correction-title">Corrected Output (Agent 6)</div>
        ${escapeHtml(data.correction.substring(0, 700))}
      </div>
    `
    : "";

  content.innerHTML = verdictHtml + domainHtml + agentHtml + summaryHtml + correctionHtml;
}

function renderHealth(healthy) {
  if (!serverStatus) return;
  serverStatus.className = `server-status ${healthy ? "ok" : "offline"}`;
  serverStatus.textContent = healthy ? "Server online" : "Server offline";
}

function resetButton() {
  if (!verifyButton) return;
  verifyButton.disabled = false;
  verifyButton.textContent = "Verify current file or selection";
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}
